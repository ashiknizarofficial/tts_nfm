import streamlit as st
import os
import re
import tempfile
from urllib.parse import urlparse, parse_qs
import subprocess
from groq import Groq
import requests
import streamlit.components.v1 as components

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

# ==== STATE INIT ====
if "wav_file_path" not in st.session_state:
    st.session_state.wav_file_path = None
if "input_file_path" not in st.session_state:
    st.session_state.input_file_path = None
if "video_id" not in st.session_state:
    st.session_state.video_id = None
if "transcript_text" not in st.session_state:
    st.session_state.transcript_text = ""

# ==== UI ====
st.markdown("<h1 style='text-align: center;'>🎵 YouTube to Text Transcriber</h1>", unsafe_allow_html=True)

with st.expander("📌 Instructions", expanded=False):
    st.markdown("""
    1. Paste a YouTube video URL.
    2. Click **Step 1** to download and convert to WAV.
    3. Choose model and language.
    4. Click **Transcribe**.
    5. Copy or download the result!
    """)

st.markdown("---")

# ==== STEP 1: Download & Convert ====
st.subheader("🛠️ Step 1: Download & Convert to WAV")
youtube_url = st.text_input("Enter YouTube Video URL:")

col1, col2 = st.columns([1, 4])
with col1:
    download_clicked = st.button("🎬 Convert")

if download_clicked:
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

                # Save state
                st.session_state.wav_file_path = wav_file
                st.session_state.input_file_path = input_file
                st.session_state.video_id = video_id
                st.success("✅ Audio downloaded and converted.")

            except subprocess.CalledProcessError as e:
                st.error(f"❌ Conversion error: {e}")
                st.stop()

# ==== STEP 2: Transcribe ====
if st.session_state.wav_file_path:
    st.markdown("---")
    st.subheader("🔤 Step 2: Transcribe Audio")

    col1, col2 = st.columns(2)

    language_map = {
        "Hindi": "hi",
        "English": "en",
        "Malayalam": "ml"
    }

    with col1:
        selected_lang = st.selectbox("🗣️ Choose Language:", list(language_map.keys()))
    with col2:
        selected_model = st.selectbox("🤖 Choose Model:", ["Groq", "IITM ASR"])

    lang_code = language_map[selected_lang]

    if st.button("📝 Transcribe"):
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
                        st.session_state.transcript_text = transcription.text

                elif selected_model == "IITM ASR":
                    with open(st.session_state.wav_file_path, "rb") as f:
                        files = {
                            'file': f,
                            'language': (None, selected_lang.lower()),
                            'vtt': (None, 'false'),
                        }
                        response = requests.post('https://asr.iitm.ac.in/internal/asr/decode', files=files)
                        result = response.json()
                        st.session_state.transcript_text = result.get("transcript", "No transcript found.")

                st.success("✅ Transcription complete!")

            except Exception as e:
                st.error(f"❌ Transcription failed: {e}")

# ==== TRANSCRIPT DISPLAY ====
if st.session_state.transcript_text:
    st.markdown("---")
    st.subheader("📄 Transcription Result")

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
