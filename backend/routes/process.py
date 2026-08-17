"""
process.py -- The Main Pipeline Endpoint

POST /api/process

This is the HEART of Resonant. It orchestrates the full pipeline:
    Audio In → STT → RAG → LLM → TTS → Audio Out

For now, this is a SKELETON with stub responses.
Each stage will be wired to real services in Weeks 2-4:
    Week 2: STT (faster-whisper)
    Week 3: LLM (Ollama via Colab)
    Week 4: TTS (gTTS / Coqui XTTS)
    Week 5: RAG (ChromaDB)
"""

import time

from fastapi import APIRouter, UploadFile, Form, HTTPException
from backend.models.schemas import ProcessResponse, ErrorResponse
from backend.utils.logger import logger

router = APIRouter(prefix="/api", tags=["Process"])


@router.post(
    "/process",
    response_model=ProcessResponse,
    responses={500: {"model": ErrorResponse}},
)
async def process_audio(
    audio: UploadFile,
    target_language: str = Form(default="en"),
    persona_id: int = Form(default=1),
):
    """
    The main pipeline endpoint.

    Receives a recorded audio file + target language,
    runs it through the AI pipeline, and returns the
    transcript, reply text, and synthesized audio URL.
    """
    start_time = time.time()

    logger.info(
        f"Processing request: file={audio.filename}, "
        f"lang={target_language}, persona_id={persona_id}"
    )

    try:
        # === STAGE 1: Save uploaded audio ===
        # (Will be implemented properly in Week 2)
        audio_bytes = await audio.read()
        logger.info(f"  Stage 1 - Received audio: {len(audio_bytes)} bytes")

        # === STAGE 2: Speech-to-Text (Whisper) ===
        # TODO Week 2: transcript = stt_service.transcribe(temp_file)
        transcript = "[STT not connected yet] Stub transcript from uploaded audio"
        logger.info(f"  Stage 2 - STT: {transcript[:50]}...")

        # === STAGE 3: RAG Retrieval (ChromaDB) ===
        # TODO Week 5: context_chunks = rag_service.retrieve(transcript, persona_id)
        context_chunks = ["[RAG not connected yet] No context retrieved"]
        logger.info(f"  Stage 3 - RAG: {len(context_chunks)} chunks retrieved")

        # === STAGE 4: LLM Persona Response ===
        # TODO Week 3: reply_text = llm_service.generate(system_prompt, transcript)
        reply_text = (
            f"[LLM not connected yet] This is a stub response "
            f"for persona {persona_id} in {target_language}."
        )
        logger.info(f"  Stage 4 - LLM: {reply_text[:50]}...")

        # === STAGE 5: Text-to-Speech ===
        # TODO Week 4: audio_path = tts_service.synthesize(reply_text, target_language)
        audio_url = "/outputs/stub_response.mp3"
        logger.info(f"  Stage 5 - TTS: {audio_url}")

        # === Calculate processing time ===
        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(f"  Pipeline complete in {processing_time_ms:.1f}ms")

        return ProcessResponse(
            transcript=transcript,
            reply_text=reply_text,
            audio_url=audio_url,
            target_language=target_language,
            context_used=context_chunks,
            processing_time_ms=processing_time_ms,
        )

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline processing failed: {str(e)}",
        )
