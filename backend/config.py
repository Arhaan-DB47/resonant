"""
config.py -- Centralized Configuration using pydantic-settings

This module loads ALL configuration from the .env file into a single
Settings object. Any file in the project can do:

    from backend.config import settings
    print(settings.database_url)

Why pydantic-settings instead of os.environ?
- os.environ.get("KEY") returns None silently if missing.
  You won't know until the API call fails mid-demo.
- pydantic-settings validates on startup -- if a required key
  is missing, the server refuses to start and tells you exactly
  which key is missing.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    All configuration for the Resonant application.
    Values are loaded from the .env file automatically.
    """

    # === Database ===
    database_url: str = Field(
        default="",
        description="PostgreSQL connection string (set in .env)",
    )

    # === Colab-Hosted AI Services ===
    # These URLs point to your Google Colab notebooks running Ollama / TTS
    # When Colab is not running, the services gracefully degrade
    colab_llm_url: str = Field(
        default="http://localhost:11434",
        description="URL of the Ollama LLM API (local or Colab via ngrok)",
    )
    colab_tts_url: str = Field(
        default="http://localhost:5002",
        description="URL of the Coqui XTTS API (Colab via ngrok)",
    )

    # === Local STT Model ===
    whisper_model_size: str = Field(
        default="tiny",
        description="faster-whisper model size: tiny, base, small, medium, large-v3",
    )

    # === Optional: ElevenLabs (paid voice cloning) ===
    elevenlabs_api_key: str = Field(
        default="",
        description="ElevenLabs API key for premium voice cloning",
    )
    elevenlabs_voice_id: str = Field(
        default="",
        description="ElevenLabs voice ID for the cloned voice",
    )

    # === App Settings ===
    default_language: str = Field(
        default="en",
        description="Default target language (ISO 639-1 code)",
    )
    log_level: str = Field(
        default="DEBUG",
        description="Logging level: DEBUG, INFO, WARNING, ERROR",
    )
    output_dir: str = Field(
        default="outputs",
        description="Directory to save generated audio files",
    )

    # === Computed Properties ===

    @property
    def is_elevenlabs_configured(self) -> bool:
        """Check if ElevenLabs is available for premium voice cloning."""
        return bool(self.elevenlabs_api_key and self.elevenlabs_voice_id)

    @property
    def tts_mode(self) -> str:
        """Which TTS engine will be used."""
        if self.is_elevenlabs_configured:
            return "elevenlabs"
        return "gtts"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # This makes settings case-insensitive for env vars
        # DATABASE_URL, database_url, Database_Url all work
        case_sensitive = False


# Create a single global instance -- import this everywhere
settings = Settings()
