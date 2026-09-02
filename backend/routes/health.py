"""
health.py -- Health Check Endpoint

GET /api/health

Returns the server status and which AI services are available.
The frontend uses this to show a green/red status indicator.
"""

from fastapi import APIRouter
from backend.models.schemas import HealthResponse
from backend.config import settings
from backend.services.llm_service import llm_service

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    Check server health and service availability.

    Returns which AI services are configured and their status.
    """
    # Check if Ollama is actually reachable
    llm_available = llm_service.is_available()
    llm_status = f"ollama ({settings.colab_llm_url}) - {'ONLINE' if llm_available else 'OFFLINE (fallback mode)'}"

    services = {
        "stt": f"faster-whisper ({settings.whisper_model_size})",
        "llm": llm_status,
        "tts": settings.tts_mode,
    }

    # Server is "degraded" if LLM is offline (still works via fallback)
    status = "healthy" if llm_available else "degraded"

    return HealthResponse(
        status=status,
        version="0.2.0",
        services=services,
    )
