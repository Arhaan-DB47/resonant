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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.utils.logger import logger

# Import route modules
from backend.routes import health
from backend.routes import process
from backend.routes import personas


# --- Lifespan Event Handler ---
# This runs ONCE when the server starts and ONCE when it shuts down.
# Use it to validate configuration and log startup info.

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on server startup and shutdown."""
    # === STARTUP ===
    logger.info("Starting Resonant API server...")
    logger.info(f"  Whisper model: {settings.whisper_model_size}")
    logger.info(f"  LLM endpoint: {settings.colab_llm_url}")
    logger.info(f"  TTS mode: {settings.tts_mode}")
    logger.info(f"  Database: {settings.database_url[:40]}...")

    # Create the outputs directory if it doesn't exist
    os.makedirs(settings.output_dir, exist_ok=True)

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

# Will be added later:
# app.include_router(conversations.router)


# --- Mount Static Files ---

# Serve generated audio files at /outputs/
# Example: /outputs/response_20260817_abc.mp3
if os.path.exists(settings.output_dir):
    app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")

# Serve the frontend at / (must be LAST — it's a catch-all)
# When someone visits http://localhost:8000/, they see index.html
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
