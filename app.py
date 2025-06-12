import streamlit as st
import os
import re
import tempfile
from urllib.parse import urlparse, parse_qs
import subprocess
from groq import Groq
import requests

# ==== CONFIGURE GROQ KEY HERE ====
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

language_map = {
    "Hindi": "hi",
    "English": "en",
    "Malayalam": "ml"
}
selected_lang = st.selectbox("Choose Transcription Language:", list(language_map.keys()))
lang_code = language_map[selected_lang]

# Choose Transcription Model
selected_model = st.selectbox("Choose Transcription Engine:", ["Groq", "IITM ASR"])

# Temporary storage
temp_dir = tempfile.mkdtemp()
input_file = ""
wav_file = ""
video_id = extract_youtube_video_id(youtube_url)

# Button to download and convert
if st.button("Step 1: Download & Convert to WAV"):
    if not youtube_url:
        st.warning("Please enter a YouTube URL.")
    elif not video_id:
        st.error("❌ Could not extract video ID.")
    else:
        with st.spinner("Downloading and converting..."):
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

                st.success("✅ Download and conversion complete.")

            except subprocess.CalledProcessError as e:
                st.error(f"❌ Error: {e}")
                st.stop()

# Button to transcribe
if st.button("Step 2: Transcribe Audio"):
    if not video_id:
        st.warning("Please complete Step 1 first.")
    else:
        with st.spinner("Transcribing..."):
            if selected_model == "Groq":
                try:
                    with open(input_file, "rb") as f:
                        transcription = client.audio.transcriptions.create(
                            file=(f"{video_id}.m4a", f.read()),
                            model="whisper-large-v3",
                            language=lang_code,
                            response_format="verbose_json"
                        )
                    st.subheader("📝 Groq Transcription Output:")
                    st.text_area("Transcript:", value=transcription.text, height=300)
                except Exception as e:
                    st.error(f"❌ Groq transcription failed: {e}")

            elif selected_model == "IITM ASR":
                try:
                    with open(wav_file, "rb") as f:
                        files = {
                            'file': f,
                            'language': (None, selected_lang.lower()),
                            'vtt': (None, 'true'),
                        }
                        response = requests.post('https://asr.iitm.ac.in/internal/asr/decode', files=files)
                        result = response.json()

                    st.subheader("📝 IITM ASR Transcription Output:")
                    st.text_area("Transcript:", value=result.get("transcript", "No transcript found."), height=300)
                except Exception as e:
                    st.error(f"❌ IITM transcription failed: {e}")
