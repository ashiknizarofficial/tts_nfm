import streamlit as st
import os
import re
import tempfile
from urllib.parse import urlparse, parse_qs
import subprocess
from groq import Groq

# ==== CONFIGURE GROQ KEY HERE ====
GROQ_API_KEY = "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"  # ← Replace with your actual Groq key

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
st.title("🎵 YouTube to WAV + Groq Transcription")

youtube_url = st.text_input("Enter YouTube Video URL:")

language_map = {
    "Hindi": "hi",
    "English": "en",
    "Malayalam": "ml"
}

selected_lang = st.selectbox("Choose Transcription Language:", list(language_map.keys()))
lang_code = language_map[selected_lang]

if st.button("Download, Convert & Transcribe"):
    if not youtube_url:
        st.warning("Please enter a YouTube URL.")
    else:
        video_id = extract_youtube_video_id(youtube_url)
        if not video_id:
            st.error("❌ Could not extract video ID.")
        else:
            with st.spinner("Processing..."):
                temp_dir = tempfile.mkdtemp()
                input_file = os.path.join(temp_dir, f"{video_id}.m4a")
                wav_file = os.path.join(temp_dir, f"{video_id}.wav")

                # Download audio with yt-dlp
                try:
                    subprocess.run([
                        "yt-dlp",
                        "-f", "bestaudio[ext=m4a]/bestaudio",
                        "-o", input_file,
                        f"https://www.youtube.com/watch?v={video_id}"
                    ], check=True)
                except subprocess.CalledProcessError:
                    st.error("❌ yt-dlp failed to download audio.")
                    st.stop()

                # Convert to WAV with ffmpeg
                try:
                    subprocess.run([
                        "ffmpeg", "-y", "-i", input_file, wav_file
                    ], check=True)
                except subprocess.CalledProcessError:
                    st.error("❌ ffmpeg conversion failed.")
                    st.stop()

                # Download option
                with open(wav_file, "rb") as f:
                    st.download_button(
                        label="⬇️ Download WAV File",
                        data=f,
                        file_name=f"{video_id}.wav",
                        mime="audio/wav"
                    )

                # Transcribe with Groq
                try:
                    with open(input_file, "rb") as f:
                        transcription = client.audio.transcriptions.create(
                            file=(f"{video_id}.m4a", f.read()),
                            model="whisper-large-v3",
                            language=lang_code,
                            response_format="verbose_json"
                        )
                    st.subheader("📝 Transcription Output:")
                    st.markdown(
                        f"""
                        <textarea id="transcriptText" rows="15" style="width: 100%; font-family: monospace;">{transcription_text}</textarea>
                        <br>
                        <button onclick="copyTranscript()">📋 Copy to Clipboard</button>
                        <script>
                        function copyTranscript() {{
                            var copyText = document.getElementById("transcriptText");
                            copyText.select();
                            document.execCommand("copy");
                        }}
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    st.error(f"❌ Groq transcription failed: {e}")
