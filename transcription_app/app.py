import os
import pandas as pd
import yt_dlp
import subprocess
import openai
from pydub import AudioSegment
import dotenv

# Set up OpenAI API key from .env file
openai.api_key = os.getenv("OPENAI_API_KEY")

# Paths
EXCEL_FILE = "ulrs_transcription_list.xlsx"  # Change this to your actual file


# Function to compress and split audio
def compress_audio(input_path, output_path):
    """Reduce audio file size using FFmpeg (convert to mono, lower bitrate)."""
    command = [
        "ffmpeg", "-i", input_path,
        "-ac", "1",  # Convert to mono
        "-b:a", "64k",  # Lower bitrate to 64kbps
        "-ar", "16000",  # Reduce sample rate to 16kHz
        output_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def split_audio(input_path, chunk_length_ms=1200000):  # 1200 seconds
    """Split audio into chunks of given length."""
    audio = AudioSegment.from_file(input_path)
    chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]

    output_files = []
    for i, chunk in enumerate(chunks):
        chunk_path = f"{input_path}_part{i}.mp3"
        chunk.export(chunk_path, format="mp3", bitrate="64k")
        output_files.append(chunk_path)

    return output_files


# Function to download audio from URL
def download_audio(url, output_folder):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output_folder}/audio.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Find downloaded audio file
    audio_file = next((f for f in os.listdir(output_folder) if f.endswith(".mp3")), None)
    if audio_file:
        input_path = os.path.join(output_folder, audio_file)
        compressed_path = os.path.join(output_folder, "compressed_audio.mp3")

        # Compress audio
        compress_audio(input_path, compressed_path)

        # Split into smaller chunks
        return split_audio(compressed_path)

    return None


# Function to transcribe audio with Whisper API
def transcribe_audio(file_path):
    with open(file_path, "rb") as audio_file:
        response = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return response.text  # Extract transcription text


# Main function
def process_videos(excel_file):
    df = pd.read_excel(excel_file)

    for index, row in df.iterrows():
        title = str(row["title"]).strip().replace("/", "-")  # Ensure safe folder names
        url = row["url"]

        if not title or not url:
            print(f"Skipping row {index} due to missing data.")
            continue

        folder_name = f"transcriptions/{title}"
        os.makedirs(folder_name, exist_ok=True)

        print(f"Downloading and processing: {title}")
        audio_files = download_audio(url, folder_name)

        if not audio_files:
            print(f"Failed to process audio for {title}")
            continue

        full_transcription = ""

        for audio_file in audio_files:
            print(f"Transcribing chunk: {audio_file}")
            transcript = transcribe_audio(audio_file)
            full_transcription += transcript + "\n"

        # Save the full transcription to a file
        transcript_file = os.path.join(folder_name, "full_transcription.txt")
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(full_transcription)

        print(f"Saved full transcription for {title}")


# Run the script
process_videos(EXCEL_FILE)
