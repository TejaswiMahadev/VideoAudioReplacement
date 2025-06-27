import streamlit as st
from streamlit_option_menu import option_menu
from moviepy.editor import VideoFileClip, AudioFileClip
from google.cloud import speech
from google.cloud import texttospeech
from pydub import AudioSegment
import librosa
import soundfile as sf
import tempfile
import os
import uuid
import wave
import re
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

# Setup Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "qwiklabs-gcp-02-8c71d534349d-197589c68be5.json"

# Helper function to extract YouTube video ID from URL
def extract_youtube_id(url):
    """Extract YouTube video ID from various YouTube URL formats"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# Function to get YouTube transcript
def get_youtube_transcript(video_id, language='en'):
    """Get transcript from YouTube video using video ID"""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
        transcript_text = ' '.join([item['text'] for item in transcript_list])
        return transcript_text, True
    except Exception as e:
        st.error(f"Error getting YouTube transcript: {str(e)}")
        return None, False

# Function to download YouTube video
def download_youtube_video(url, output_path):
    """Download YouTube video using yt-dlp"""
    try:
        ydl_opts = {
            'format': 'mp4/best',
            'outtmpl': output_path,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        st.error(f"Error downloading YouTube video: {str(e)}")
        return False

# Sidebar navigation
st.sidebar.markdown(
    """
    <style>
    .sidebar .sidebar-content {
        width: 300px;
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.sidebar.markdown(
    """
    <h1 style='font-size: 2em;'>
        <img src="https://img.icons8.com/?size=100&id=szxM3fi4e37N&format=png&color=000000" alt="Yapp Icon" style="vertical-align: middle;"> YAPP!
    </h1>
    """,
    unsafe_allow_html=True
)
st.sidebar.header("NAVIGATION")
with st.sidebar.expander("Menu", expanded=True):
    page = option_menu(
        menu_title="Navigation", 
        options=["Homepage", "YouTube Transcription", "Video Upload Transcription"], 
        icons=["house", "youtube", "person"], 
        menu_icon="cast", 
        default_index=0
    )

if page == "Homepage":
    st.title("Welcome to the Video Upload - Voice Replacement App")
    
    st.write("""
    This app allows you to:
    1. **YouTube Transcription**: Extract transcripts from YouTube videos and replace audio
    2. **Video Upload Transcription**: Upload your own videos for transcription and voice replacement
    
    Both methods will generate new audio using Google Text-to-Speech and create a final video with replaced audio.
    """)
    
elif page == "YouTube Transcription":
    st.title("YouTube Video Transcription and Voice Replacement")
    
    youtube_url = st.text_input("Enter YouTube Video URL:")
    
    if youtube_url:
        video_id = extract_youtube_id(youtube_url)
        
        if video_id:
            st.success(f"Video ID extracted: {video_id}")
            
            # Language selection for transcript
            transcript_language = st.selectbox(
                "Select transcript language:",
                options=['en', 'es', 'fr', 'de', 'it', 'pt', 'hi', 'ja', 'ko', 'zh'],
                index=0,
                help="Select the language of the video's transcript"
            )
            
            if st.button("Process YouTube Video"):
                unique_id = str(uuid.uuid4())
                progress = st.progress(0)
                
                # Get YouTube transcript
                st.write("Fetching YouTube transcript...")
                progress.progress(20)
                transcript, success = get_youtube_transcript(video_id, transcript_language)
                
                if success and transcript:
                    st.write("**Original Transcript:**")
                    st.text_area("Transcript", transcript, height=200)
                    progress.progress(40)
                    
                    # Download YouTube video
                    st.write("Downloading YouTube video...")
                    video_filename = f"youtube_video_{unique_id}.%(ext)s"
                    if download_youtube_video(youtube_url, video_filename):
                        # Find the actual downloaded file
                        video_files = [f for f in os.listdir('.') if f.startswith(f"youtube_video_{unique_id}")]
                        if video_files:
                            actual_video_file = video_files[0]
                            progress.progress(60)
                            
                            # Process the video
                            video_clip = VideoFileClip(actual_video_file)
                            video_duration = video_clip.duration
                            
                            # Generate new audio using Text-to-Speech
                            def generate_speech(text, output_audio_file):
                                client = texttospeech.TextToSpeechClient()
                                input_text = texttospeech.SynthesisInput(text=text)
                                voice = texttospeech.VoiceSelectionParams(
                                    language_code="gu-IN", 
                                    name="gu-IN-Standard-D",
                                )
                                audio_config = texttospeech.AudioConfig(
                                    audio_encoding=texttospeech.AudioEncoding.LINEAR16
                                )
                                response = client.synthesize_speech(
                                    input=input_text, 
                                    voice=voice, 
                                    audio_config=audio_config
                                )
                                
                                with open(output_audio_file, "wb") as out:
                                    out.write(response.audio_content)
                            
                            # Time-stretch audio function
                            def time_stretch_audio(input_audio_file, target_duration):
                                audio_data, sample_rate = librosa.load(input_audio_file, sr=None)
                                current_duration = librosa.get_duration(y=audio_data, sr=sample_rate)
                                stretch_factor = target_duration / current_duration
                                stretched_audio = librosa.effects.time_stretch(audio_data, rate=stretch_factor)
                                output_audio_file = f"stretched_{os.path.basename(input_audio_file)}"
                                sf.write(output_audio_file, stretched_audio, sample_rate)
                                return output_audio_file
                            
                            # Generate speech from transcript
                            st.write("Generating new audio using Text-to-Speech...")
                            progress.progress(70)
                            
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_output:
                                output_audio = temp_audio_output.name
                            
                            generate_speech(transcript, output_audio)
                            
                            # Stretch audio to match video duration
                            st.write("Stretching audio to match video duration...")
                            progress.progress(80)
                            stretched_audio_file = time_stretch_audio(output_audio, video_duration)
                            
                            # Replace audio in video
                            st.write("Replacing audio in video...")
                            new_audio_clip = AudioFileClip(stretched_audio_file)
                            video_with_new_audio = video_clip.set_audio(new_audio_clip)
                            
                            # Save final video
                            final_video_file = f"final_youtube_video_{unique_id}.mp4"
                            video_with_new_audio.write_videofile(final_video_file)
                            progress.progress(100)
                            
                            # Provide download button
                            with open(final_video_file, "rb") as video_file:
                                video_bytes = video_file.read()
                                st.download_button(
                                    label="Download Final Video",
                                    data=video_bytes,
                                    file_name=final_video_file,
                                    mime="video/mp4"
                                )
                            
                            st.success(f"Video processing completed! Final video: {final_video_file}")
                            
                            # Cleanup
                            video_clip.close()
                            new_audio_clip.close()
                        else:
                            st.error("Could not find downloaded video file")
                    else:
                        st.error("Failed to download YouTube video")
                else:
                    st.error("Could not fetch transcript from YouTube video. The video might not have transcripts available or the language might not be supported.")
        else:
            st.error("Invalid YouTube URL. Please enter a valid YouTube video URL.")

elif page == "Video Upload Transcription":
    st.title("Upload Video for Transcription and Voice Replacement")

    uploaded_video = st.file_uploader("Upload your video file", type=["mp4", "mov", "avi"])

    if uploaded_video:
        unique_id = str(uuid.uuid4())
        video_filename = f"uploaded_video_{unique_id}.mp4"
        audio_filename = f"audio_{unique_id}.wav"
        mono_audio_filename = f"mono_audio_{unique_id}.wav"
        progress = st.progress(0)
        
        # Save uploaded video
        with open(video_filename, "wb") as f:
            f.write(uploaded_video.read())

        # Extract audio from video
        st.write("Extracting audio...")
        progress.progress(20)
        video_clip = VideoFileClip(video_filename)
        video_clip.audio.write_audiofile(audio_filename)

        # Convert stereo audio to mono using pydub
        def convert_stereo_to_mono(input_audio, output_audio):
            audio = AudioSegment.from_wav(input_audio)
            mono_audio = audio.set_channels(1)
            mono_audio.export(output_audio, format="wav")

        st.write("Converting audio to mono...")
        progress.progress(30)
        convert_stereo_to_mono(audio_filename, mono_audio_filename)

        def get_audio_sample_rate(audio_file):
            with wave.open(audio_file, 'rb') as wav_file:
                return wav_file.getframerate()

        audio_sample_rate = get_audio_sample_rate(mono_audio_filename)

        # Transcribe large audio file using long_running_recognize
        def transcribe_long_audio(audio_file):
            client = speech.SpeechClient()
            with open(audio_file, "rb") as f:
                audio_data = f.read()

            audio = speech.RecognitionAudio(content=audio_data)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=audio_sample_rate,
                language_code="en-US",
                enable_automatic_punctuation=True,
            )

            operation = client.long_running_recognize(config=config, audio=audio)
            st.write("Transcribing audio... this may take a few minutes.")
            response = operation.result(timeout=600)

            transcription = ""
            for result in response.results:
                transcription += result.alternatives[0].transcript + " "
            return transcription

        st.write("Transcribing audio using long-running recognition...")
        progress.progress(50)
        transcription = transcribe_long_audio(mono_audio_filename)
        st.write(f"**Transcription:** {transcription}")

        # Convert generated transcription to speech using Google Text-to-Speech
        def generate_speech(text, output_audio_file):
            client = texttospeech.TextToSpeechClient()
            input_text = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="gu-IN", name="gu-IN-Standard-D",
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
            response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)

            with open(output_audio_file, "wb") as out:
                out.write(response.audio_content)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_output:
            output_audio = temp_audio_output.name

        st.write("Generating new audio using Text-to-Speech...")
        progress.progress(60)
        generate_speech(transcription, output_audio)

        # Time-stretch the generated audio to match video duration
        def time_stretch_audio(input_audio_file, target_duration):
            audio_data, sample_rate = librosa.load(input_audio_file, sr=None)
            current_duration = librosa.get_duration(y=audio_data, sr=sample_rate)
            stretch_factor = target_duration / current_duration
            stretched_audio = librosa.effects.time_stretch(audio_data, rate=stretch_factor)
            output_audio_file = f"stretched_{os.path.basename(input_audio_file)}"
            sf.write(output_audio_file, stretched_audio, sample_rate)
            return output_audio_file

        video_duration = video_clip.duration
        st.write("Stretching audio to match video duration...")
        progress.progress(80)
        stretched_audio_file = time_stretch_audio(output_audio, video_duration)

        # Replace original audio in the video with the stretched audio
        new_audio_clip = AudioFileClip(stretched_audio_file)
        video_with_stretched_audio = video_clip.set_audio(new_audio_clip)

        # Save the final video
        st.write("Saving final video...")
        final_video_file = f"final_video_{unique_id}.mp4"
        video_with_stretched_audio.write_videofile(final_video_file)
        progress.progress(100)

        with open(final_video_file, "rb") as video_file:
            video_bytes = video_file.read()
            st.download_button(
                label="Download Final Video",
                data=video_bytes,
                file_name=final_video_file,
                mime="video/mp4"
            )

        st.write(f"Final video saved: {final_video_file}")
        
        # Cleanup
        video_clip.close()
        new_audio_clip.close()
