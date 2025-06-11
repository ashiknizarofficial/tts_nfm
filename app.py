import streamlit as st
import re
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

def extract_video_id(url):
    """
    Extract YouTube video ID from various YouTube URL formats
    """
    # Regular expression patterns for different YouTube URL formats
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
    """
    Get available transcript languages for a video
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        languages = []
        
        # Get manually created transcripts
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
        return []
    except NoTranscriptFound:
        st.error("No transcripts found for this video.")
        return []
    except VideoUnavailable:
        st.error("This video is unavailable or private.")
        return []
    except Exception as e:
        st.error(f"Error accessing video: {str(e)}")
        if "no element found" in str(e).lower():
            st.error("This might be due to YouTube access restrictions. Try a different video or check if the video ID is correct.")
        return []

def get_transcript(video_id, language_code=None):
    """
    Get transcript for a video in specified language or auto-detect
    """
    try:
        if language_code:
            # Get transcript in specific language
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language_code])
        else:
            # Auto-detect language (get first available transcript)
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Combine all transcript segments into continuous text
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
    st.title("🎥 YouTube Transcript Extractor")
    st.markdown("Extract and view transcripts from YouTube videos with automatic language detection or manual selection.")
    
    # URL input
    url_input = st.text_input(
        "Enter YouTube URL:",
        placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        help="Paste the full YouTube video URL here"
    )
    
    # Example videos section
    st.markdown("**Try these example videos (they usually have transcripts):**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📚 TED Talk Example"):
            st.session_state.example_url = "https://www.youtube.com/watch?v=UF8uR6Z6KLc"
    
    with col2:
        if st.button("🎓 Educational Video"):
            st.session_state.example_url = "https://www.youtube.com/watch?v=kJuJKp0m6J4"
    
    with col3:
        if st.button("📺 News Broadcast"):
            st.session_state.example_url = "https://www.youtube.com/watch?v=9bZkp7q19f0"
    
    # Use example URL if selected
    if hasattr(st.session_state, 'example_url') and st.session_state.example_url:
        url_input = st.session_state.example_url
        st.info(f"Using example: {url_input}")
        # Clear the example after using it
        if st.button("Clear Example"):
            del st.session_state.example_url
            st.rerun()
    
    if url_input:
        # Extract video ID
        video_id = extract_video_id(url_input)
        
        if not video_id:
            st.error("❌ Invalid YouTube URL. Please enter a valid YouTube video URL.")
            return
        
        st.success(f"✅ Video ID extracted: `{video_id}`")
        
        # Get available languages
        with st.spinner("🔍 Checking available transcript languages..."):
            available_languages = get_available_languages(video_id)
        
        if not available_languages:
            st.error("❌ No transcripts available for this video or the video cannot be accessed.")
            return
        
        # Display available languages
        st.subheader("📋 Available Transcript Languages")
        
        # Preferred languages mapping
        preferred_languages = {
            "English": ["en", "en-US", "en-GB", "en-CA", "en-AU"],
            "Hindi": ["hi", "hi-IN"],
            "Malayalam": ["ml", "ml-IN"]
        }
        
        # Check which preferred languages are available
        available_preferred = {}
        for pref_name, codes in preferred_languages.items():
            for lang in available_languages:
                if lang['language_code'] in codes:
                    if pref_name not in available_preferred:
                        available_preferred[pref_name] = []
                    available_preferred[pref_name].append(lang)
        
        # Language preference selection
        if available_preferred:
            st.markdown("**Quick Language Selection:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if "English" in available_preferred:
                    if st.button(f"🇬🇧 English ({len(available_preferred['English'])} available)"):
                        st.session_state.selected_lang_code = available_preferred["English"][0]['language_code']
            
            with col2:
                if "Hindi" in available_preferred:
                    if st.button(f"🇮🇳 Hindi ({len(available_preferred['Hindi'])} available)"):
                        st.session_state.selected_lang_code = available_preferred["Hindi"][0]['language_code']
            
            with col3:
                if "Malayalam" in available_preferred:
                    if st.button(f"🇮🇳 Malayalam ({len(available_preferred['Malayalam'])} available)"):
                        st.session_state.selected_lang_code = available_preferred["Malayalam"][0]['language_code']
        
        # Clear selection button
        if hasattr(st.session_state, 'selected_lang_code'):
            if st.button("🔄 Clear Language Selection"):
                del st.session_state.selected_lang_code
                st.rerun()
        
        # Create language selection options
        language_options = ["Auto-detect (First available)"]
        language_mapping = {"Auto-detect (First available)": None}
        
        # Add quick selection if available
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
            lang_display = f"{lang['language']} ({lang['language_code']})"
            if lang['is_generated']:
                lang_display += " - Auto-generated"
            if lang_display not in [opt.replace("✓ ", "") for opt in language_options]:
                language_options.append(lang_display)
                language_mapping[lang_display] = lang['language_code']
        
        # Language selection dropdown
        default_index = 1 if len(language_options) > 1 and hasattr(st.session_state, 'selected_lang_code') else 0
        selected_language = st.selectbox(
            "Select transcript language:",
            options=language_options,
            index=default_index,
            help="Choose a specific language or use auto-detect to get the first available transcript"
        )
        
        # Fetch transcript button
        if st.button("🚀 Get Transcript", type="primary"):
            selected_code = language_mapping[selected_language]
            
            with st.spinner("📝 Fetching transcript..."):
                transcript_text, error = get_transcript(video_id, selected_code)
            
            if error:
                st.error(f"❌ {error}")
            elif transcript_text:
                st.success("✅ Transcript fetched successfully!")
                
                # Display transcript
                st.subheader("📄 Video Transcript")
                
                # Show transcript info
                if selected_code:
                    selected_lang_info = next(
                        (lang for lang in available_languages if lang['language_code'] == selected_code), 
                        None
                    )
                    if selected_lang_info:
                        info_text = f"**Language:** {selected_lang_info['language']} ({selected_lang_info['language_code']})"
                        if selected_lang_info['is_generated']:
                            info_text += " - Auto-generated"
                        st.info(info_text)
                else:
                    st.info("**Language:** Auto-detected")
                
                # Display transcript in a text area for easy copying
                st.text_area(
                    "Transcript content:",
                    value=transcript_text,
                    height=400,
                    help="You can copy this text using Ctrl+A and Ctrl+C"
                )
                
                # Show word count
                word_count = len(transcript_text.split())
                st.caption(f"📊 Word count: {word_count:,} words")
            else:
                st.error("❌ Failed to fetch transcript. Please try again.")
    
    # Instructions
    st.markdown("---")
    st.subheader("ℹ️ How to use:")
    st.markdown("""
    1. **Paste YouTube URL**: Enter the full YouTube video URL in the input field
    2. **Select Language**: Choose from available transcript languages or use auto-detect
    3. **Get Transcript**: Click the button to fetch and display the transcript
    4. **Copy Text**: Use the text area to easily copy the transcript content
    
    **Supported URL formats:**
    - `https://www.youtube.com/watch?v=VIDEO_ID`
    - `https://youtu.be/VIDEO_ID`
    - `https://www.youtube.com/embed/VIDEO_ID`
    - `https://www.youtube.com/v/VIDEO_ID`
    
    **Try these example videos:**
    - TED Talks (usually have good transcripts)
    - Educational channels like Khan Academy
    - Official music videos with lyrics
    - News broadcasts
    """)
    
    st.markdown("---")
    st.caption("💡 Note: Not all videos have transcripts available. Auto-generated transcripts may contain errors. If you get XML parsing errors, try a different video as this usually indicates YouTube access restrictions.")

if __name__ == "__main__":
    main()
