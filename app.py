import streamlit as st
from datetime import datetime, timezone, timedelta
import asyncio
import os
import tempfile
import subprocess
import re
import requests
from groq import Groq
import edge_tts
from pathlib import Path
from streamlit_cookies_manager import EncryptedCookieManager
import streamlit as st

# MUST BE FIRST STREAMLIT CALL
st.set_page_config(page_title="STT + TTS", layout="centered")

# now you can use session_state, etc.
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ... rest of your code

# === CONFIGURATION ===
GROQ_API_KEY = "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"
VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"
OUTPUT_FOLDER = Path("static/audio")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
client = Groq(api_key=GROQ_API_KEY)

# === COOKIES ===
cookies = EncryptedCookieManager(prefix="myapp_", password="super-secret-key")
if not cookies.ready():
    st.stop()

# === SESSION INIT ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = cookies.get("auth") == "1"

# === LOGIN ===
def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            cookies.set("auth", "1", max_age_days=7)
            st.rerun()
        else:
            st.error("❌ Invalid credentials")

# === LOGOUT ===
def logout():
    st.session_state.authenticated = False
    cookies.delete("auth")
    st.success("Logged out successfully")
    st.rerun()

# === UTILS ===
def delete_file_later(filepath, delay=300):
    import threading, time
    def delayed_delete():
        time.sleep(delay)
        try:
            os.remove(filepath)
        except:
            pass
    threading.Thread(target=delayed_delete, daemon=True).start()

language_map = {
    "Hindi": "hi",
    "English": "en",
    "Malayalam": "ml"
}

def extract_youtube_video_id(url):
    patterns = [
        r'youtu\.be/([^&?/]+)',
        r'youtube\.com/embed/([^&?/]+)',
        r'youtube\.com/v/([^&?/]+)',
        r"v=([^&]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# === STT ===
def show_stt():
    st.header("🎙️ YouTube Speech to Text")
    st.subheader("1. Download YouTube Audio")
    youtube_url = st.text_input("YouTube Video URL")

    if st.button("🎵 Download & Convert"):
        video_id = extract_youtube_video_id(youtube_url)
        if not video_id:
            st.error("❌ Invalid YouTube URL")
            return

        temp_dir = tempfile.mkdtemp()
        input_file = os.path.join(temp_dir, f"{video_id}.m4a")
        wav_file = os.path.join(temp_dir, f"{video_id}.wav")

        try:
            subprocess.run(["yt-dlp", "-f", "bestaudio[ext=m4a]", "-o", input_file, youtube_url], check=True)
            subprocess.run(["ffmpeg", "-y", "-i", input_file, wav_file], check=True)
            st.audio(wav_file)
            st.session_state.wav_file = wav_file
            st.download_button("⬇️ Download WAV", open(wav_file, "rb"), f"{video_id}.wav")
        except Exception as e:
            st.error(str(e))

    st.subheader("2. Choose Engine & Language")
    engine = st.radio("Engine", ["Groq", "IITM"])
    selected_lang = st.selectbox("Language", list(language_map.keys()))
    lang_code = language_map[selected_lang]

    if st.button("📝 Transcribe"):
        if 'wav_file' not in st.session_state:
            st.warning("Download and convert audio first.")
            return

        wav_file = st.session_state.wav_file

        if engine == "Groq":
            try:
                with open(wav_file, "rb") as f:
                    transcription = client.audio.transcriptions.create(
                        file=(os.path.basename(wav_file), f.read()),
                        model="whisper-large-v3",
                        language=lang_code,
                        response_format="verbose_json"
                    )
                transcript = transcription.text
            except Exception as e:
                st.error(f"Groq Error: {e}")
                return
        else:
            try:
                with open(wav_file, "rb") as f:
                    files = {
                        'file': f,
                        'language': (None, selected_lang.lower()),
                        'vtt': (None, 'false')
                    }
                    response = requests.post("https://asr.iitm.ac.in/internal/asr/decode", files=files)
                    result = response.json()
                    transcript = result.get("transcript", "No transcript")
            except Exception as e:
                st.error(f"IITM Error: {e}")
                return

        st.text_area("Transcript", transcript, height=300)
        st.markdown(f"""
        <button onclick="navigator.clipboard.writeText(`{transcript}`);alert('Copied!')">
        📋 Copy to Clipboard</button>
        """, unsafe_allow_html=True)

# === TTS ===
def show_tts():
    st.header("🗣️ Text to Speech")

    VOICES = {
        "Malayalam (ml-IN)": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
        "English (en-US)": ["en-US-GuyNeural", "en-US-AriaNeural"],
        "Hindi (hi-IN)": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
    }

    language_label = st.selectbox("Language", list(VOICES.keys()))
    voice = st.selectbox("Voice", VOICES[language_label])
    speed = st.slider("Speed", 0.5, 2.0, 1.23, 0.1)
    filename_input = st.text_input("Optional File Name", "")
    text_input = st.text_area("Text", height=150)

    if st.button("🛠️ Synthesize"):
        if not text_input.strip():
            st.warning("Enter text.")
            return

        rate_value = round((speed - 1) * 100)
        rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"

        IST = timezone(timedelta(hours=5, minutes=30))
        timestamp = datetime.now(IST).strftime("%d_%m_%Y-%H_%M_%S")
        clean_name = re.sub(r'[^\w\-]', '_', filename_input.strip()) or "NFM"
        final_filename = f"{clean_name}_{timestamp}.mp3"
        filepath = OUTPUT_FOLDER / final_filename

        async def generate():
            communicator = edge_tts.Communicate(text_input, voice, rate=rate)
            await communicator.save(str(filepath))

        asyncio.run(generate())
        delete_file_later(filepath)

        try:
            with open(filepath, "rb") as f:
                audio_bytes = f.read()
            st.audio(audio_bytes)
            st.download_button("💾 Download Audio", audio_bytes, file_name=final_filename, mime="audio/mp3")
        except Exception as e:
            st.error(str(e))

# === MAIN ===
def main():
    
    if not st.session_state.authenticated:
        login()
    else:
        st.sidebar.button("🚪 Logout", on_click=logout)
        tabs = st.tabs(["🗣️ TTS", "🎙️ STT"])
        with tabs[0]: show_tts()
        with tabs[1]: show_stt()

if __name__ == "__main__":
    main()
