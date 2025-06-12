import streamlit as st
import os
import re
import tempfile
from urllib.parse import urlparse, parse_qs
import subprocess
from groq import Groq
import requests

# ==== CONFIGURE GROQ KEY ====
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ==== VIDEO ID PARSER ====
def extract_youtube_video_id(url):
    patterns = [
        r'youtu\.be/([^&?/]+)',
        r'youtube\.com/embed/([^&?/]+)',
        r'youtube\.com/v/([^&?/]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    parsed_url = urlparse(url)
    if parsed_url.hostname in ['www.youtube.com', 'youtube.com']:
        query = parse_qs(parsed_url.query)
        if 'v' in query:
            return query['v'][0]
    return None

# ==== STREAMLIT UI ====
st.title("🎵 YouTube to WAV + Transcription")

youtube_url = st.text_input("Enter YouTube Video URL:")

if "wav_file_path" not in st.session_state:
    st.session_state.wav_file_path = None
if "input_file_path" not in st.session_state:
    st.session_state.input_file_path = None
if "video_id" not in st.session_state:
    st.session_state.video_id = None

# === Step 1: Download and Convert ===
if st.button("Step 1: Download & Convert to WAV"):
    video_id = extract_youtube_video_id(youtube_url)
    if not youtube_url or not video_id:
        st.error("❌ Invalid YouTube URL.")
    else:
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

                with open(wav_file, "rb") as f:
                    st.download_button(
                        label="⬇️ Download WAV File",
                        data=f,
                        file_name=f"{video_id}.wav",
                        mime="audio/wav"
                    )

                st.success("✅ Audio downloaded and converted.")

                # Save paths in session
                st.session_state.wav_file_path = wav_file
                st.session_state.input_file_path = input_file
                st.session_state.video_id = video_id

            except subprocess.CalledProcessError as e:
                st.error(f"❌ Download/conversion error: {e}")
                st.stop()

# === Step 2: Transcription ===
if st.session_state.wav_file_path:
    st.markdown("---")
    st.header("Step 2: Transcribe")

    language_map = {
        "Hindi": "hi",
        "English": "en",
        "Malayalam": "ml"
    }
    selected_lang = st.selectbox("Choose Language:", list(language_map.keys()))
    lang_code = language_map[selected_lang]
    selected_model = st.selectbox("Choose Transcription Engine:", ["Groq", "IITM ASR"])

    if st.button("Transcribe Audio"):
        with st.spinner("Transcribing..."):
            try:
                if selected_model == "Groq":
                    with open(st.session_state.input_file_path, "rb") as f:
                        transcription = client.audio.transcriptions.create(
                            file=(f"{st.session_state.video_id}.m4a", f.read()),
                            model="whisper-large-v3",
                            language=lang_code,
                            response_format="verbose_json"
                        )
                    st.subheader("📝 Groq Transcription:")
                    st.text_area("Transcript:", value=transcription.text, height=300)

                elif selected_model == "IITM ASR":
                    with open(st.session_state.wav_file_path, "rb") as f:
                        files = {
                            'file': f,
                            'language': (None, selected_lang.lower()),
                            'vtt': (None, 'false'),
                        }
                        response = requests.post('https://asr.iitm.ac.in/internal/asr/decode', files=files)
                        result = response.json()
                    st.subheader("📝 IITM ASR Transcription:")
                    st.text_area("Transcript:", value=result.get("transcript", "No transcript found."), height=300)

            except Exception as e:
                st.error(f"❌ Transcription failed: {e}")
