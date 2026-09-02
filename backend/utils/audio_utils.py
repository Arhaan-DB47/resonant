"""
audio_utils.py -- Audio File Utilities

Handles:
1. Converting uploaded audio (WebM, MP3, OGG, etc.) to WAV format
   (because faster-whisper works best with WAV)
2. Saving uploaded files to disk
3. Validating audio files
4. Cleaning up temp files

Uses pydub under the hood, which requires ffmpeg to be installed.
"""

import os
import uuid
import tempfile
from pathlib import Path

from pydub import AudioSegment

from backend.config import settings
from backend.utils.logger import logger


# Maximum allowed file size (10 MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Maximum recording duration (5 minutes)
MAX_DURATION_MS = 5 * 60 * 1000

# Supported input formats
SUPPORTED_FORMATS = {".wav", ".mp3", ".webm", ".ogg", ".flac", ".m4a", ".mp4"}


def save_upload(audio_bytes: bytes, original_filename: str) -> str:
    """
    Save uploaded audio bytes to a temp file.

    Args:
        audio_bytes: Raw bytes from the uploaded file
        original_filename: Original filename (used to detect format)

    Returns:
        Path to the saved temp file

    Raises:
        ValueError: If file is too large or format is unsupported
    """
    # Validate file size
    if len(audio_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Audio file too large: {len(audio_bytes) / 1024 / 1024:.1f} MB "
            f"(max: {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB)"
        )

    if len(audio_bytes) == 0:
        raise ValueError("Audio file is empty")

    # Check format
    ext = Path(original_filename).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported audio format: '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    # Save to temp file
    unique_id = uuid.uuid4().hex[:8]
    temp_path = os.path.join(tempfile.gettempdir(), f"resonant_{unique_id}{ext}")

    with open(temp_path, "wb") as f:
        f.write(audio_bytes)

    logger.debug(f"Saved upload: {temp_path} ({len(audio_bytes) / 1024:.1f} KB)")
    return temp_path


def convert_to_wav(input_path: str) -> str:
    """
    Convert any audio file to WAV format (16kHz, mono).

    faster-whisper works with many formats, but WAV at 16kHz mono
    gives the most consistent results. This also normalizes audio
    from different sources (browser mic, phone, etc.).

    Args:
        input_path: Path to the input audio file

    Returns:
        Path to the converted WAV file (in the temp directory)

    Raises:
        RuntimeError: If conversion fails (usually means ffmpeg is missing)
    """
    input_file = Path(input_path)

    # If already a WAV file, check if conversion is still needed
    if input_file.suffix.lower() == ".wav":
        logger.debug("Input is already WAV, skipping conversion")
        return input_path

    try:
        logger.debug(f"Converting {input_file.suffix} to WAV...")

        # Load the audio file (pydub auto-detects format via ffmpeg)
        audio = AudioSegment.from_file(input_path)

        # Validate duration
        if len(audio) > MAX_DURATION_MS:
            raise ValueError(
                f"Audio too long: {len(audio) / 1000:.0f}s "
                f"(max: {MAX_DURATION_MS / 1000:.0f}s)"
            )

        # Convert to 16kHz mono WAV (optimal for Whisper)
        audio = audio.set_frame_rate(16000).set_channels(1)

        # Save as WAV
        unique_id = uuid.uuid4().hex[:8]
        wav_path = os.path.join(tempfile.gettempdir(), f"resonant_{unique_id}.wav")
        audio.export(wav_path, format="wav")

        logger.debug(
            f"Converted: {input_file.name} -> {wav_path} "
            f"(duration: {len(audio) / 1000:.1f}s)"
        )
        return wav_path

    except Exception as e:
        if "ffmpeg" in str(e).lower() or "ffprobe" in str(e).lower():
            raise RuntimeError(
                "ffmpeg is required for audio conversion but was not found. "
                "Install it: https://ffmpeg.org/download.html"
            ) from e
        raise RuntimeError(f"Audio conversion failed: {str(e)}") from e


def cleanup_temp_files(*file_paths: str):
    """
    Delete temporary audio files after processing.

    Called after the pipeline completes to avoid filling up
    the temp directory with audio files.
    """
    for path in file_paths:
        try:
            if path and os.path.exists(path) and "resonant_" in path:
                os.remove(path)
                logger.debug(f"Cleaned up: {path}")
        except OSError as e:
            logger.warning(f"Failed to clean up {path}: {e}")
