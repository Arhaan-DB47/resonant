"""
llm_service.py -- LLM Service (Ollama + Groq API Client)

This module sends prompts to an LLM and returns the generated reply.
Supports two backends:

1. Ollama (self-hosted or Colab) — POST /api/chat
2. Groq Cloud API (free Llama 3.1) — OpenAI-compatible REST API

The service includes a fallback mode: when no LLM is reachable,
it returns a simple echo response so development can continue.

Usage:
    from backend.services.llm_service import llm_service

    reply = llm_service.generate(
        system_prompt="You are Dr. Sharma...",
        user_message="What is machine learning?",
    )
    print(reply)  # "Machine learning is a subset of AI that..."
"""

import time
from typing import Optional

import requests

from backend.config import settings
from backend.utils.logger import logger


# Groq API endpoint (OpenAI-compatible)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


class LLMService:
    """
    LLM service that communicates with Ollama or Groq.

    Supports three modes (configured via LLM_MODE env var):
        - "groq"   → Always use Groq Cloud API
        - "ollama"  → Always use Ollama (local or Colab)
        - "auto"    → Try Groq first (if API key set), then Ollama, then fallback
    """

    # Default Ollama model
    DEFAULT_MODEL = "llama3.1:8b"

    # Request timeout (seconds)
    TIMEOUT = 120

    # Headers required for ngrok/cloudflare tunnels
    NGROK_HEADERS = {
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "Resonant/1.0",
    }

    def __init__(self):
        self._ollama_available: Optional[bool] = None

    def _get_base_url(self) -> str:
        """Get the Ollama API base URL from config."""
        return settings.colab_llm_url.rstrip("/")

    def is_ollama_available(self) -> bool:
        """Check if the Ollama server is reachable."""
        try:
            url = self._get_base_url()
            response = requests.get(url, timeout=5, headers=self.NGROK_HEADERS)
            self._ollama_available = response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            self._ollama_available = False

        logger.debug(f"Ollama availability: {self._ollama_available} ({self._get_base_url()})")
        return self._ollama_available

    def is_groq_configured(self) -> bool:
        """Check if a Groq API key is set."""
        return bool(settings.groq_api_key)

    # Keep backward compatibility for health check
    def is_available(self) -> bool:
        """Check if any LLM backend is available."""
        if self.is_groq_configured():
            return True
        return self.is_ollama_available()

    def list_models(self) -> list[str]:
        """List available models on the Ollama server."""
        try:
            url = f"{self._get_base_url()}/api/tags"
            response = requests.get(url, timeout=10, headers=self.NGROK_HEADERS)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except (requests.ConnectionError, requests.Timeout):
            pass
        return []

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
    ) -> dict:
        """
        Generate a response from the LLM.

        Routing logic (based on LLM_MODE):
            "groq"   → Groq only, fallback if fails
            "ollama"  → Ollama only, fallback if fails
            "auto"    → Groq (if key set) → Ollama → fallback
        """
        model = model or self.DEFAULT_MODEL
        mode = settings.llm_mode.lower()

        # --- Mode: groq ---
        if mode == "groq":
            if self.is_groq_configured():
                return self._generate_groq(system_prompt, user_message)
            logger.warning("LLM_MODE=groq but GROQ_API_KEY is not set. Using fallback.")
            return self._generate_fallback(system_prompt, user_message)

        # --- Mode: ollama ---
        if mode == "ollama":
            if self.is_ollama_available():
                return self._generate_ollama(system_prompt, user_message, model)
            logger.warning(f"Ollama not reachable at {self._get_base_url()}. Using fallback.")
            return self._generate_fallback(system_prompt, user_message)

        # --- Mode: auto (default) ---
        # Try Groq first (fast, reliable, no GPU needed)
        if self.is_groq_configured():
            try:
                return self._generate_groq(system_prompt, user_message)
            except Exception as e:
                logger.warning(f"Groq failed, trying Ollama: {e}")

        # Then try Ollama
        if self.is_ollama_available():
            return self._generate_ollama(system_prompt, user_message, model)

        # Fallback
        logger.warning("No LLM backend available. Using fallback mode.")
        return self._generate_fallback(system_prompt, user_message)

    # ========== Groq Cloud API ==========

    def _generate_groq(self, system_prompt: str, user_message: str) -> dict:
        """
        Generate a response using the Groq Cloud API.

        Groq provides free, fast inference for Llama 3.1 8B via an
        OpenAI-compatible REST API. Typical latency: 1-3 seconds.
        """
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
            "max_tokens": 300,
        }

        logger.info(f"Calling Groq: model={GROQ_MODEL}, prompt_len={len(system_prompt)}")

        start = time.time()
        response = requests.post(
            GROQ_API_URL, json=payload, headers=headers, timeout=60
        )
        duration_ms = (time.time() - start) * 1000

        if response.status_code != 200:
            error_msg = response.text[:200]
            logger.error(f"Groq returned {response.status_code}: {error_msg}")
            raise RuntimeError(f"Groq API error: {response.status_code}")

        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()

        if not reply:
            logger.warning("Groq returned empty reply")
            reply = "[The AI generated an empty response. Please try again.]"

        logger.info(
            f"Groq response: {len(reply)} chars, "
            f"model={GROQ_MODEL}, time={duration_ms:.0f}ms"
        )

        return {
            "reply": reply,
            "model": GROQ_MODEL,
            "duration_ms": round(duration_ms, 1),
            "mode": "groq",
        }

    # ========== Ollama (Self-hosted / Colab) ==========

    def _generate_ollama(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
    ) -> dict:
        """Generate a response using the Ollama API."""
        url = f"{self._get_base_url()}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 300,
            },
        }

        logger.info(f"Calling Ollama: model={model}, prompt_len={len(system_prompt)}")

        try:
            start = time.time()
            response = requests.post(url, json=payload, timeout=self.TIMEOUT, headers=self.NGROK_HEADERS)
            duration_ms = (time.time() - start) * 1000

            if response.status_code != 200:
                logger.error(
                    f"Ollama returned {response.status_code}: {response.text[:200]}"
                )
                return self._generate_fallback(system_prompt, user_message)

            data = response.json()
            reply = data.get("message", {}).get("content", "").strip()

            if not reply:
                logger.warning("Ollama returned empty reply")
                reply = "[The AI generated an empty response. Please try again.]"

            logger.info(
                f"Ollama response: {len(reply)} chars, "
                f"model={model}, time={duration_ms:.0f}ms"
            )

            return {
                "reply": reply,
                "model": model,
                "duration_ms": round(duration_ms, 1),
                "mode": "ollama",
            }

        except requests.Timeout:
            logger.error(f"Ollama timed out after {self.TIMEOUT}s")
            return self._generate_fallback(system_prompt, user_message)

        except Exception as e:
            logger.error(f"Ollama call failed: {str(e)}")
            return self._generate_fallback(system_prompt, user_message)

    # ========== Fallback ==========

    def _generate_fallback(
        self,
        system_prompt: str,
        user_message: str,
    ) -> dict:
        """
        Fallback response when no LLM backend is available.
        """
        start = time.time()

        reply = (
            f"[FALLBACK MODE — No LLM connected]\n\n"
            f"I received your message: \"{user_message}\"\n\n"
            f"To get a real AI response, set GROQ_API_KEY in your .env file "
            f"(free at console.groq.com) or start your Colab notebook.\n\n"
            f"[AI-Generated Response — Fallback Mode]"
        )

        duration_ms = (time.time() - start) * 1000

        return {
            "reply": reply,
            "model": "fallback",
            "duration_ms": round(duration_ms, 1),
            "mode": "fallback",
        }


# Global singleton
llm_service = LLMService()
