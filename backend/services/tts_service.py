"""
tts_service.py -- Text-to-Speech Service

Converts the LLM's text reply into an audio file that the user can listen to.
Supports two modes:

1. Edge TTS (default, local) — Microsoft's Neural TTS engine
   - Pros: Free, natural-sounding neural voices, 300+ voices, 75+ languages
   - Cons: Requires internet connection

2. Coqui XTTS (Colab) — Deep learning TTS with voice cloning
   - Pros: Can clone the real person's voice
   - Cons: Needs GPU, runs on Colab, Python 3.13 incompatible

Fallback: gTTS (Google Translate TTS) — used if Edge TTS fails

Usage:
    from backend.services.tts_service import tts_service

    result = tts_service.synthesize("Hello, how are you?", language="en")
    print(result["audio_path"])    # "/outputs/response_20260902_abc123.mp3"
    print(result["duration_ms"])   # 340.5
    print(result["mode"])          # "edge_tts" or "coqui_xtts" or "gtts"
"""

import os
import re
import time
import uuid
import asyncio
from pathlib import Path
from typing import Optional

import requests
import edge_tts
from gtts import gTTS

from backend.config import settings
from backend.utils.logger import logger


# Output directory for generated audio files
OUTPUTS_DIR = Path("outputs")

# Map language codes to Edge TTS voice names
# These are high-quality neural voices that sound natural
EDGE_VOICE_MAP = {
    "en": "en-US-AriaNeural",         # American English (female, natural)
    "hi": "hi-IN-SwaraNeural",         # Hindi (female)
    "es": "es-ES-ElviraNeural",        # Spanish (female)
    "fr": "fr-FR-DeniseNeural",        # French (female)
    "de": "de-DE-KatjaNeural",         # German (female)
    "ja": "ja-JP-NanamiNeural",        # Japanese (female)
    "ta": "ta-IN-PallaviNeural",       # Tamil (female)
    "te": "te-IN-ShrutiNeural",        # Telugu (female)
    "bn": "bn-IN-TanishaaNeural",      # Bengali (female)
    "ur": "ur-PK-UzmaNeural",          # Urdu (female)
    "zh": "zh-CN-XiaoxiaoNeural",      # Chinese Mandarin (female)
    "ko": "ko-KR-SunHiNeural",         # Korean (female)
    "ar": "ar-SA-ZariyahNeural",       # Arabic (female)
    "pt": "pt-BR-FranciscaNeural",     # Portuguese (female)
    "ru": "ru-RU-SvetlanaNeural",      # Russian (female)
    "it": "it-IT-ElsaNeural",          # Italian (female)
}

# Default voice when language not in map
DEFAULT_VOICE = "en-US-AriaNeural"


class TTSService:
    """
    Text-to-Speech service with Edge TTS neural voices.

    Primary: Edge TTS (natural neural voices, free)
    Fallback: gTTS (robotic but reliable)
    Optional: Coqui XTTS on Colab (voice cloning)
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
                - mode (str): "edge_tts" or "coqui_xtts" or "gtts"
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
                logger.warning(f"Coqui XTTS failed, falling back to Edge TTS: {e}")

        # Primary: Edge TTS (natural neural voices)
        try:
            return self._synthesize_edge(clean_text, language)
        except Exception as e:
            logger.warning(f"Edge TTS failed, falling back to gTTS: {e}")

        # Fallback: gTTS (robotic but reliable)
        return self._synthesize_gtts(clean_text, language)

    def _clean_text(self, text: str) -> str:
        """
        Clean text before sending to TTS.

        Removes artifacts that would sound weird when spoken aloud:
        - AI watermarks like [AI-Generated Response...]
        - Markdown formatting
        - Multiple newlines
        """
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

    def _synthesize_edge(self, text: str, language: str) -> dict:
        """
        Synthesize speech using Microsoft Edge TTS neural voices.

        Uses the edge-tts library which accesses Microsoft's free
        neural TTS service — the same voices used in Edge browser's
        Read Aloud feature. Much more natural than gTTS.
        """
        start = time.time()

        voice = EDGE_VOICE_MAP.get(language, DEFAULT_VOICE)

        try:
            relative_url, absolute_path = self._generate_filename("mp3")

            # edge-tts is async, run it in an event loop
            async def _generate():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(absolute_path)

            # Use existing loop if available, otherwise create new one
            try:
                loop = asyncio.get_running_loop()
                # We're inside an async context (FastAPI), run in executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    loop.run_in_executor(pool, lambda: asyncio.run(_generate()))
                    # Actually, simpler: just use asyncio.run in a thread
                    # But since we might be in async context, let's just use asyncio.run
                    raise RuntimeError("Use sync path")
            except RuntimeError:
                asyncio.run(_generate())

            duration_ms = (time.time() - start) * 1000

            file_size = os.path.getsize(absolute_path)
            logger.info(
                f"Edge TTS synthesis complete: voice={voice}, lang={language}, "
                f"chars={len(text)}, size={file_size / 1024:.1f}KB, "
                f"time={duration_ms:.0f}ms"
            )

            return {
                "audio_path": relative_url,
                "audio_file": absolute_path,
                "duration_ms": round(duration_ms, 1),
                "mode": "edge_tts",
            }

        except Exception as e:
            logger.error(f"Edge TTS failed: {str(e)}")
            raise RuntimeError(f"Edge TTS synthesis failed: {str(e)}") from e

    def _synthesize_gtts(self, text: str, language: str) -> dict:
        """
        Synthesize speech using Google's free TTS API (fallback).

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
                f"gTTS synthesis complete (fallback): lang={language}, "
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
