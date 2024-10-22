import yt_dlp
import uuid
import asyncio
import os
import moviepy.editor as mp
from deepgram import Deepgram
import streamlit as st
from elevenlabs import ElevenLabs, Voice, VoiceSettings

# Deepgram and ElevenLabs API keys
DEEPGRAM_API_KEY = 'YOUR_DEEPGRAM_API_KEY'  # Replace with your actual Deepgram API key
ELEVENLABS_API_KEY = 'YOUR_ELEVENLABS_API_KEY'  # Replace with your actual Eleven Labs API key

# Asynchronous function to transcribe audio using Deepgram
async def transcribe_audio_deepgram(audio_file, deepgram_api_key):
    deepgram = Deepgram(deepgram_api_key)

    with open(audio_file, 'rb') as audio:
        source = {'buffer': audio, 'mimetype': 'audio/mp3'}
        response = await deepgram.transcription.prerecorded(source, {'punctuate': True})
        transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
    
    return transcript

# Function to convert text to audio using Eleven Labs
def convert_text_to_audio_elevenlabs(transcript, output_audio='output_audio.mp3'):
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    voice = Voice(
        voice_id="YOUR_VOICE_ID",  # Replace with your voice ID
        settings=VoiceSettings(
            stability=0,
            similarity_boost=0.75
        )
    )

    audio_generator = client.generate(
        text=transcript,
        voice=voice
    )

    audio_bytes = b"".join(audio_generator)
    with open(output_audio, 'wb') as f:
        f.write(audio_bytes)

    return output_audio

# Function to replace audio in a video
def replace_audio_in_video(video_file, audio_file, output_video='output_video.mp4'):
    video_clip = mp.VideoFileClip(video_file)
    audio_clip = mp.AudioFileClip(audio_file)

    # Set the new audio for the video
    video_clip = video_clip.set_audio(audio_clip)
    video_clip.write_videofile(output_video, codec='libx264', audio_codec='aac')

    return output_video

# Streamlit UI
def main():
    st.title("Video Upload - Audio Transcription and Replacement")

    video_file = st.file_uploader("Upload Video File", type=["mp4", "mov", "avi"])

    if st.button("Process"):
        if video_file:
            with st.spinner("Saving uploaded video..."):
                # Save the uploaded video to a temporary file
                video_filename = f"uploaded_video_{uuid.uuid4()}.mp4"
                with open(video_filename, "wb") as f:
                    f.write(video_file.read())

            with st.spinner("Extracting audio from video..."):
                try:
                    # Extract audio from the uploaded video
                    video_clip = mp.VideoFileClip(video_filename)
                    audio_filename = f"extracted_audio_{uuid.uuid4()}.mp3"
                    video_clip.audio.write_audiofile(audio_filename)
                    st.success("Audio extracted successfully.")
                except Exception as e:
                    st.error(f"Error extracting audio: {e}")
                    return

            with st.spinner("Transcribing audio..."):
                try:
                    # Transcribe the extracted audio using Deepgram
                    transcript = asyncio.run(transcribe_audio_deepgram(audio_filename, DEEPGRAM_API_KEY))
                    st.success("Transcription complete.")
                    st.text_area("Transcript", transcript, height=200)
                except Exception as e:
                    st.error(f"Error during transcription: {e}")
                    return

            with st.spinner("Converting transcript to speech..."):
                try:
                    # Convert the transcript back to speech using ElevenLabs
                    output_audio_path = convert_text_to_audio_elevenlabs(transcript)
                    st.success("Text-to-speech conversion complete.")

                    st.audio(output_audio_path)

                    with open(output_audio_path, 'rb') as f:
                        st.download_button(label="Download Generated Audio", data=f, file_name=output_audio_path, mime='audio/mp3')
                except Exception as e:
                    st.error(f"Error during text-to-speech conversion: {e}")
                    return

            with st.spinner("Replacing audio in video..."):
                try:
                    # Replace the audio in the video with the newly generated audio
                    output_video_path = replace_audio_in_video(video_filename, output_audio_path)
                    st.success("Audio replaced successfully.")

                    st.video(output_video_path)

                    with open(output_video_path, 'rb') as f:
                        st.download_button(label="Download Final Video", data=f, file_name=output_video_path, mime='video/mp4')

                except Exception as e:
                    st.error(f"Error during audio replacement: {e}")
        else:
            st.error("Please upload a video file.")

if __name__ == "__main__":
    main()
