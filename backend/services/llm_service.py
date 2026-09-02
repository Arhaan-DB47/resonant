"""
llm_service.py -- LLM Service (Ollama API Client)

This module sends prompts to an Ollama instance and returns the generated reply.
Ollama can be running:
  - Locally (http://localhost:11434) — if your machine has enough RAM
  - On Google Colab (https://xxxx.ngrok-free.app) — for GPU-powered inference

The service includes a fallback mode: when Ollama is not reachable,
it returns a simple echo response so development can continue without
needing Colab running at all times.

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


class LLMService:
    """
    LLM service that communicates with Ollama's REST API.

    Ollama exposes a simple HTTP API:
        POST /api/chat
        {
            "model": "llama3.1:8b",
            "messages": [
                {"role": "system", "content": "You are..."},
                {"role": "user", "content": "What is ML?"}
            ],
            "stream": false
        }
    """

    # Default model to use — can be overridden per request
    DEFAULT_MODEL = "llama3.1:8b"

    # Request timeout (seconds) — LLMs can be slow on first inference
    TIMEOUT = 120

    def __init__(self):
        self._available: Optional[bool] = None

    def _get_base_url(self) -> str:
        """Get the Ollama API base URL from config."""
        return settings.colab_llm_url.rstrip("/")

    def is_available(self) -> bool:
        """
        Check if the Ollama server is reachable.

        Returns True if we can connect to the API, False otherwise.
        Result is cached to avoid repeated health checks.
        """
        try:
            url = self._get_base_url()
            response = requests.get(url, timeout=5)
            self._available = response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            self._available = False

        logger.debug(f"Ollama availability: {self._available} ({self._get_base_url()})")
        return self._available

    def list_models(self) -> list[str]:
        """List available models on the Ollama server."""
        try:
            url = f"{self._get_base_url()}/api/tags"
            response = requests.get(url, timeout=10)
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

        Args:
            system_prompt: The compiled persona system prompt
            user_message: The user's transcribed question
            model: Ollama model name (default: llama3.1:8b)

        Returns:
            dict with keys:
                - reply (str): The LLM's generated text
                - model (str): Which model was used
                - duration_ms (float): Time taken for generation
                - mode (str): "ollama" or "fallback"
        """
        model = model or self.DEFAULT_MODEL

        # Try Ollama first
        if self.is_available():
            return self._generate_ollama(system_prompt, user_message, model)

        # Fallback when Ollama is not reachable
        logger.warning(
            f"Ollama not reachable at {self._get_base_url()}. "
            f"Using fallback mode. Start your Colab notebook to enable real LLM."
        )
        return self._generate_fallback(system_prompt, user_message)

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
                "temperature": 0.7,    # Balanced creativity vs consistency
                "num_predict": 300,    # Max tokens in the response (~200 words)
            },
        }

        logger.info(f"Calling Ollama: model={model}, prompt_len={len(system_prompt)}")

        try:
            start = time.time()
            response = requests.post(url, json=payload, timeout=self.TIMEOUT)
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

    def _generate_fallback(
        self,
        system_prompt: str,
        user_message: str,
    ) -> dict:
        """
        Fallback response when Ollama is not available.

        This allows development and testing to continue even when
        the Colab notebook isn't running. The response clearly
        indicates it's a fallback so it's obvious in the UI.
        """
        start = time.time()

        reply = (
            f"[FALLBACK MODE — Ollama not connected]\n\n"
            f"I received your message: \"{user_message}\"\n\n"
            f"To get a real AI response, start the Colab notebook and "
            f"update COLAB_LLM_URL in your .env file.\n\n"
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
