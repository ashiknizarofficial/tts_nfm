from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import edge_tts
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import os
import threading
import time

app = Flask(__name__)
app.secret_key = "super_secret_key_change_this"

VALID_USERNAME = "ashik"
VALID_PASSWORD = "pwd"

VOICES = {
    "ml-IN": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
    "en-US": ["en-US-GuyNeural", "en-US-AriaNeural"],
    "hi-IN": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
}

OUTPUT_FOLDER = "static/audio"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def delete_file_later(filepath, delay=300):
    """Delete file after delay seconds (default 5 mins)"""
    def delete_later():
        time.sleep(delay)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
    threading.Thread(target=delete_later, daemon=True).start()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session['user'] = username
            return redirect(url_for('index'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/tts')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', voices=VOICES)

@app.route('/synthesize', methods=['POST'])
def synthesize():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    text = request.form['text']
    language = request.form['language']
    voice = request.form['voice']
    speed = request.form['speed']
    custom_name = request.form['filename'].strip()

    rate_value = round((float(speed) - 1) * 100)
    rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"

    IST = timezone(timedelta(hours=5, minutes=30))
    timestamp = datetime.now(IST).strftime("%d-%m-%Y_%H-%M-%S")
    filename = f"{custom_name + '_' if custom_name else ''}{timestamp}.mp3"
    filepath = os.path.join(OUTPUT_FOLDER, filename)

    async def generate_tts():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(filepath)

    asyncio.run(generate_tts())

    # Schedule file deletion in 5 mins
    delete_file_later(filepath, delay=300)

    # Return path for client to play/download
    return jsonify({"audio_url": url_for('static', filename=f"audio/{filename}")})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
