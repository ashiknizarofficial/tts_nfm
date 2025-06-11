import streamlit as st
import os
import re
import tempfile
from urllib.parse import urlparse, parse_qs
import subprocess

# Extract YouTube video ID
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
            st.error("❌ Could not extract video ID.")
        else:
            with st.spinner("Downloading and converting..."):
                temp_dir = tempfile.mkdtemp()
                input_file = os.path.join(temp_dir, f"{video_id}.m4a")
                output_file = os.path.join(temp_dir, f"{video_id}.wav")

                # 1. Download best audio using yt-dlp
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

                # 2. Convert to WAV using ffmpeg
                try:
                    subprocess.run([
                        "ffmpeg", "-y", "-i", input_file, output_file
                    ], check=True)
                except subprocess.CalledProcessError:
                    st.error("❌ ffmpeg conversion failed.")
                    st.stop()

                # 3. Offer download
                with open(output_file, "rb") as f:
                    st.success("✅ Conversion complete!")
                    st.download_button(
                        label="⬇️ Download WAV File",
                        data=f,
                        file_name=f"{video_id}.wav",
                        mime="audio/wav"
                    )
