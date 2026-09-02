"""
tts_service.py -- Text-to-Speech Service

Converts the LLM's text reply into an audio file that the user can listen to.
Supports two modes:

1. gTTS (default, local) — Uses Google's free TTS API
   - Pros: Free, supports 50+ languages, no GPU needed
   - Cons: Requires internet, robotic voice, no voice cloning

2. Coqui XTTS (Colab) — Deep learning TTS with voice cloning
   - Pros: Natural voice, can clone the real person's voice
   - Cons: Needs GPU, runs on Colab via ngrok

Usage:
    from backend.services.tts_service import tts_service

    result = tts_service.synthesize("Hello, how are you?", language="en")
    print(result["audio_path"])    # "/outputs/response_20260902_abc123.mp3"
    print(result["duration_ms"])   # 340.5
    print(result["mode"])          # "gtts" or "coqui_xtts"
"""

import os
import time
import uuid
from pathlib import Path
from typing import Optional

import requests
from gtts import gTTS

from backend.config import settings
from backend.utils.logger import logger


# Output directory for generated audio files
OUTPUTS_DIR = Path("outputs")


class TTSService:
    """
    Text-to-Speech service with dual-mode support.

    Mode 1 (gTTS): Free, works immediately, robotic voice
    Mode 2 (Coqui XTTS): Natural voice via Colab, requires setup
    """

    def synthesize(
        self,
        text: str,
        language: str = "en",
        voice_sample_path: Optional[str] = None,
    ) -> dict:
        """
        Convert text to speech audio.

        Args:
            text: The text to speak
            language: Language code (e.g., "en", "hi")
            voice_sample_path: Path to voice sample for cloning (Coqui XTTS only)

        Returns:
            dict with keys:
                - audio_path (str): Relative URL path to the audio file
                - audio_file (str): Absolute filesystem path
                - duration_ms (float): Time taken to synthesize
                - mode (str): "gtts" or "coqui_xtts"
        """
        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text")

        # Clean the text for TTS
        clean_text = self._clean_text(text)

        # Try Coqui XTTS on Colab if configured
        if settings.colab_tts_url and settings.colab_tts_url != "http://localhost:5002":
            try:
                return self._synthesize_coqui(clean_text, language, voice_sample_path)
            except Exception as e:
                logger.warning(f"Coqui XTTS failed, falling back to gTTS: {e}")

        # Default: use gTTS
        return self._synthesize_gtts(clean_text, language)

    def _clean_text(self, text: str) -> str:
        """
        Clean text before sending to TTS.

        Removes artifacts that would sound weird when spoken aloud:
        - AI watermarks like [AI-Generated Response...]
        - Markdown formatting
        - Multiple newlines
        """
        import re

        # Remove watermark brackets
        cleaned = re.sub(r"\[.*?\]", "", text)
        # Remove markdown bold/italic
        cleaned = re.sub(r"[*_]{1,3}", "", cleaned)
        # Remove markdown headers
        cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
        # Collapse whitespace
        cleaned = re.sub(r"\n{2,}", ". ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)

        return cleaned.strip()

    def _generate_filename(self, extension: str = "mp3") -> tuple[str, str]:
        """
        Generate a unique filename for the audio output.

        Returns:
            (relative_url, absolute_path) tuple
        """
        unique_id = uuid.uuid4().hex[:8]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"response_{timestamp}_{unique_id}.{extension}"

        # Ensure outputs directory exists
        OUTPUTS_DIR.mkdir(exist_ok=True)

        absolute_path = str(OUTPUTS_DIR / filename)
        relative_url = f"/outputs/{filename}"

        return relative_url, absolute_path

    def _synthesize_gtts(self, text: str, language: str) -> dict:
        """
        Synthesize speech using Google's free TTS API.

        gTTS supports 50+ languages. The voice is robotic but functional.
        Requires an internet connection.
        """
        start = time.time()

        # Map some language codes that gTTS handles differently
        gtts_lang = language
        if language == "zh":
            gtts_lang = "zh-CN"

        try:
            relative_url, absolute_path = self._generate_filename("mp3")

            tts = gTTS(text=text, lang=gtts_lang, slow=False)
            tts.save(absolute_path)

            duration_ms = (time.time() - start) * 1000

            file_size = os.path.getsize(absolute_path)
            logger.info(
                f"gTTS synthesis complete: lang={language}, "
                f"chars={len(text)}, size={file_size / 1024:.1f}KB, "
                f"time={duration_ms:.0f}ms"
            )

            return {
                "audio_path": relative_url,
                "audio_file": absolute_path,
                "duration_ms": round(duration_ms, 1),
                "mode": "gtts",
            }

        except Exception as e:
            logger.error(f"gTTS failed: {str(e)}")
            raise RuntimeError(f"TTS synthesis failed: {str(e)}") from e

    def _synthesize_coqui(
        self,
        text: str,
        language: str,
        voice_sample_path: Optional[str] = None,
    ) -> dict:
        """
        Synthesize speech using Coqui XTTS on Google Colab.

        Sends a POST request to the Colab-hosted TTS server.
        Supports voice cloning if a voice sample is provided.
        """
        start = time.time()
        url = f"{settings.colab_tts_url.rstrip('/')}/api/tts"

        payload = {
            "text": text,
            "language": language,
        }

        # If a voice sample is available, send it for cloning
        files = None
        if voice_sample_path and os.path.exists(voice_sample_path):
            files = {"speaker_wav": open(voice_sample_path, "rb")}
            logger.info(f"Using voice sample for cloning: {voice_sample_path}")

        try:
            response = requests.post(url, data=payload, files=files, timeout=60)

            if response.status_code != 200:
                raise RuntimeError(f"Coqui XTTS returned {response.status_code}")

            # Save the returned audio
            relative_url, absolute_path = self._generate_filename("wav")
            with open(absolute_path, "wb") as f:
                f.write(response.content)

            duration_ms = (time.time() - start) * 1000

            logger.info(
                f"Coqui XTTS synthesis complete: lang={language}, "
                f"time={duration_ms:.0f}ms, cloning={'yes' if voice_sample_path else 'no'}"
            )

            return {
                "audio_path": relative_url,
                "audio_file": absolute_path,
                "duration_ms": round(duration_ms, 1),
                "mode": "coqui_xtts",
            }

        except requests.Timeout:
            raise RuntimeError("Coqui XTTS timed out after 60s")
        finally:
            if files:
                files["speaker_wav"].close()


# Global singleton
tts_service = TTSService()
