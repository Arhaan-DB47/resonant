"""
personas.py -- Persona CRUD Endpoints

GET    /api/personas          → List all personas
POST   /api/personas          → Create a new persona
GET    /api/personas/{id}     → Get a specific persona
PUT    /api/personas/{id}     → Update a persona
DELETE /api/personas/{id}     → Delete a persona
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Persona
from backend.models.schemas import PersonaCreate, PersonaUpdate, PersonaResponse
from backend.utils.logger import logger

router = APIRouter(prefix="/api", tags=["Personas"])


@router.get("/personas", response_model=list[PersonaResponse])
def list_personas(db: Session = Depends(get_db)):
    """List all persona profiles."""
    personas = db.query(Persona).all()
    logger.info(f"Listed {len(personas)} personas")
    return personas


@router.post("/personas", response_model=PersonaResponse, status_code=201)
def create_persona(data: PersonaCreate, db: Session = Depends(get_db)):
    """Create a new persona profile."""
    persona = Persona(
        name=data.name,
        role=data.role,
        institution=data.institution,
        personality_traits=data.personality_traits,
        knowledge_areas=data.knowledge_areas,
        speaking_style=data.speaking_style,
        constraints=data.constraints,
        voice_sample_path=data.voice_sample_path,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)

    logger.info(f"Created persona: {persona.name} (id={persona.id})")
    return persona


@router.get("/personas/{persona_id}", response_model=PersonaResponse)
def get_persona(persona_id: int, db: Session = Depends(get_db)):
    """Get a specific persona by ID."""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()

    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    return persona


@router.put("/personas/{persona_id}", response_model=PersonaResponse)
def update_persona(persona_id: int, data: PersonaUpdate, db: Session = Depends(get_db)):
    """Update an existing persona. Only provided fields are updated."""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()

    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    # Only update fields that were actually provided (not None)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(persona, field, value)

    db.commit()
    db.refresh(persona)

    logger.info(f"Updated persona: {persona.name} (id={persona.id})")
    return persona


@router.delete("/personas/{persona_id}", status_code=204)
def delete_persona(persona_id: int, db: Session = Depends(get_db)):
    """Delete a persona and all its conversations and knowledge docs."""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()

    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    logger.info(f"Deleting persona: {persona.name} (id={persona.id})")
    db.delete(persona)
    db.commit()
