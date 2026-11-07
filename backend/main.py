"""
main.py -- FastAPI Application Entry Point

This is the first file that runs when you start the server:
    uvicorn backend.main:app --reload

It creates the FastAPI app and wires everything together:
1. CORS middleware (so the browser can talk to the API)
2. Route modules (health, process, personas, etc.)
3. Static file serving (frontend + audio outputs)
4. Startup validation (checks that services are reachable)
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.utils.logger import logger

# Import route modules
from backend.routes import health
from backend.routes import process
from backend.routes import personas
from backend.routes import conversations
from backend.routes import knowledge


def _auto_setup():
    """
    Auto-setup on startup: create DB tables and ingest sample docs.

    On Render.com (free tier), the filesystem is ephemeral — ChromaDB data
    is lost on every deploy. This function re-ingests sample documents
    automatically so the demo always has data ready.
    """
    # Create database tables if they don't exist
    try:
        from backend.database import engine, Base
        from backend.models import db_models  # noqa: F401 — registers models
        Base.metadata.create_all(bind=engine)
        logger.info("  Database tables verified/created")
    except Exception as e:
        logger.warning(f"  DB table creation skipped: {e}")

    # Create a default persona if none exists
    try:
        from backend.database import SessionLocal
        from backend.models.db_models import Persona
        db = SessionLocal()
        if db.query(Persona).count() == 0:
            default_persona = Persona(
                name="Dr. Ayesha Sharma",
                role="Professor of Computer Science",
                institution="IIT Delhi",
                personality_traits=["Patient", "Uses real-world analogies", "Encouraging", "Humorous"],
                knowledge_areas=["Machine Learning", "Cloud Computing", "Data Structures", "Python"],
                speaking_style="Conversational but academic, uses analogies from everyday life",
                constraints=["Never give direct exam answers", "Keep responses under 200 words"],
            )
            db.add(default_persona)
            db.commit()
            logger.info("  Created default persona: Dr. Ayesha Sharma")
        db.close()
    except Exception as e:
        logger.warning(f"  Default persona creation skipped: {e}")

    # Auto-ingest sample documents into ChromaDB
    try:
        sample_dir = Path("rag/sample_docs")
        if sample_dir.exists() and list(sample_dir.glob("*.txt")):
            from rag.ingest import get_collection, ingest_directory
            collection = get_collection()
            if collection.count() == 0:
                results = ingest_directory(str(sample_dir), persona_id=1)
                total_chunks = sum(r["chunk_count"] for r in results)
                logger.info(f"  Auto-ingested {len(results)} docs ({total_chunks} chunks) into ChromaDB")
            else:
                logger.info(f"  ChromaDB already has {collection.count()} chunks, skipping ingestion")
    except Exception as e:
        logger.warning(f"  ChromaDB auto-ingest skipped: {e}")


# --- Lifespan Event Handler ---
# This runs ONCE when the server starts and ONCE when it shuts down.
# Use it to validate configuration and log startup info.

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on server startup and shutdown."""
    # === STARTUP ===
    logger.info("Starting Resonant API server...")
    logger.info(f"  Whisper model: {settings.whisper_model_size}")
    logger.info(f"  LLM mode: {settings.llm_mode}")
    logger.info(f"  LLM endpoint: {settings.colab_llm_url}")
    logger.info(f"  Groq API: {'configured' if settings.groq_api_key else 'not set'}")
    logger.info(f"  Database: {settings.database_url[:40]}...")

    # Create the outputs directory if it doesn't exist
    os.makedirs(settings.output_dir, exist_ok=True)

    # Auto-setup: create tables, default persona, ingest sample docs
    _auto_setup()

    logger.info("Server ready!")

    yield  # Server runs here

    # === SHUTDOWN ===
    logger.info("Shutting down Resonant API server...")


# --- Create the FastAPI App ---

app = FastAPI(
    title="Resonant API",
    description="An AI Digital Twin for Multilingual Personal Presence",
    version="0.1.0",
    lifespan=lifespan,
)


# --- CORS Middleware ---
# Without this, the browser blocks requests from the frontend to the API
# because they're on different ports during development.
# allow_origins=["*"] means "accept requests from any origin" (fine for dev).

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Include Route Modules ---
# Each module in backend/routes/ defines an APIRouter.
# include_router() wires them into the main app.

app.include_router(health.router)
app.include_router(process.router)
app.include_router(personas.router)
app.include_router(conversations.router)
app.include_router(knowledge.router)


# --- Mount Static Files ---

# Serve generated audio files at /outputs/
# Example: /outputs/response_20260817_abc.mp3
if os.path.exists(settings.output_dir):
    app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")

# Serve the frontend at / (must be LAST — it's a catch-all)
# When someone visits http://localhost:8000/, they see index.html
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
