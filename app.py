import streamlit as st
from datetime import datetime, timezone, timedelta
import asyncio
import os
import tempfile
import subprocess
import re
import requests
import uuid
from groq import Groq
import edge_tts
from pathlib import Path

# === CONFIGURATION ===
GROQ_API_KEY = "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"
VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"
OUTPUT_FOLDER = Path("static/audio")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
client = Groq(api_key=GROQ_API_KEY)

# === SESSION MANAGEMENT ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            st.success("Logged in successfully.")
        else:
            st.error("Invalid credentials")

# === NAVIGATION ===
def main():
    page = st.sidebar.radio("📂 Navigate", ["STT from YouTube", "TTS (Text to Speech)", "Logout"])
    if page == "STT from YouTube":
        show_stt()
    elif page == "TTS (Text to Speech)":
        show_tts()
    elif page == "Logout":
        st.session_state.authenticated = False
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

# === STT FUNCTION ===
def show_stt():
    st.title("🎤 Speech to Text (STT) from YouTube")

    youtube_url = st.text_input("Enter YouTube Video URL:")
    model_choice = st.radio("Choose STT Engine:", ["Groq", "IITM-ASR"])
    language_map = {"Hindi": "hi", "English": "en", "Malayalam": "ml"}
    selected_lang = st.selectbox("Choose Transcription Language:", list(language_map.keys()))
    lang_code = language_map[selected_lang]

    if st.button("🔽 Download & Convert to WAV"):
        if not youtube_url:
            st.warning("Enter a YouTube URL")
            return

        video_id = extract_youtube_video_id(youtube_url)
        temp_dir = tempfile.mkdtemp()
        m4a_path = os.path.join(temp_dir, f"{video_id}.m4a")
        wav_path = os.path.join(temp_dir, f"{video_id}.wav")

        # Download
        try:
            subprocess.run(["yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio",
                            "-o", m4a_path, youtube_url], check=True)
            subprocess.run(["ffmpeg", "-y", "-i", m4a_path, wav_path], check=True)
            st.audio(wav_path, format="audio/wav")

            with open(wav_path, "rb") as f:
                st.download_button("⬇️ Download WAV", f, file_name=f"{video_id}.wav", mime="audio/wav")

            st.session_state.wav_file = wav_path
            st.session_state.model_choice = model_choice
            st.session_state.lang_code = lang_code

        except Exception as e:
            st.error(f"Download or conversion failed: {e}")
            return

    if "wav_file" in st.session_state and st.button("🧠 Transcribe"):
        wav_path = st.session_state.wav_file
        lang_code = st.session_state.lang_code

        if st.session_state.model_choice == "Groq":
            with open(wav_path, "rb") as f:
                try:
                    transcription = client.audio.transcriptions.create(
                        file=("audio.wav", f.read()),
                        model="whisper-large-v3",
                        language=lang_code,
                        response_format="verbose_json"
                    )
                    st.text_area("📝 Transcript", transcription.text, height=300)
                    st.code(transcription.text)
                    st.button("📋 Copy Transcript", on_click=st.experimental_set_query_params, kwargs={"copied": transcription.text})
                except Exception as e:
                    st.error(f"Groq STT failed: {e}")

        elif st.session_state.model_choice == "IITM-ASR":
            try:
                with open(wav_path, 'rb') as f:
                    files = {
                        'file': f,
                        'language': (None, lang_code),
                        'vtt': (None, 'true')
                    }
                    response = requests.post('https://asr.iitm.ac.in/internal/asr/decode', files=files)
                    data = response.json()
                    st.text_area("📝 Transcript", data.get("text", ""), height=300)
            except Exception as e:
                st.error(f"IITM STT failed: {e}")

# === TTS FUNCTION ===
def show_tts():
    st.title("🗣️ Text to Speech (TTS)")

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

        # Calculate rate string
        rate_value = round((speed - 1) * 100)
        rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"

        # Timestamp
        IST = timezone(timedelta(hours=5, minutes=30))
        timestamp = datetime.now(IST).strftime("%d_%m_%Y-%H_%M_%S")

        # Build final filename
        clean_name = re.sub(r'[^\w\-]', '_', filename_input.strip()) if filename_input else ""
        final_filename = f"{clean_name}_{timestamp}.mp3"
        filepath = OUTPUT_FOLDER / final_filename

        # Run Edge TTS async
        async def generate():
            communicator = edge_tts.Communicate(text_input, voice, rate=rate)
            await communicator.save(str(filepath))

        asyncio.run(generate())
        delete_file_later(filepath)

        # Safely load audio
        try:
            with open(filepath, "rb") as audio_file:
                audio_bytes = audio_file.read()

            st.audio(audio_bytes, format="audio/mp3")
            st.download_button(
                "💾 Download Audio",
                data=audio_bytes,
                file_name=final_filename,
                mime="audio/mp3"
            )
        except Exception as e:
            st.error(f"❌ Could not load or serve audio file: {e}")


# === ENTRY POINT ===
if __name__ == "__main__":
    st.set_page_config(page_title="STT + TTS App", layout="centered")
    if not st.session_state.authenticated:
        login()
    else:
        main()
