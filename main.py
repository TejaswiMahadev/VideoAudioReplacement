import streamlit as st
from streamlit_option_menu import option_menu
from moviepy.editor import VideoFileClip
import os
import uuid
import tempfile
import requests
import yt_dlp as youtube_dl
import asyncio
from deepgram import Deepgram
import aiofiles

# API Keys
DEEPGRAM_API_KEY = 'YOUR_DEEPGRAM_API_KEY'
AZURE_API_KEY = 'YOUR_AZURE_API_KEY'
AZURE_ENDPOINT = 'YOUR_AZURE_ENDPOINT'
ELEVEN_LABS_API_KEY = 'YOUR_ELEVEN_LABS_API_KEY'

# Initialize Deepgram client
dg_client = Deepgram(DEEPGRAM_API_KEY)

# Sidebar navigation
st.sidebar.header("NAVIGATION")
with st.sidebar.expander("Menu", expanded=True):
    page = option_menu(menu_title="Navigation", options=["Homepage", "Transcription"], icons=["house", "person"], menu_icon="cast", default_index=0)

if page == "Homepage":
    st.title("Welcome to the YouTube Video Voice Replacement App")

elif page == "Transcription":
    st.title("YouTube Video Voice Replacement with AI")

    youtube_url = st.text_input("Enter YouTube Video URL")

    if youtube_url:
        unique_id = str(uuid.uuid4())
        video_filename = f"downloaded_video_{unique_id}.mp4"
        audio_filename = f"audio_{unique_id}.wav"
        mono_audio_filename = f"mono_audio_{unique_id}.wav"
        progress = st.progress(0)

        # Download YouTube video
        st.write("Downloading video from YouTube...")
        ydl_opts = {'format': 'best', 'outtmpl': video_filename}
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        # Extract audio from video
        st.write("Extracting audio...")
        video_clip = VideoFileClip(video_filename)
        video_clip.audio.write_audiofile(audio_filename)

        # Convert stereo audio to mono
        def convert_stereo_to_mono(input_audio, output_audio):
            audio = AudioSegment.from_wav(input_audio)
            mono_audio = audio.set_channels(1)
            mono_audio.export(output_audio, format="wav")

        convert_stereo_to_mono(audio_filename, mono_audio_filename)

        # Transcribe using Deepgram
        async def transcribe_audio_with_deepgram(audio_file):
            async with aiofiles.open(audio_file, 'rb') as afp:
                audio_data = await afp.read()

            source = {'buffer': audio_data, 'mimetype': 'audio/wav'}
            response = await dg_client.transcription.prerecorded(source, {'punctuate': True})
            transcription = response['results']['channels'][0]['alternatives'][0]['transcript']
            return transcription

        st.write("Transcribing audio...")
        transcription = asyncio.run(transcribe_audio_with_deepgram(mono_audio_filename))
        st.write(f"Transcription: {transcription}")

        # Correct transcription using Azure OpenAI GPT-4
        def correct_transcription_with_azure(transcript):
            headers = {"Content-Type": "application/json", "api-key": AZURE_API_KEY}
            data = {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that corrects transcription errors."},
                    {"role": "user", "content": f"Correct the following transcription: {transcript}"}
                ]
            }

            response = requests.post(AZURE_ENDPOINT, headers=headers, json=data)
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

        # Generate speech using Eleven Labs API
        def generate_speech_eleven_labs(text, output_audio_file):
            url = 'https://api.elevenlabs.io/v1/text-to-speech/voice_id'
            headers = {
                'accept': 'audio/mpeg',
                'xi-api-key': ELEVEN_LABS_API_KEY,
                'Content-Type': 'application/json',
            }
            payload = {
                'text': text,
                'voice_settings': {'stability': 0.75, 'similarity_boost': 0.75}
            }
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                with open(output_audio_file, 'wb') as f:
                    f.write(response.content)
                st.success("Generated speech successfully!")
            else:
                st.error(f"Error generating speech: {response.text}")

        output_audio_file = f"generated_audio_{unique_id}.mp3"
        generate_speech_eleven_labs(corrected_transcription, output_audio_file)

        # (Optional) Add functionality to play the generated audio or download it
        with open(output_audio_file, "rb") as audio_file:
            audio_bytes = audio_file.read()
            st.audio(audio_bytes, format='audio/mp3')
