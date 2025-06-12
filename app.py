import streamlit as st
from datetime import datetime, timezone, timedelta
import asyncio
import os
import subprocess
import tempfile
import re
import requests
from pathlib import Path
from groq import Groq
import edge_tts

# ==== CONFIG ====
GROQ_API_KEY = "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"
VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"
OUTPUT_FOLDER = Path("static/audio")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
client = Groq(api_key=GROQ_API_KEY)

# ==== PAGE CONFIG MUST BE FIRST ====
st.set_page_config(page_title="TTS + STT App", layout="centered")

# ==== SESSION INITIALIZATION ====
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ==== LOGIN ====
def login():
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

    if login_btn:
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            st.experimental_rerun()
        else:
            st.error("❌ Invalid credentials")

# ==== LOGOUT ====
def logout():
    st.session_state.authenticated = False
    st.experimental_rerun()

# ==== TRANSCRIPTION ====
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
        r'v=([^&]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def show_stt():
    st.subheader("🎙️ YouTube STT")

    st.markdown("**Step 1: Download YouTube audio & convert to WAV**")
    youtube_url = st.text_input("YouTube URL")
    if st.button("Download & Convert"):
        video_id = extract_youtube_video_id(youtube_url)
        if not video_id:
            st.error("❌ Invalid YouTube URL")
            return

        with st.spinner("Downloading..."):
            temp_dir = tempfile.mkdtemp()
            input_file = os.path.join(temp_dir, f"{video_id}.m4a")
            wav_file = os.path.join(temp_dir, f"{video_id}.wav")

            try:
                subprocess.run([
                    "yt-dlp", "-f", "bestaudio[ext=m4a]", "-o", input_file,
                    f"https://www.youtube.com/watch?v={video_id}"
                ], check=True)

                subprocess.run(["ffmpeg", "-y", "-i", input_file, wav_file], check=True)

                st.success("✅ Downloaded & converted")
                st.audio(wav_file, format="audio/wav")
                st.session_state['wav_file'] = wav_file
                st.download_button("⬇ Download WAV", open(wav_file, "rb"), f"{video_id}.wav", mime="audio/wav")

            except Exception as e:
                st.error(f"❌ Error: {e}")
                return

    st.markdown("**Step 2: Choose STT Engine & Language**")
    engine = st.radio("STT Engine", ["Groq", "IITM"])
    selected_lang = st.selectbox("Language", list(language_map.keys()))
    lang_code = language_map[selected_lang]

    if st.button("📝 Transcribe"):
        if "wav_file" not in st.session_state:
            st.warning("Please download audio first.")
            return

        wav_file = st.session_state['wav_file']
        transcript = ""

        if engine == "Groq":
            with open(wav_file, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=(os.path.basename(wav_file), f.read()),
                    model="whisper-large-v3",
                    language=lang_code,
                    response_format="verbose_json"
                )
            transcript = transcription.text

        elif engine == "IITM":
            with open(wav_file, "rb") as f:
                files = {
                    'file': f,
                    'language': (None, selected_lang.lower()),
                    'vtt': (None, 'false'),
                }
                response = requests.post('https://asr.iitm.ac.in/internal/asr/decode', files=files)
                result = response.json()
                transcript = result.get("transcript", "No transcript found.")

        st.subheader("📄 Transcript")
        st.text_area("Transcript", transcript, height=300)
        st.markdown(f"""
        <button onclick="navigator.clipboard.writeText(`{transcript}`)" style="padding: 10px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;">📋 Copy to Clipboard</button>
        """, unsafe_allow_html=True)

# ==== TEXT TO SPEECH ====
def show_tts():
    st.subheader("🗣️ Text to Speech (TTS)")

    VOICES = {
        "Malayalam (ml-IN)": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
        "English (en-US)": ["en-US-GuyNeural", "en-US-AriaNeural"],
        "Hindi (hi-IN)": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
    }

    language_label = st.selectbox("Language", list(VOICES.keys()))
    voice = st.selectbox("Voice", VOICES[language_label])
    speed = st.slider("Speed", 0.5, 2.0, 1.2, 0.1)
    filename_input = st.text_input("Filename (optional)", "")
    text_input = st.text_area("Text", height=150)

    if st.button("🛠️ Synthesize"):
        if not text_input.strip():
            st.warning("Please enter text.")
            return

        rate = f"{'+' if speed >= 1 else ''}{int((speed - 1) * 100)}%"
        IST = timezone(timedelta(hours=5, minutes=30))
        timestamp = datetime.now(IST).strftime("%d_%m_%Y-%H_%M_%S")
        safe_name = re.sub(r'[^\w\-]', '_', filename_input.strip()) or "NFM"
        final_filename = f"{safe_name}_{timestamp}.mp3"
        filepath = OUTPUT_FOLDER / final_filename

        async def generate():
            communicator = edge_tts.Communicate(text_input, voice, rate=rate)
            await communicator.save(str(filepath))

        asyncio.run(generate())

        with open(filepath, "rb") as f:
            audio_bytes = f.read()

        st.audio(audio_bytes, format="audio/mp3")
        st.download_button("💾 Download MP3", data=audio_bytes, file_name=final_filename, mime="audio/mp3")

# ==== MAIN APP ====
def main():
    if not st.session_state.authenticated:
        login()
    else:
        st.sidebar.success(f"👋 Logged in as {VALID_USERNAME}")
        st.sidebar.button("🚪 Logout", on_click=logout)

        tabs = st.tabs(["🗣️ TTS", "🎙️ STT"])
        with tabs[0]: show_tts()
        with tabs[1]: show_stt()

# ==== ENTRY ====
if __name__ == "__main__":
    main()
