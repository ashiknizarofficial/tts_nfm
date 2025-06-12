import streamlit as st
import os
import re
import tempfile
import subprocess
import asyncio
import edge_tts
import threading
import time
import uuid
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from groq import Groq
from pathlib import Path

# ==== CONFIG ====
GROQ_API_KEY = "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"
VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"
client = Groq(api_key=GROQ_API_KEY)
OUTPUT_FOLDER = Path("static/audio")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# ==== SESSION STATE INIT ====
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "Login"

# ==== UTILITY FUNCTIONS ====
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

def delete_file_later(filepath, delay=300):
    def delete():
        time.sleep(delay)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
    threading.Thread(target=delete, daemon=True).start()

# ==== LOGIN PAGE ====
def show_login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.logged_in = True
            st.session_state.page = "STT"
        else:
            st.error("❌ Invalid credentials")

# ==== STT PAGE ====
def show_tts():
    st.title("🗣️ Text to Speech")

    VOICES = {
        "Malayalam (ml-IN)": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
        "English (en-US)": ["en-US-GuyNeural", "en-US-AriaNeural"],
        "Hindi (hi-IN)": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
    }

    language_label = st.selectbox("Language", list(VOICES.keys()))
    voice = st.selectbox("Voice", VOICES[language_label])
    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=1.0, step=0.1)
    filename_input = st.text_input("Optional File Name", "")
    text_input = st.text_area("Text to Synthesize", height=150)

    if st.button("Synthesize"):
        if not text_input.strip():
            st.warning("Please enter some text.")
        else:
            rate_value = round((speed - 1) * 100)
            rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"

            # Generate timestamped filename with IST
            IST = timezone(timedelta(hours=5, minutes=30))
            timestamp = datetime.now(IST).strftime("%d-%m-%Y_%H-%M-%S")
            filename = f"{filename_input.strip() + '_' if filename_input.strip() else ''}{timestamp}.mp3"
            filepath = OUTPUT_FOLDER / filename

            async def generate():
                communicator = edge_tts.Communicate(text_input, voice, rate=rate)
                await communicator.save(str(filepath))

            asyncio.run(generate())
            delete_file_later(filepath)

            # Read file bytes once
            with open(filepath, "rb") as audio_file:
                audio_bytes = audio_file.read()

            st.audio(audio_bytes, format="audio/mp3")
            st.download_button(
                label="💾 Download Audio",
                data=audio_bytes,
                file_name=filename,
                mime="audio/mp3"
            )

# ==== TTS PAGE ====
def show_tts():
    st.title("🗣️ Text to Speech")

    VOICES = {
        "Malayalam (ml-IN)": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
        "English (en-US)": ["en-US-GuyNeural", "en-US-AriaNeural"],
        "Hindi (hi-IN)": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
    }

    language_label = st.selectbox("Language", list(VOICES.keys()))
    voice = st.selectbox("Voice", VOICES[language_label])
    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=1.23, step=0.1)
    filename_input = st.text_input("Optional File Name", "")
    text_input = st.text_area("Text to Synthesize", height=150)

    if st.button("Synthesize"):
        if not text_input.strip():
            st.warning("Please enter some text.")
        else:
            rate_value = round((speed - 1) * 100)
            rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"

            IST = timezone(timedelta(hours=5, minutes=30))
            timestamp = datetime.now(IST).strftime("%d-%m-%Y_%H-%M-%S")
            filename = f"{filename_input.strip() + '_' if filename_input.strip() else ''}{timestamp}.mp3"
            filepath = OUTPUT_FOLDER / filename

            async def generate():
                communicator = edge_tts.Communicate(text_input, voice, rate=rate)
                await communicator.save(str(filepath))

            asyncio.run(generate())
            delete_file_later(filepath)

            st.audio(str(filepath), format="audio/mp3")
            with open(filepath, "rb") as audio_file:
                st.download_button("💾 Download Audio", audio_file, filename=filename, mime="audio/mp3")

# ==== MAIN NAVIGATION ====
if not st.session_state.logged_in:
    show_login()
else:
    st.sidebar.title("📌 Navigation")
    page = st.sidebar.radio("Go to:", ["STT", "TTS", "Logout"])

    if page == "STT":
        show_stt()
    elif page == "TTS":
        show_tts()
    elif page == "Logout":
        st.session_state.logged_in = False
        st.session_state.page = "Login"
        st.experimental_rerun()
