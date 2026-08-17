"""
health.py -- Health Check Endpoint

GET /api/health

Returns the server status and which AI services are available.
The frontend uses this to show a green/red status indicator.
"""

from fastapi import APIRouter
from backend.models.schemas import HealthResponse
from backend.config import settings

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    Check server health and service availability.

    Returns which AI services are configured and their status.
    """
    services = {
        "stt": f"faster-whisper ({settings.whisper_model_size})",
        "llm": f"ollama ({settings.colab_llm_url})",
        "tts": settings.tts_mode,
    }

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        services=services,
    )
