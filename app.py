import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
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
import base64

# === MUST BE FIRST STREAMLIT CALL ===
st.set_page_config(page_title="STT + TTS", layout="centered")

# === CONFIG ===
VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)
OUTPUT_FOLDER = Path("static/audio")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# === COOKIES SETUP ===
cookies = EncryptedCookieManager(
    prefix="stt_tts_app_",
    password="pwd"
)

if not cookies.ready():
    st.stop()

# === SESSION STATE ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = cookies.get("auth") == "1"

# === LOGIN FUNCTION ===
def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            cookies["auth"] = "1"
            st.experimental_rerun()
        else:
            st.error("❌ Invalid credentials")

# === LOGOUT FUNCTION ===
def logout():
    st.session_state.authenticated = False
    cookies.set("auth", "0")
    st.success("🔒 Logged out.")
    st.experimental_rerun()

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

def extract_youtube_video_id(url):
    patterns = [r'youtu\.be/([^&?/]+)', r'youtube\.com/embed/([^&?/]+)', r'youtube\.com/v/([^&?/]+)']
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return re.search(r"v=([^&]+)", url).group(1) if "v=" in url else None

language_map = {"Hindi": "hi", "English": "en", "Malayalam": "ml"}

# === TTS FUNCTION ===
def show_tts():
    st.header("🗣️ Text to Speech (TTS)")

    VOICES = {
        "Malayalam (ml-IN)": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
        "English (en-US)": ["en-US-GuyNeural", "en-US-AriaNeural"],
        "Hindi (hi-IN)": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
    }

    lang_label = st.selectbox("Language", list(VOICES.keys()))
    voice = st.selectbox("Voice", VOICES[lang_label])
    speed = st.slider("Speed", 0.5, 2.0, 1.0, 0.1)
    text = st.text_area("Text to Synthesize", height=150)
    filename_input = st.text_input("Optional Filename (without extension)", "")

    if st.button("🛠️ Synthesize"):
        if not text.strip():
            st.warning("Enter text to synthesize.")
            return

        rate_value = round((speed - 1) * 100)
        rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"

        IST = timezone(timedelta(hours=5, minutes=30))
        timestamp = datetime.now(IST).strftime("%d_%m_%Y-%H_%M_%S")
        clean_name = re.sub(r"[^\w\-]", "_", filename_input.strip()) or "NFM"
        filename = f"{clean_name}_{timestamp}.mp3"
        filepath = OUTPUT_FOLDER / filename

        async def generate():
            communicator = edge_tts.Communicate(text, voice, rate=rate)
            await communicator.save(str(filepath))

        asyncio.run(generate())
        delete_file_later(filepath)

        with open(filepath, "rb") as f:
            audio_bytes = f.read()

        st.audio(audio_bytes, format="audio/mp3")
        st.download_button("💾 Download Audio", audio_bytes, filename=filename, mime="audio/mp3")

# === STT FUNCTION ===
def show_stt():
    st.header("🎙️ YouTube Speech to Text (STT)")

    # Step 1: Download YouTube & Convert
    st.subheader("Step 1: Download YouTube Audio")
    yt_url = st.text_input("YouTube URL")
    if st.button("🎵 Download & Convert"):
        if not yt_url:
            st.warning("Please enter a YouTube URL.")
            return

        video_id = extract_youtube_video_id(yt_url)
        if not video_id:
            st.error("❌ Invalid YouTube URL.")
            return

        with st.spinner("Processing..."):
            temp_dir = tempfile.mkdtemp()
            input_file = os.path.join(temp_dir, f"{video_id}.m4a")
            wav_file = os.path.join(temp_dir, f"{video_id}.wav")

            try:
                subprocess.run([
                    "yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio", "-o", input_file,
                    f"https://www.youtube.com/watch?v={video_id}"
                ], check=True)
                subprocess.run(["ffmpeg", "-y", "-i", input_file, wav_file], check=True)

                st.success("✅ Audio ready.")
                st.audio(wav_file, format="audio/wav")
                st.download_button("⬇️ Download WAV", open(wav_file, "rb"), f"{video_id}.wav", mime="audio/wav")
                st.session_state["wav_file"] = wav_file

            except Exception as e:
                st.error(f"❌ Error: {e}")
                return

    # Step 2-3: Engine and Transcription
    st.subheader("Step 2: Transcription")
    engine = st.radio("Choose Engine", ["Groq", "IITM"])
    language = st.selectbox("Language", list(language_map.keys()))
    lang_code = language_map[language]

    if st.button("📝 Transcribe"):
        if "wav_file" not in st.session_state:
            st.warning("Download audio first.")
            return

        wav_file = st.session_state["wav_file"]
        transcript = "Not Available"

        try:
            if engine == "Groq":
                with open(wav_file, "rb") as f:
                    transcription = client.audio.transcriptions.create(
                        file=(os.path.basename(wav_file), f.read()),
                        model="whisper-large-v3",
                        language=lang_code,
                        response_format="verbose_json"
                    )
                    transcript = transcription.text
            else:
                with open(wav_file, "rb") as f:
                    files = {
                        'file': f,
                        'language': (None, language.lower()),
                        'vtt': (None, 'false'),
                    }
                    response = requests.post('https://asr.iitm.ac.in/internal/asr/decode', files=files)
                    result = response.json()
                    transcript = result.get("transcript", "No transcript returned.")
        except Exception as e:
            st.error(f"❌ Transcription error: {e}")
            return

        st.subheader("📄 Transcript")
        st.text_area("Transcript", transcript, height=300)

        # Clipboard Button via HTML + JS
        if transcript:
            b64_text = base64.b64encode(transcript.encode()).decode()
            js_code = f"""
                <script>
                function copyText() {{
                    const text = atob("{b64_text}");
                    navigator.clipboard.writeText(text).then(
                        () => alert("📋 Transcript copied to clipboard."),
                        () => alert("❌ Clipboard copy failed.")
                    );
                }}
                </script>
                <button onclick="copyText()">📋 Copy to Clipboard</button>
            """
            st.markdown(js_code, unsafe_allow_html=True)

# === MAIN ===
def main():
    if not st.session_state.authenticated:
        login()
    else:
        st.sidebar.title("Navigation")
        if st.sidebar.button("🚪 Logout"):
            logout()
        tabs = st.tabs(["🗣️ TTS", "🎙️ STT"])
        with tabs[0]: show_tts()
        with tabs[1]: show_stt()

if __name__ == "__main__":
    main()
