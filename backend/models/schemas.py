"""
schemas.py -- Pydantic Request/Response Models

These are NOT database models (those are in db_models.py).
These define the exact JSON shape of API requests and responses.

Why separate from db_models?
- db_models define what's STORED in PostgreSQL.
- schemas define what's SENT/RECEIVED over HTTP.
- They often look similar but serve different purposes.
  For example, ProcessResponse includes processing_time_ms
  which is computed at runtime, not stored in the DB.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ========================================
# Process Endpoint (the main pipeline)
# ========================================

class ProcessResponse(BaseModel):
    """
    JSON response from POST /api/process

    This is what the frontend receives after recording audio.
    """
    transcript: str = Field(description="What the user said (from Whisper STT)")
    reply_text: str = Field(description="The persona's text response (from LLM)")
    audio_url: str = Field(description="URL to the generated audio file")
    target_language: str = Field(description="Language code the response is in")
    context_used: list[str] = Field(
        default=[],
        description="RAG context chunks that were injected into the prompt",
    )
    processing_time_ms: float = Field(description="Total pipeline time in milliseconds")


# ========================================
# Health Endpoint
# ========================================

class HealthResponse(BaseModel):
    """JSON response from GET /api/health"""
    status: str = Field(description="Server status: healthy / degraded / unhealthy")
    version: str = Field(default="0.1.0", description="API version")
    services: dict = Field(
        description="Status of each AI service (stt, llm, tts)",
        default={},
    )


# ========================================
# Persona Endpoints (CRUD)
# ========================================

class PersonaCreate(BaseModel):
    """Request body for POST /api/personas"""
    name: str = Field(min_length=1, max_length=100)
    role: Optional[str] = None
    institution: Optional[str] = None
    personality_traits: list[str] = Field(default=[])
    knowledge_areas: list[str] = Field(default=[])
    speaking_style: Optional[str] = None
    constraints: list[str] = Field(default=[])
    voice_sample_path: Optional[str] = None


class PersonaUpdate(BaseModel):
    """Request body for PUT /api/personas/{id} (all fields optional)"""
    name: Optional[str] = None
    role: Optional[str] = None
    institution: Optional[str] = None
    personality_traits: Optional[list[str]] = None
    knowledge_areas: Optional[list[str]] = None
    speaking_style: Optional[str] = None
    constraints: Optional[list[str]] = None
    voice_sample_path: Optional[str] = None


class PersonaResponse(BaseModel):
    """JSON response for a single persona"""
    id: int
    name: str
    role: Optional[str] = None
    institution: Optional[str] = None
    personality_traits: list[str] = []
    knowledge_areas: list[str] = []
    speaking_style: Optional[str] = None
    constraints: list[str] = []
    voice_sample_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Allows creating from SQLAlchemy ORM objects


# ========================================
# Conversation Endpoints
# ========================================

class ConversationResponse(BaseModel):
    """JSON response for a single conversation entry"""
    id: int
    persona_id: int
    transcript: str
    target_language: str
    reply_text: str
    reply_audio_path: Optional[str] = None
    processing_time_ms: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========================================
# Error Response
# ========================================

class ErrorResponse(BaseModel):
    """Standardized error response"""
    error: str = Field(description="Short error type, e.g. 'transcription_failed'")
    detail: str = Field(description="Human-readable error message")
    status_code: int = Field(description="HTTP status code")
