"""
conversations.py -- Conversation History Endpoints

GET    /api/personas/{id}/history       → Get conversation history for a persona
DELETE /api/conversations/{id}          → Delete a specific conversation
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Persona, Conversation
from backend.models.schemas import ConversationResponse
from backend.utils.logger import logger

router = APIRouter(prefix="/api", tags=["Conversations"])


@router.get(
    "/personas/{persona_id}/history",
    response_model=list[ConversationResponse],
)
def get_conversation_history(
    persona_id: int,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """Get the conversation history for a specific persona."""
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    conversations = (
        db.query(Conversation)
        .filter(Conversation.persona_id == persona_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .all()
    )

    logger.info(f"Retrieved {len(conversations)} conversations for persona {persona_id}")
    return conversations


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Delete a specific conversation."""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )

    logger.info(f"Deleting conversation id={conversation_id}")
    db.delete(conversation)
    db.commit()
