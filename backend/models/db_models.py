"""
db_models.py — SQLAlchemy ORM Models

These classes define the structure of the 3 database tables:
1. Persona     — the digital twin profiles
2. Conversation — every Q&A interaction logged
3. KnowledgeDoc — source documents for RAG retrieval

Each class maps directly to a PostgreSQL table.
Each attribute maps to a column in that table.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    ARRAY,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class Persona(Base):
    """
    Represents a digital twin persona.

    Example:
        Persona(
            name="Dr. Ayesha Sharma",
            role="Professor of Computer Science",
            institution="IIT Delhi",
            personality_traits=["Patient", "Uses analogies", "Humorous"],
            knowledge_areas=["Machine Learning", "Cloud Computing"],
            speaking_style="Conversational but academic",
            constraints=["Never claim to be human", "Keep responses under 150 words"],
        )
    """

    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    role = Column(String(200))
    institution = Column(String(200))

    # PostgreSQL supports native arrays — perfect for lists of traits
    personality_traits = Column(ARRAY(Text), default=[])
    knowledge_areas = Column(ARRAY(Text), default=[])
    speaking_style = Column(Text)
    constraints = Column(ARRAY(Text), default=[])

    # Path to the reference voice audio clip (for voice cloning)
    voice_sample_path = Column(String(500))

    # The fully compiled system prompt (generated from the template + persona data)
    system_prompt = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships — allows persona.conversations and persona.knowledge_docs
    conversations = relationship("Conversation", back_populates="persona", cascade="all, delete-orphan")
    knowledge_docs = relationship("KnowledgeDoc", back_populates="persona", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Persona(id={self.id}, name='{self.name}', role='{self.role}')>"


class Conversation(Base):
    """
    Stores every Q&A interaction with a persona.

    Each row represents one complete pipeline run:
    user audio → transcript → LLM reply → TTS audio
    """

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key linking this conversation to a specific persona
    persona_id = Column(Integer, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)

    # The input
    user_audio_path = Column(String(500))       # Path to the uploaded audio file
    transcript = Column(Text, nullable=False)    # What the user said (from Whisper)
    target_language = Column(String(10), nullable=False)  # e.g., "en", "hi", "es"

    # The output
    reply_text = Column(Text, nullable=False)     # What the LLM generated
    reply_audio_path = Column(String(500))        # Path to the TTS output audio

    # Metadata
    processing_time_ms = Column(Float)            # How long the full pipeline took
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship — allows conversation.persona
    persona = relationship("Persona", back_populates="conversations")

    def __repr__(self):
        return f"<Conversation(id={self.id}, persona_id={self.persona_id}, lang='{self.target_language}')>"


class KnowledgeDoc(Base):
    """
    Source documents used for RAG (Retrieval Augmented Generation).

    These are the professor's lecture notes, FAQs, syllabi, etc.
    They get chunked and embedded into ChromaDB for semantic search.
    This table stores the original full-text document + metadata.
    """

    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key linking this document to a specific persona
    persona_id = Column(Integer, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)

    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)          # The full document text

    # What kind of document this is
    doc_type = Column(String(50))                    # "lecture_notes", "faq", "paper", etc.

    # How many chunks were created when this doc was ingested into ChromaDB
    chunk_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship — allows doc.persona
    persona = relationship("Persona", back_populates="knowledge_docs")

    def __repr__(self):
        return f"<KnowledgeDoc(id={self.id}, title='{self.title}', type='{self.doc_type}')>"
