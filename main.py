import streamlit as st
from streamlit_option_menu import option_menu
from moviepy.editor import VideoFileClip, AudioFileClip
from google.cloud import speech
from google.cloud import texttospeech
from pydub import AudioSegment, silence
import tempfile
import os
import yt_dlp as youtube_dl
import uuid
import wave
import requests

# Setup Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "c:\\Users\\mahad\\Downloads\\qwiklabs-gcp-02-913bf1ea2269-1b0cb61f2b40.json"

# Azure OpenAI API setup
azure_api_key = '22ec84421ec24230a3638d1b51e3a7dc'
azure_endpoint = 'https://internshala.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-08-01-preview'

# Sidebar navigation
st.sidebar.markdown(
        """
        <style>
        .sidebar .sidebar-content {
            width: 300px;
        }
        </style>
        """,
        unsafe_allow_html=True)
st.sidebar.markdown(
        """
        <h1 style='font-size: 2em;'>
            <img src="https://img.icons8.com/?size=100&id=szxM3fi4e37N&format=png&color=000000" alt="Yapp Icon" style="vertical-align: middle;"> YAPP!
        </h1>
        """,
        unsafe_allow_html=True
    )
st.sidebar.header("NAVIGATION")
with st.sidebar.expander("Menu",expanded=True):
    page = option_menu(menu_title="Navigation",options=["Homepage","Transcription"],icons=["house","person"],menu_icon="cast",default_index=0)

if page == "Homepage":
    st.title("Welcome to the YouTube Video Voice Replacement App")
    
    st.write("""
    This app allows you to download YouTube videos, extract and transcribe the audio, correct transcription errors using AI, and replace the audio with a newly generated voice using Google Text-to-Speech.

    ## Features
    - **Download YouTube Videos**: Quickly download any public YouTube video with just a URL.
    - **Audio Extraction**: Extract high-quality audio from the downloaded videos.
    - **Transcription**: Convert the audio into text using advanced speech recognition technologies.
    - **AI Correction**: Automatically correct transcription errors using AI to improve accuracy and readability.
    - **Text-to-Speech Conversion**: Generate new audio using natural-sounding voices from the corrected text.
    - **Silence Detection**: Analyze the original audio to detect pauses and silence, ensuring a natural flow in the final audio.
    - **Final Video Creation**: Combine the new audio with the original video to produce a polished output.

    ## Benefits
    - **Improved Accessibility**: Make video content accessible to a wider audience through accurate subtitles.
    - **Content Creation**: Perfect for content creators looking to enhance their videos or create new voiceovers.
    - **Language Learning**: A useful tool for language learners to practice listening and speaking skills.

    ## How to Use
    1. Navigate to the **Transcription** page using the sidebar.
    2. Enter the YouTube video URL you want to process.
    3. Follow the prompts to download the video, extract audio, transcribe, and generate new audio.
    4. Finally, download the finished video with the replaced audio!

    Use the sidebar to navigate to the transcription page and start processing your video!
    """)


