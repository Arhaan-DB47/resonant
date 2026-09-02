"""
process.py -- The Main Pipeline Endpoint

POST /api/process

This is the HEART of Resonant. It orchestrates the full pipeline:
    Audio In -> STT -> RAG -> LLM -> TTS -> Audio Out

Week 2: STT is LIVE (faster-whisper)
Week 3: LLM is LIVE (Ollama via Colab, with fallback mode)
Remaining stubs:
    Week 4: TTS (gTTS / Coqui XTTS)
    Week 5: RAG (ChromaDB)
"""

import time

from fastapi import APIRouter, UploadFile, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.models.schemas import ProcessResponse, ErrorResponse
from backend.models.db_models import Persona
from backend.database import get_db
from backend.services.stt_service import stt_service
from backend.services.llm_service import llm_service
from backend.prompts.prompt_loader import build_system_prompt
from backend.utils.audio_utils import save_upload, convert_to_wav, cleanup_temp_files
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
    db: Session = Depends(get_db),
):
    """
    The main pipeline endpoint.

    Receives a recorded audio file + target language,
    runs it through the AI pipeline, and returns the
    transcript, reply text, and synthesized audio URL.
    """
    start_time = time.time()
    temp_path = None
    wav_path = None

    logger.info(
        f"Processing request: file={audio.filename}, "
        f"lang={target_language}, persona_id={persona_id}"
    )

    try:
        # === STAGE 1: Save uploaded audio ===
        audio_bytes = await audio.read()
        logger.info(f"  Stage 1 - Received audio: {len(audio_bytes)} bytes")

        temp_path = save_upload(audio_bytes, audio.filename or "upload.wav")

        # === STAGE 2: Speech-to-Text (Whisper) === [LIVE - Week 2]
        wav_path = convert_to_wav(temp_path)
        stt_result = stt_service.transcribe(wav_path, language=target_language if target_language != "auto" else None)

        transcript = stt_result["transcript"]
        detected_lang = stt_result["language"]
        stt_time = stt_result["duration_ms"]

        logger.info(
            f"  Stage 2 - STT complete: lang={detected_lang}, "
            f"time={stt_time:.0f}ms, text='{transcript[:60]}'"
        )

        # === STAGE 3: RAG Retrieval (ChromaDB) ===
        # TODO Week 5: context_chunks = rag_service.retrieve(transcript, persona_id)
        context_chunks = []
        logger.info(f"  Stage 3 - RAG: skipped (not connected yet)")

        # === STAGE 4: LLM Persona Response === [LIVE - Week 3]
        # Load persona from database
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            logger.warning(f"Persona {persona_id} not found, using default response")
            reply_text = f"[Persona {persona_id} not found] You said: '{transcript}'"
            llm_mode = "error"
            llm_time = 0.0
        else:
            # Build the system prompt from persona data + template
            system_prompt = build_system_prompt(
                persona=persona,
                target_language=detected_lang,
                context_chunks=context_chunks if context_chunks else None,
            )

            # Call the LLM (Ollama or fallback)
            llm_result = llm_service.generate(
                system_prompt=system_prompt,
                user_message=transcript,
            )

            reply_text = llm_result["reply"]
            llm_mode = llm_result["mode"]
            llm_time = llm_result["duration_ms"]

        logger.info(
            f"  Stage 4 - LLM: mode={llm_mode}, time={llm_time:.0f}ms, "
            f"reply='{reply_text[:60]}'"
        )

        # === STAGE 5: Text-to-Speech ===
        # TODO Week 4: audio_path = tts_service.synthesize(reply_text, target_language)
        audio_url = "/outputs/stub_response.mp3"
        logger.info(f"  Stage 5 - TTS: stub audio")

        # === Calculate processing time ===
        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(f"  Pipeline complete in {processing_time_ms:.1f}ms")

        return ProcessResponse(
            transcript=transcript,
            reply_text=reply_text,
            audio_url=audio_url,
            target_language=detected_lang,
            context_used=context_chunks,
            processing_time_ms=processing_time_ms,
        )

    except ValueError as e:
        # Input validation errors (bad format, too large, etc.)
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except FileNotFoundError as e:
        logger.error(f"File error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline processing failed: {str(e)}",
        )

    finally:
        # Always clean up temp files, even if an error occurred
        cleanup_temp_files(temp_path, wav_path)
