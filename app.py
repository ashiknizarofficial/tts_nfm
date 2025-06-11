import streamlit as st
import re
import os
import tempfile
from urllib.parse import urlparse, parse_qs
from pydub import AudioSegment
import subprocess

# Function to extract video ID
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

# Streamlit UI
st.title("🎵 YouTube to WAV Downloader")

youtube_url = st.text_input("Enter YouTube Video URL:")

if st.button("Download and Convert"):
    if not youtube_url:
        st.warning("Please enter a YouTube URL.")
    else:
        video_id = extract_youtube_video_id(youtube_url)
        if not video_id:
            st.error("❌ Could not extract a valid video ID.")
        else:
            with st.spinner("Downloading and converting audio..."):
                temp_dir = tempfile.mkdtemp()
                audio_path = os.path.join(temp_dir, f"{video_id}.m4a")
                output_wav = os.path.join(temp_dir, f"{video_id}.wav")

                # Use yt-dlp to download the audio
                try:
                    subprocess.run([
                        "yt-dlp",
                        "-f", "bestaudio[ext=m4a]/bestaudio",
                        "-o", audio_path,
                        f"https://www.youtube.com/watch?v={video_id}"
                    ], check=True)
                except subprocess.CalledProcessError:
                    st.error("❌ Failed to download audio with yt-dlp.")
                    st.stop()

                # Convert to WAV
                try:
                    audio = AudioSegment.from_file(audio_path)
                    audio.export(output_wav, format="wav")
                    st.success("✅ Conversion complete!")
                    
                    with open(output_wav, "rb") as f:
                        st.download_button(
                            label="⬇️ Download WAV File",
                            data=f,
                            file_name=f"{video_id}.wav",
                            mime="audio/wav"
                        )
                except Exception as e:
                    st.error(f"❌ Conversion failed: {e}")
