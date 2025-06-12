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
from urllib.parse import urlparse, parse_qs

# === CONFIGURATION ===
GROQ_API_KEY = "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"
VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"
OUTPUT_FOLDER = Path("static/audio")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
client = Groq(api_key=GROQ_API_KEY)

# === SESSION STATE ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    st.title("🔐 Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    login_btn = st.button("Login")

    # Use session flag to trigger rerun after setting authentication
    if login_btn:
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.logged_in = True  # Flag for rerun trigger
        else:
            st.error("❌ Invalid credentials")

    # Trigger rerun *after* the widget declarations
    if st.session_state.get("logged_in"):
        del st.session_state.logged_in  # Remove trigger after use
        st.experimental_rerun()


def logout():
    st.session_state.authenticated = False
    st.success("Logged out successfully.")
    st.experimental_rerun()

# === UTILITIES ===
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

def clipboard_button(text):
    """ HTML and JS for copy to clipboard """
    st.markdown(f"""
        <textarea id="clipboardContent" style="display:none;">{text}</textarea>
        <button onclick="navigator.clipboard.writeText(document.getElementById('clipboardContent').value)">📋 Copy to Clipboard</button>
    """, unsafe_allow_html=True)

# === STT FUNCTION ===
def show_stt():
    st.header("🎙️ YouTube Speech to Text (STT)")

    # Step 1: YouTube Download
    st.subheader("Step 1: Download YouTube Audio")
    youtube_url = st.text_input("Enter YouTube Video URL:")

    if st.button("🎵 Download & Convert"):
        if not youtube_url:
            st.warning("Please enter a YouTube URL.")
            return

        video_id = extract_youtube_video_id(youtube_url)
        if not video_id:
            st.error("❌ Could not extract video ID.")
            return

        with st.spinner("Downloading and converting..."):
            temp_dir = tempfile.mkdtemp()
            input_file = os.path.join(temp_dir, f"{video_id}.m4a")
            wav_file = os.path.join(temp_dir, f"{video_id}.wav")

            try:
                subprocess.run([
                    "yt-dlp",
                    "-f", "bestaudio[ext=m4a]/bestaudio",
                    "-o", input_file,
                    f"https://www.youtube.com/watch?v={video_id}"
                ], check=True)
                subprocess.run([
                    "ffmpeg", "-y", "-i", input_file, wav_file
                ], check=True)

                st.success("✅ Audio downloaded and converted to WAV.")
                st.audio(wav_file, format="audio/wav")
                st.session_state['wav_file'] = wav_file
                st.download_button("⬇️ Download WAV", open(wav_file, "rb"), f"{video_id}.wav", mime="audio/wav")
            except Exception as e:
                st.error(f"❌ Error: {e}")
                return

    # Step 2: Engine
    st.subheader("Step 2: Choose Engine")
    engine = st.radio("Transcription Engine", ["Groq", "IITM"])

    # Step 3: Language & Transcription
    st.subheader("Step 3: Select Language")
    selected_lang = st.selectbox("Language", list(language_map.keys()))
    lang_code = language_map[selected_lang]

    if st.button("📝 Transcribe Audio"):
        if 'wav_file' not in st.session_state:
            st.warning("Please complete step 1 first.")
            return

        wav_file = st.session_state['wav_file']
        transcript = ""

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
                st.error(f"❌ Groq error: {e}")
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
                st.error(f"❌ IITM error: {e}")
                return

        # Step 4: Show Result
        st.subheader("📄 Transcript Output")
        st.text_area("Transcript", transcript, height=300)
        clipboard_button(transcript)

# === TTS FUNCTION ===
def show_tts():
    st.header("🗣️ Text to Speech (TTS)")

    VOICES = {
        "Malayalam (ml-IN)": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
        "English (en-US)": ["en-US-GuyNeural", "en-US-AriaNeural"],
        "Hindi (hi-IN)": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
    }

    language_label = st.selectbox("Language", list(VOICES.keys()))
    voice = st.selectbox("Voice", VOICES[language_label])
    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=1.23, step=0.1)
    filename_input = st.text_input("Optional File Name (without extension)", "")
    text_input = st.text_area("Text to Synthesize", height=150)

    if st.button("🛠️ Synthesize"):
        if not text_input.strip():
            st.warning("Please enter some text to synthesize.")
            return

        rate_value = round((speed - 1) * 100)
        rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"

        # Filename
        IST = timezone(timedelta(hours=5, minutes=30))
        timestamp = datetime.now(IST).strftime("%d_%m_%Y-%H_%M_%S")
        clean_name = re.sub(r'[^\w\-]', '_', filename_input.strip()) if filename_input else "NFM"
        final_filename = f"{clean_name}_{timestamp}.mp3"
        filepath = OUTPUT_FOLDER / final_filename

        async def generate():
            communicator = edge_tts.Communicate(text_input, voice, rate=rate)
            await communicator.save(str(filepath))

        asyncio.run(generate())
        delete_file_later(filepath)

        # Serve audio
        try:
            with open(filepath, "rb") as audio_file:
                audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/mp3")
            st.download_button("💾 Download Audio", data=audio_bytes, file_name=final_filename, mime="audio/mp3")
        except Exception as e:
            st.error(f"❌ Error loading audio: {e}")

# === MAIN ENTRY ===
def main():
    st.set_page_config(page_title="STT + TTS App", layout="centered")
    if not st.session_state.authenticated:
        login()
    else:
        st.sidebar.button("🚪 Logout", on_click=logout)
        tabs = st.tabs(["🗣️ TTS", "🎙️ STT"])
        with tabs[0]: show_tts()
        with tabs[1]: show_stt()

if __name__ == "__main__":
    main()
