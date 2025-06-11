import streamlit as st
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.proxies import WebshareProxyConfig

# === HARD-CODED PROXY CREDENTIALS (replace with yours) ===
PROXY_USERNAME = "ztfiugyj"
PROXY_PASSWORD = "w0cvuxwirpkk"

# === Setup YouTubeTranscriptApi with proxy ===
proxy_config = WebshareProxyConfig(
    proxy_username=PROXY_USERNAME,
    proxy_password=PROXY_PASSWORD
)
ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)

def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_available_languages(video_id):
    try:
        transcript_list = ytt_api.list_transcripts(video_id)
        languages = []
        for transcript in transcript_list:
            languages.append({
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': transcript.is_generated,
                'is_translatable': transcript.is_translatable
            })
        return languages
    except TranscriptsDisabled:
        st.error("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        st.error("No transcripts found for this video.")
    except VideoUnavailable:
        st.error("This video is unavailable or private.")
    except Exception as e:
        st.error(f"Error accessing video: {str(e)}")
        if "no element found" in str(e).lower():
            st.error("This might be due to YouTube access restrictions. Try a different video.")
    return []

def get_transcript(video_id, language_code=None):
    try:
        if language_code:
            transcript = ytt_api.get_transcript(video_id, languages=[language_code])
        else:
            transcript = ytt_api.get_transcript(video_id)
        full_transcript = " ".join([entry['text'] for entry in transcript])
        return full_transcript, None
    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video."
    except NoTranscriptFound:
        return None, "No transcript found for this video in the requested language."
    except VideoUnavailable:
        return None, "Video is unavailable or private."
    except Exception as e:
        error_msg = str(e)
        if "no element found" in error_msg.lower():
            return None, "Unable to access video data. This may be due to YouTube restrictions or the video may not exist."
        return None, f"An error occurred: {error_msg}"

def main():
    st.title("🎥 YouTube Transcript Extractor (with Proxy Support)")
    st.markdown("Extract and view transcripts from YouTube videos, even with access restrictions.")

    url_input = st.text_input(
        "Enter YouTube URL:",
        placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    # Example buttons
    st.markdown("**Try these example videos:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📚 TED Talk"):
            st.session_state.example_url = "https://www.youtube.com/watch?v=UF8uR6Z6KLc"
    with col2:
        if st.button("🎓 Educational"):
            st.session_state.example_url = "https://www.youtube.com/watch?v=kJuJKp0m6J4"
    with col3:
        if st.button("📺 News"):
            st.session_state.example_url = "https://www.youtube.com/watch?v=9bZkp7q19f0"

    if hasattr(st.session_state, 'example_url'):
        url_input = st.session_state.example_url
        st.info(f"Using example: {url_input}")
        if st.button("Clear Example"):
            del st.session_state.example_url
            st.rerun()

    if url_input:
        video_id = extract_video_id(url_input)
        if not video_id:
            st.error("❌ Invalid YouTube URL.")
            return

        st.success(f"✅ Video ID: `{video_id}`")

        with st.spinner("🔍 Checking available transcript languages..."):
            available_languages = get_available_languages(video_id)

        if not available_languages:
            return

        st.subheader("📋 Available Transcript Languages")
        preferred = {
            "English": ["en", "en-US", "en-GB"],
            "Hindi": ["hi", "hi-IN"],
            "Malayalam": ["ml", "ml-IN"]
        }

        available_preferred = {}
        for pref_name, codes in preferred.items():
            for lang in available_languages:
                if lang['language_code'] in codes:
                    available_preferred.setdefault(pref_name, []).append(lang)

        if available_preferred:
            st.markdown("**Quick Language Selection:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                if "English" in available_preferred:
                    if st.button(f"🇬🇧 English ({len(available_preferred['English'])})"):
                        st.session_state.selected_lang_code = available_preferred["English"][0]['language_code']
            with col2:
                if "Hindi" in available_preferred:
                    if st.button(f"🇮🇳 Hindi ({len(available_preferred['Hindi'])})"):
                        st.session_state.selected_lang_code = available_preferred["Hindi"][0]['language_code']
            with col3:
                if "Malayalam" in available_preferred:
                    if st.button(f"🇮🇳 Malayalam ({len(available_preferred['Malayalam'])})"):
                        st.session_state.selected_lang_code = available_preferred["Malayalam"][0]['language_code']

        if hasattr(st.session_state, 'selected_lang_code'):
            if st.button("🔄 Clear Language Selection"):
                del st.session_state.selected_lang_code
                st.rerun()

        language_options = ["Auto-detect (First available)"]
        language_mapping = {"Auto-detect (First available)": None}

        if hasattr(st.session_state, 'selected_lang_code'):
            selected_lang_info = next(
                (lang for lang in available_languages if lang['language_code'] == st.session_state.selected_lang_code),
                None
            )
            if selected_lang_info:
                quick_option = f"✓ {selected_lang_info['language']} ({selected_lang_info['language_code']})"
                if selected_lang_info['is_generated']:
                    quick_option += " - Auto-generated"
                language_options.insert(1, quick_option)
                language_mapping[quick_option] = selected_lang_info['language_code']

        for lang in available_languages:
            label = f"{lang['language']} ({lang['language_code']})"
            if lang['is_generated']:
                label += " - Auto-generated"
            if label not in [opt.replace("✓ ", "") for opt in language_options]:
                language_options.append(label)
                language_mapping[label] = lang['language_code']

        default_index = 1 if hasattr(st.session_state, 'selected_lang_code') else 0
        selected = st.selectbox("Select transcript language:", options=language_options, index=default_index)
        selected_code = language_mapping[selected]

        if st.button("🚀 Get Transcript", type="primary"):
            with st.spinner("📝 Fetching transcript..."):
                transcript_text, error = get_transcript(video_id, selected_code)
            if error:
                st.error(error)
            elif transcript_text:
                st.success("✅ Transcript fetched successfully!")
                st.subheader("📄 Video Transcript")
                st.info(f"**Language:** {'Auto-detected' if not selected_code else selected}")
                st.text_area("Transcript content:", value=transcript_text, height=400)
                st.caption(f"📊 Word count: {len(transcript_text.split()):,} words")
            else:
                st.error("❌ Failed to fetch transcript.")

    st.markdown("---")
    st.subheader("ℹ️ How to use:")
    st.markdown("""
    1. **Paste a YouTube URL**
    2. **Choose transcript language**
    3. **Click Get Transcript**
    4. **Copy from text area**

    💡 Not all videos support transcripts. If you see errors, try another video.
    """)
    st.caption("⚠️ Note: This version uses hardcoded proxy credentials for bypassing YouTube blocks.")

if __name__ == "__main__":
    main()
