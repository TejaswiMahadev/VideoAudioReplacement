import streamlit as st
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
import requests

# Setup Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path-to-your-json-file"

# Azure OpenAI API setup
azure_api_key = 'API-KEY'
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
page = st.sidebar.radio("Menu", ["Homepage", "Transcription"])

if page == "Homepage":
    st.title("Welcome to the Video Voice Replacement App")
    st.write("""This app allows you to upload a video, extract and transcribe the audio, correct transcription errors using AI, and replace the audio with a newly generated voice using Google Text-to-Speech.""")

elif page == "Transcription":
    st.title("Video Voice Replacement with AI")

    # Upload video file
    video_file = st.file_uploader("Upload a video file", type=["mp4", "mkv", "avi"])
    
    if video_file:
        unique_id = str(uuid.uuid4())
        video_filename = f"uploaded_video_{unique_id}.mp4"
        audio_filename = f"audio_{unique_id}.wav"
        mono_audio_filename = f"mono_audio_{unique_id}.wav"
        progress = st.progress(0)

        # Save uploaded video
        with open(video_filename, "wb") as f:
            f.write(video_file.read())

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

        # Transcribe audio using Google Cloud Speech-to-Text
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

        st.write("Transcribing audio using Google Speech-to-Text...")
        progress.progress(50)
        transcription = transcribe_long_audio(mono_audio_filename)
        st.write(f"Transcription: {transcription}")

        # Correct transcription using Azure OpenAI GPT-4
        def correct_transcription_with_azure(transcript):
            headers = {"Content-Type": "application/json", "api-key": azure_api_key}
            data = {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that corrects transcription errors."},
                    {"role": "user", "content": f"Correct the following transcription: {transcript}"}
                ]
            }

            response = requests.post(azure_endpoint, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                st.error(f"Failed to correct transcription. Error: {response.text}")
                return None

        st.write("Correcting transcription with Azure OpenAI GPT-4...")
        progress.progress(60)
        corrected_transcription = correct_transcription_with_azure(transcription)
        if corrected_transcription:
            st.write(corrected_transcription)
        else:
            st.error("Failed to generate corrected transcription.")

        # Convert corrected transcription to speech using Google Text-to-Speech
        def generate_speech(text, output_audio_file):
            client = texttospeech.TextToSpeechClient()
            input_text = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US", name="en-US-Standard-D",
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
            response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)

            with open(output_audio_file, "wb") as out:
                out.write(response.audio_content)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_output:
            output_audio = temp_audio_output.name

        st.write("Generating new audio using Google Text-to-Speech...")
        progress.progress(70)
        generate_speech(corrected_transcription, output_audio)

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
            st.video(video_bytes)

        st.success("Process completed successfully!")
