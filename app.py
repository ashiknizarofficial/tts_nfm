import streamlit as st
from datetime import datetime, timedelta, timezone
import os, re, tempfile, asyncio, threading, subprocess, uuid, requests
from pathlib import Path
from groq import Groq
import edge_tts

# === CONFIG ===
VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

OUTPUT_FOLDER = Path("static/audio")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# === SESSION ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# === UTILS ===
def rerun():
    st.rerun()

def delete_file_later(filepath, delay=300):
    def delayed():
        try:
            time.sleep(delay)
            os.remove(filepath)
        except:
            pass
    threading.Thread(target=delayed, daemon=True).start()

def extract_youtube_video_id(url):
    patterns = [
        r'youtu\.be/([^&?/]+)', r'youtube\.com/embed/([^&?/]+)',
        r'youtube\.com/v/([^&?/]+)', r'v=([^&]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# === LOGIN ===
def login():
    st.title("🔐 Login")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            rerun()
        else:
            st.error("❌ Invalid credentials")

# === LOGOUT ===
def logout():
    st.session_state.authenticated = False
    rerun()

# === TTS ===
def show_tts():
    st.header("🗣️ Text-to-Speech")

    VOICES = {
        "Malayalam (ml-IN)": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
        "English (en-US)": ["en-US-GuyNeural", "en-US-AriaNeural"],
        "Hindi (hi-IN)": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
    }

    lang = st.selectbox("Language", list(VOICES.keys()))
    voice = st.selectbox("Voice", VOICES[lang])
    speed = st.slider("Speed", 0.5, 2.0, 1.23, 0.1)
    filename_input = st.text_input("Optional Filename (without extension)")
    text_input = st.text_area("Text to Synthesize", height=150)

    if st.button("🛠️ Synthesize"):
        if not text_input.strip():
            st.warning("Please enter some text.")
            return

        rate = f"{'+' if speed >= 1 else ''}{round((speed - 1)*100)}%"
        IST = timezone(timedelta(hours=5, minutes=30))
        timestamp = datetime.now(IST).strftime("%d_%m_%Y-%H_%M_%S")
        clean_name = re.sub(r'[^\w\-]', '_', filename_input.strip()) if filename_input else "NFM"
        filename = f"{clean_name}_{timestamp}.mp3"
        filepath = OUTPUT_FOLDER / filename

        async def generate():
            communicator = edge_tts.Communicate(text_input, voice, rate=rate)
            await communicator.save(str(filepath))

        asyncio.run(generate())
        delete_file_later(filepath)

        with open(filepath, "rb") as audio_file:
            audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/mp3")
            st.download_button("💾 Download Audio", data=audio_bytes, file_name=filename, mime="audio/mp3")

# === STT ===
def show_stt():
    st.header("🎙️ YouTube Speech-to-Text")

    language_map = {"Hindi": "hi", "English": "en", "Malayalam": "ml"}

    # Step 1: Download
    st.subheader("Step 1: Download YouTube Audio & Convert to WAV")
    url = st.text_input("YouTube URL")
    if st.button("🎵 Download & Convert"):
        video_id = extract_youtube_video_id(url)
        if not video_id:
            st.error("❌ Invalid YouTube URL.")
            return

        with st.spinner("Downloading..."):
            temp_dir = tempfile.mkdtemp()
            input_file = os.path.join(temp_dir, f"{video_id}.m4a")
            wav_file = os.path.join(temp_dir, f"{video_id}.wav")
            subprocess.run(["yt-dlp", "-f", "bestaudio[ext=m4a]", "-o", input_file, url], check=True)
            subprocess.run(["ffmpeg", "-y", "-i", input_file, wav_file], check=True)
            st.session_state.wav_file = wav_file
            st.audio(wav_file)
            st.download_button("⬇️ Download WAV", open(wav_file, "rb"), f"{video_id}.wav", mime="audio/wav")

    # Step 2: Engine & Language
    st.subheader("Step 2: Transcribe")
    engine = st.radio("Choose Engine", ["Groq", "IITM"])
    lang_label = st.selectbox("Language", list(language_map.keys()))
    lang_code = language_map[lang_label]

    if st.button("📝 Transcribe"):
        if 'wav_file' not in st.session_state:
            st.warning("Please complete Step 1.")
            return

        wav_file = st.session_state.wav_file

        if engine == "Groq":
            with open(wav_file, "rb") as f:
                response = client.audio.transcriptions.create(
                    file=(os.path.basename(wav_file), f.read()),
                    model="whisper-large-v3",
                    language=lang_code,
                    response_format="verbose_json"
                )
            transcript = response.text

        elif engine == "IITM":
            with open(wav_file, "rb") as f:
                files = {
                    'file': f,
                    'language': (None, lang_label.lower()),
                    'vtt': (None, 'false'),
                }
                r = requests.post("https://asr.iitm.ac.in/internal/asr/decode", files=files)
                transcript = r.json().get("transcript", "No transcript.")

        st.text_area("📄 Transcript", transcript, height=300)
        st.markdown(f"""
        <button onclick="navigator.clipboard.writeText(`{transcript}`); alert('Copied to clipboard!')">
        📋 Copy to Clipboard</button>
        """, unsafe_allow_html=True)

# === MAIN ===
def main():
    st.set_page_config("STT + TTS App", layout="centered", page_icon="🎤")

    if not st.session_state.authenticated:
        login()
    else:
        st.sidebar.button("🚪 Logout", on_click=logout)
        tabs = st.tabs(["🗣️ TTS", "🎙️ STT"])
        with tabs[0]: show_tts()
        with tabs[1]: show_stt()

if __name__ == "__main__":
    main()
