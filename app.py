import streamlit as st
import os
import tempfile
import subprocess
import re
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
import uuid
from groq import Groq
import edge_tts
import base64
# === CONFIG ===
GROQ_API_KEY = "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"
VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"
SESSION_FILE = ".user_session"
OUTPUT_FOLDER = Path("static/audio")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
client = Groq(api_key=GROQ_API_KEY)

# === INIT ===
st.set_page_config(page_title="STT + TTS", layout="centered")

# === LOGIN UTIL ===
def is_logged_in():
    return st.session_state.get("authenticated", False)

def save_session():
    with open(SESSION_FILE, "w") as f:
        f.write("1")

def load_session():
    if os.path.exists(SESSION_FILE):
        st.session_state.authenticated = True

def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    st.session_state.authenticated = False

# === LOGIN PAGE ===
def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            save_session()
            st.rerun()
        else:
            st.error("❌ Invalid credentials")

def logout():
    clear_session()
    st.rerun()

# === COPY CLIPBOARD (JS) ===
def copy_to_clipboard(text):
    st.markdown(f"""
        <button onclick="navigator.clipboard.writeText(`{text}`); alert('Copied to clipboard!')">
            📋 Copy to Clipboard
        </button>
    """, unsafe_allow_html=True)

# === NAVIGATION ===
def main():
    load_session()
    if not is_logged_in():
        login()
        return

    st.sidebar.button("🚪 Logout", on_click=logout)
    tabs = st.tabs(["🗣️ TTS", "🎙️ STT"])

    with tabs[0]:
        show_tts()

    with tabs[1]:
        show_stt()

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
        r'youtube\.com/v/([^&?/]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return re.search(r"v=([^&]+)", url).group(1) if "v=" in url else None

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
    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=1.23, step=0.01)
    filename_input = st.text_input("Optional File Name", "")
    text_input = st.text_area("Text to Synthesize", height=150)

    if st.button("🛠️ Synthesize"):
        if not text_input.strip():
            st.warning("Please enter text.")
            return

        rate = f"{'+' if speed >= 1 else ''}{int((speed - 1) * 100)}%"
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

        with open(filepath, "rb") as audio_file:
            audio_bytes = audio_file.read()
            audio_base64 = base64.b64encode(audio_bytes).decode()
    
        # Embed autoplay audio
        st.markdown(
            f"""
            <audio controls autoplay>
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                Your browser does not support the audio element.
            </audio>
            """,
            unsafe_allow_html=True
        )
        st.download_button("💾 Download Audio", audio_bytes, file_name=final_filename, mime="audio/mp3")

# === STT ===
def show_stt():
    st.header("🎙️ YouTube Speech to Text")

    st.subheader("Step 1: Download YouTube Audio")
    youtube_url = st.text_input("YouTube Video URL:")

    if st.button("🎵 Download & Convert"):
        if not youtube_url:
            st.warning("Please enter a URL.")
            return

        video_id = extract_youtube_video_id(youtube_url)
        if not video_id:
            st.error("Invalid YouTube URL.")
            return

        with st.spinner("Downloading and converting..."):
            temp_dir = tempfile.mkdtemp()
            input_file = os.path.join(temp_dir, f"{video_id}.m4a")
            wav_file = os.path.join(temp_dir, f"{video_id}.wav")

            try:
                subprocess.run([
                    "yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio",
                    "-o", input_file, f"https://www.youtube.com/watch?v={video_id}"
                ], check=True)
                subprocess.run(["ffmpeg", "-y", "-i", input_file, wav_file], check=True)

                st.success("Downloaded and converted.")
                st.audio(wav_file, format="audio/wav")
                st.session_state['wav_file'] = wav_file
                st.download_button("⬇️ Download WAV", open(wav_file, "rb"), f"{video_id}.wav", mime="audio/wav")
            except Exception as e:
                st.error(f"Error: {e}")
                return

    st.subheader("Step 2: Transcribe Audio")
    engine = st.radio("Engine", ["Groq", "IITM"])
    selected_lang = st.selectbox("Language", list(language_map.keys()))
    lang_code = language_map[selected_lang]

    if st.button("📝 Transcribe Audio"):
        if 'wav_file' not in st.session_state:
            st.warning("Please download audio first.")
            return

        wav_file = st.session_state['wav_file']

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
                st.error(f"Groq error: {e}")
                return

        elif engine == "IITM":
            try:
                with open(wav_file, "rb") as f:
                    files = {
                        'file': f,
                        'language': (None, selected_lang.lower()),
                        'vtt': (None, 'false'),
                    }
                    response = requests.post('https://asr.iitm.ac.in/internal/asr/decode', files=files)
                    result = response.json()
                    transcript = result.get("transcript", "No transcript found.")
            except Exception as e:
                st.error(f"IITM error: {e}")
                return

        st.subheader("📄 Transcript Output")
        st.text_area("Transcript:", value=st.session_state.transcript_text, height=300, key="final_output")
    
        # Clipboard copy HTML
        components.html(f"""
        <button onclick="navigator.clipboard.writeText('{st.session_state.transcript_text.replace("'", "\\'").replace('"', '\\"')}');" style="
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            font-size: 16px;
            margin-top: 10px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        ">📋 Copy to Clipboard</button>
        """, height=70)
            
    

# === ENTRY POINT ===
if __name__ == "__main__":
    main()