elif page == "Transcription":
    st.title("YouTube Video Voice Replacement with AI")
    
    # Input YouTube URL
    youtube_url = st.text_input("Enter YouTube Video URL")

    if youtube_url:
        # Generate a unique filename using uuid
        unique_id = str(uuid.uuid4())
        video_filename = f"downloaded_video_{unique_id}.mp4"
        audio_filename = f"audio_{unique_id}.wav"
        mono_audio_filename = f"mono_audio_{unique_id}.wav"

        # Download YouTube video using yt-dlp
        st.write("Downloading video from YouTube...")
        ydl_opts = {
            'format': 'best',
            'outtmpl': video_filename,
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        # Extract audio from video
        st.write("Extracting audio...")
        video_clip = VideoFileClip(video_filename)
        video_clip.audio.write_audiofile(audio_filename)

        # Convert stereo audio to mono using pydub
        def convert_stereo_to_mono(input_audio, output_audio):
            audio = AudioSegment.from_wav(input_audio)
            mono_audio = audio.set_channels(1)  # Convert to mono
            mono_audio.export(output_audio, format="wav")

        st.write("Converting audio to mono...")
        convert_stereo_to_mono(audio_filename, mono_audio_filename)

        # Fix the sample rate mismatch issue by detecting the sample rate
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

            # Use long_running_recognize for large files
            operation = client.long_running_recognize(config=config, audio=audio)
            st.write("Transcribing audio... this may take a few minutes.")

            # Wait for the operation to complete
            response = operation.result(timeout=600)

            # Combine all transcriptions
            transcription = ""
            for result in response.results:
                transcription += result.alternatives[0].transcript + " "

            return transcription
        
        st.write("Transcribing audio using long-running recognition...")
        transcription = transcribe_long_audio(mono_audio_filename)
        st.write(f"Transcription: {transcription}")

        # 4. Correct transcription using Azure OpenAI GPT-4
        def correct_transcription_with_azure(transcript):
            headers = {
                "Content-Type": "application/json",
                "api-key": azure_api_key
            }

            data = {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that corrects transcription errors."},
                    {"role": "user", "content": f"Correct the following transcription by removing grammatical errors and filler words like 'um', 'hmm', etc.: {transcript}"}
                ]
            }

            response = requests.post(azure_endpoint, headers=headers, json=data)

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                st.error(f"Failed to correct transcription. Error: {response.text}")
                return None

        st.write("Correcting transcription with Azure OpenAI GPT-4...")
        corrected_transcription = correct_transcription_with_azure(transcription)
        if corrected_transcription:
            st.write(f"Corrected Transcription: {corrected_transcription}")
        else:
            st.error("Failed to generate corrected transcription.")

        # 5. Convert corrected transcription to speech using Google Text-to-Speech
        def generate_speech(text, output_audio_file):
            client = texttospeech.TextToSpeechClient()
            input_text = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="ko-KR",
                name="ko-KR-Standard-A",
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16
            )

            response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)

            with open(output_audio_file, "wb") as out:
                out.write(response.audio_content)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_output:
            output_audio = temp_audio_output.name

        st.write("Generating new audio using Text-to-Speech...")
        generate_speech(corrected_transcription, output_audio)

        # Detect Silence in the Original Audio
        def detect_silences(audio_file, min_silence_len=500, silence_thresh=-40):
            audio = AudioSegment.from_file(audio_file)
            silence_ranges = silence.detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
            return silence_ranges

        # Insert corresponding pauses in the new audio
        def insert_pauses_in_audio(new_audio_file, silence_ranges, original_audio_file):
            new_audio = AudioSegment.from_file(new_audio_file)
            original_audio = AudioSegment.from_file(original_audio_file)
            adjusted_audio = AudioSegment.empty()  # Empty audio object to build the result
            
            # Loop over detected silences
            last_position = 0
            for silence_start, silence_end in silence_ranges:
                silence_duration = silence_end - silence_start
                # Add the segment of new audio up to the silence point
                adjusted_audio += new_audio[last_position:silence_start]
                # Add the corresponding silence from the original audio
                adjusted_audio += AudioSegment.silent(duration=silence_duration)
                last_position = silence_start
            
            # Append any remaining audio after the last silence
            adjusted_audio += new_audio[last_position:]
            
            return adjusted_audio

        # Detect silences in the original audio
        st.write("Detecting silences in the original audio...")
        silence_ranges = detect_silences(mono_audio_filename)

        # Insert pauses in the new audio
        st.write("Inserting corresponding pauses in the new audio...")
        adjusted_audio = insert_pauses_in_audio(output_audio, silence_ranges, mono_audio_filename)

        # Save the adjusted new audio
        adjusted_audio_file = f"adjusted_audio_{unique_id}.wav"
        adjusted_audio.export(adjusted_audio_file, format="wav")

        # Synchronize new audio with original video duration
        # ... existing code ...

# Synchronize new audio with original video duration
        st.write("Replacing original audio in the video with adjusted audio...")

# Calculate the duration difference
        video_duration = video_clip.duration
        adjusted_audio_duration = len(adjusted_audio) / 1000.0  # Convert from ms to seconds

# Adjust the audio duration to match the video duration
        if adjusted_audio_duration < video_duration:
    # Add silence to the end of the audio
            silence_duration = (video_duration - adjusted_audio_duration) * 1000  # Convert to ms
            adjusted_audio += AudioSegment.silent(duration=silence_duration)
        elif adjusted_audio_duration > video_duration:
    # Trim the audio to match the video duration
            adjusted_audio = adjusted_audio[:int(video_duration * 1000)]  # Convert to ms

# Save the adjusted new audio
        adjusted_audio_file = f"adjusted_audio_{unique_id}.wav"
        adjusted_audio.export(adjusted_audio_file, format="wav")

# Replace original audio in the video with adjusted audio
        new_audio_clip = AudioFileClip(adjusted_audio_file)
        video_with_adjusted_audio = video_clip.set_audio(new_audio_clip)

        video_with_new_audio_filename = f"video_with_new_audio_{unique_id}.mp4"
        video_with_adjusted_audio.write_videofile(video_with_new_audio_filename)

        st.write("Video processing complete. You can download it below:")
        st.download_button("Download Video", video_with_new_audio_filename)

# Clean up temporary files
        os.remove(video_filename)
        os.remove(audio_filename)
        os.remove(mono_audio_filename)
        os.remove(output_audio)
        os.remove(adjusted_audio_file)

