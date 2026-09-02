"""
stt_service.py -- Speech-to-Text Service (faster-whisper)

This module handles converting audio files into text transcripts.
It uses faster-whisper, which is a CTranslate2 implementation of
OpenAI's Whisper model — runs on CPU, no API key needed.

Usage:
    from backend.services.stt_service import stt_service

    result = stt_service.transcribe("path/to/audio.wav")
    print(result["transcript"])   # "What is machine learning?"
    print(result["language"])     # "en"
    print(result["confidence"])   # 0.947
    print(result["duration_ms"])  # 1340.5
"""

import time
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from backend.config import settings
from backend.utils.logger import logger


class STTService:
    """
    Speech-to-Text service using faster-whisper.

    The model is loaded ONCE when the service is first used (lazy loading),
    then reused for all subsequent transcriptions. This avoids loading
    the model on every request (which would add ~2 seconds of latency).
    """

    def __init__(self):
        self._model: Optional[WhisperModel] = None

    def _load_model(self) -> WhisperModel:
        """
        Load the Whisper model. Called once on first transcription.

        Model sizes and their trade-offs:
            tiny   → 39M params, ~1 GB RAM, fast but less accurate
            base   → 74M params, ~1.5 GB RAM
            small  → 244M params, ~2.5 GB RAM
            medium → 769M params, ~5 GB RAM (good accuracy)
            large-v3 → 1.5B params, ~10 GB RAM (best accuracy, needs GPU)

        We use 'tiny' locally (good enough for dev) and 'medium'/'large'
        on Google Colab for the final demo.
        """
        model_size = settings.whisper_model_size
        logger.info(f"Loading Whisper model: {model_size} (this takes a few seconds on first run)...")

        start = time.time()
        model = WhisperModel(
            model_size,
            device="cpu",           # No GPU available on this machine
            compute_type="int8",    # int8 quantization = faster on CPU, slightly less accurate
        )
        load_time = time.time() - start

        logger.info(f"Whisper model loaded in {load_time:.1f}s")
        return model

    @property
    def model(self) -> WhisperModel:
        """Lazy-load the model on first access."""
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        """
        Transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file (WAV, MP3, WebM, etc.)
            language: Optional language hint (e.g., "en", "hi").
                      If None, Whisper auto-detects the language.

        Returns:
            dict with keys:
                - transcript (str): The transcribed text
                - language (str): Detected language code
                - confidence (float): Language detection confidence (0-1)
                - duration_ms (float): Time taken for transcription

        Raises:
            FileNotFoundError: If audio_path doesn't exist
            RuntimeError: If transcription fails
        """
        # Validate input
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if audio_file.stat().st_size == 0:
            raise ValueError(f"Audio file is empty: {audio_path}")

        logger.info(f"Transcribing: {audio_file.name} ({audio_file.stat().st_size / 1024:.1f} KB)")

        try:
            start = time.time()

            # Run transcription
            # beam_size=5 is the default — higher = more accurate but slower
            transcribe_kwargs = {"beam_size": 5}
            if language:
                transcribe_kwargs["language"] = language

            segments, info = self.model.transcribe(audio_path, **transcribe_kwargs)

            # Collect all segments into a single transcript
            # segments is a generator — we must iterate it to get the text
            transcript_parts = []
            for segment in segments:
                transcript_parts.append(segment.text.strip())

            transcript = " ".join(transcript_parts)
            duration_ms = (time.time() - start) * 1000

            # Handle empty transcription
            if not transcript.strip():
                logger.warning("Whisper returned empty transcript — audio may be silent or too noisy")
                transcript = "[No speech detected]"

            logger.info(
                f"Transcription complete: lang={info.language} "
                f"({info.language_probability:.1%}), "
                f"time={duration_ms:.0f}ms, "
                f"text='{transcript[:80]}...'" if len(transcript) > 80 else
                f"Transcription complete: lang={info.language} "
                f"({info.language_probability:.1%}), "
                f"time={duration_ms:.0f}ms, "
                f"text='{transcript}'"
            )

            return {
                "transcript": transcript,
                "language": info.language,
                "confidence": round(info.language_probability, 3),
                "duration_ms": round(duration_ms, 1),
            }

        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise RuntimeError(f"Transcription failed: {str(e)}") from e


# Global singleton — import this in routes
stt_service = STTService()
