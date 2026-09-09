"""
knowledge.py -- Knowledge Document Management Endpoints

POST   /api/personas/{id}/knowledge    → Upload a document for RAG
GET    /api/personas/{id}/knowledge    → List ingested documents
DELETE /api/personas/{id}/knowledge    → Delete all documents for a persona
"""

import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Persona, KnowledgeDoc
from backend.utils.logger import logger
from rag.ingest import ingest_document, delete_persona_documents, get_collection_stats

router = APIRouter(prefix="/api", tags=["Knowledge"])


@router.post("/personas/{persona_id}/knowledge", status_code=201)
def upload_knowledge_document(
    persona_id: int,
    document: UploadFile,
    title: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """
    Upload a text document to a persona's knowledge base.

    The document is:
    1. Saved temporarily
    2. Chunked and embedded into ChromaDB (for RAG retrieval)
    3. Metadata saved to PostgreSQL knowledge_docs table
    """
    # Verify persona exists
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    # Read the uploaded file
    content_bytes = document.file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="Uploaded document is empty")

    # Decode text content
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Could not decode file. Please upload a UTF-8 text file (.txt).",
        )

    # Use filename as title if not provided
    doc_title = title.strip() or (document.filename or "Untitled").rsplit(".", 1)[0].replace("_", " ").title()

    # Save to a temp file for ingestion
    temp_path = os.path.join(tempfile.gettempdir(), f"resonant_doc_{uuid.uuid4().hex[:8]}.txt")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Ingest into ChromaDB
        result = ingest_document(temp_path, persona_id=persona_id, title=doc_title)

        # Save metadata to PostgreSQL
        knowledge_doc = KnowledgeDoc(
            persona_id=persona_id,
            title=doc_title,
            content=content,
            doc_type=document.filename.rsplit(".", 1)[-1] if document.filename else "txt",
            chunk_count=result["chunk_count"],
        )
        db.add(knowledge_doc)
        db.commit()
        db.refresh(knowledge_doc)

        logger.info(
            f"Knowledge doc uploaded: '{doc_title}' for persona {persona_id} "
            f"({result['chunk_count']} chunks)"
        )

        return {
            "id": knowledge_doc.id,
            "title": doc_title,
            "persona_id": persona_id,
            "chunk_count": result["chunk_count"],
            "total_chars": result["total_chars"],
            "message": f"Document '{doc_title}' ingested successfully with {result['chunk_count']} chunks.",
        }

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/personas/{persona_id}/knowledge")
def list_knowledge_documents(
    persona_id: int,
    db: Session = Depends(get_db),
):
    """List all knowledge documents for a persona."""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.persona_id == persona_id).all()

    return {
        "persona_id": persona_id,
        "persona_name": persona.name,
        "documents": [
            {
                "id": doc.id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in docs
        ],
        "total_documents": len(docs),
        "total_chunks": sum(doc.chunk_count or 0 for doc in docs),
    }


@router.delete("/personas/{persona_id}/knowledge", status_code=200)
def delete_knowledge_documents(
    persona_id: int,
    db: Session = Depends(get_db),
):
    """Delete all knowledge documents for a persona (from both ChromaDB and PostgreSQL)."""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    # Delete from ChromaDB
    deleted_chunks = delete_persona_documents(persona_id)

    # Delete from PostgreSQL
    docs_deleted = db.query(KnowledgeDoc).filter(KnowledgeDoc.persona_id == persona_id).delete()
    db.commit()

    logger.info(
        f"Deleted knowledge for persona {persona_id}: "
        f"{docs_deleted} docs, {deleted_chunks} chunks"
    )

    return {
        "message": f"Deleted {docs_deleted} documents ({deleted_chunks} chunks) for persona {persona_id}",
        "documents_deleted": docs_deleted,
        "chunks_deleted": deleted_chunks,
    }
