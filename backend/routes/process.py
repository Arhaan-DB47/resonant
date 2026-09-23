"""
process.py -- The Main Pipeline Endpoint

POST /api/process

This is the HEART of Resonant. It orchestrates the full pipeline:
    Audio In -> STT -> RAG -> LLM -> TTS -> Audio Out

Week 2: STT is LIVE (faster-whisper)
Week 3: LLM is LIVE (Ollama via Colab, with fallback mode)
Week 4: TTS is LIVE (gTTS local, Coqui XTTS on Colab)
         Conversations saved to PostgreSQL
Week 5: RAG is LIVE (ChromaDB + sentence-transformers)
Week 7: Per-stage timing, edge case handling, improved error messages

ALL PIPELINE STAGES ARE NOW LIVE.
"""

import time

from fastapi import APIRouter, UploadFile, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.models.schemas import ProcessResponse, ErrorResponse
from backend.models.db_models import Persona, Conversation
from backend.database import get_db
from backend.services.stt_service import stt_service
from backend.services.llm_service import llm_service
from backend.services.tts_service import tts_service
from backend.services.rag_service import rag_service
from backend.prompts.prompt_loader import build_system_prompt
from backend.utils.audio_utils import save_upload, convert_to_wav, cleanup_temp_files
from backend.utils.logger import logger

router = APIRouter(prefix="/api", tags=["Process"])

# Minimum useful audio size (~1KB = very short recording)
MIN_AUDIO_BYTES = 500


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
    pipeline_start = time.time()
    temp_path = None
    wav_path = None

    # Per-stage timing
    timings = {}

    logger.info(
        f"Processing request: file={audio.filename}, "
        f"lang={target_language}, persona_id={persona_id}"
    )

    try:
        # === STAGE 1: Save uploaded audio ===
        stage_start = time.time()

        audio_bytes = await audio.read()

        # Edge case: too short / empty recording
        if len(audio_bytes) < MIN_AUDIO_BYTES:
            raise ValueError(
                "Recording too short. Please hold the record button "
                "for at least 1-2 seconds while speaking."
            )

        temp_path = save_upload(audio_bytes, audio.filename or "upload.wav")
        timings["save"] = (time.time() - stage_start) * 1000

        logger.info(
            f"  Stage 1 - Save: {len(audio_bytes)/1024:.1f} KB, "
            f"{timings['save']:.0f}ms"
        )

        # === STAGE 2: Speech-to-Text (Whisper) ===
        stage_start = time.time()

        wav_path = convert_to_wav(temp_path)
        stt_result = stt_service.transcribe(
            wav_path,
            language=target_language if target_language != "auto" else None,
        )

        transcript = stt_result["transcript"]
        detected_lang = stt_result["language"]
        timings["stt"] = (time.time() - stage_start) * 1000

        # Edge case: empty transcript (silence or background noise)
        if not transcript or transcript.strip() == "":
            raise ValueError(
                "Could not detect any speech. Please speak clearly "
                "and ensure your microphone is working."
            )

        logger.info(
            f"  Stage 2 - STT: lang={detected_lang}, "
            f"{timings['stt']:.0f}ms, text='{transcript[:60]}'"
        )

        # === STAGE 3: RAG Retrieval (ChromaDB) ===
        stage_start = time.time()

        context_chunks = rag_service.retrieve(transcript, persona_id=persona_id)
        timings["rag"] = (time.time() - stage_start) * 1000

        logger.info(
            f"  Stage 3 - RAG: {len(context_chunks)} chunks, "
            f"{timings['rag']:.0f}ms"
        )

        # === STAGE 4: LLM Persona Response ===
        stage_start = time.time()

        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"Persona with id {persona_id} not found. "
                       f"Create one first via the UI or POST /api/personas.",
            )

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
        timings["llm"] = (time.time() - stage_start) * 1000

        logger.info(
            f"  Stage 4 - LLM: mode={llm_mode}, "
            f"{timings['llm']:.0f}ms, reply='{reply_text[:60]}'"
        )

        # === STAGE 5: Text-to-Speech ===
        stage_start = time.time()

        voice_sample = persona.voice_sample_path if persona else None
        tts_result = tts_service.synthesize(
            text=reply_text,
            language=detected_lang,
            voice_sample_path=voice_sample,
        )

        audio_url = tts_result["audio_path"]
        tts_mode = tts_result["mode"]
        timings["tts"] = (time.time() - stage_start) * 1000

        logger.info(
            f"  Stage 5 - TTS: mode={tts_mode}, "
            f"{timings['tts']:.0f}ms, file={audio_url}"
        )

        # === STAGE 6: Save Conversation to Database ===
        stage_start = time.time()

        processing_time_ms = (time.time() - pipeline_start) * 1000

        conversation = Conversation(
            persona_id=persona.id,
            transcript=transcript,
            target_language=detected_lang,
            reply_text=reply_text,
            reply_audio_path=audio_url,
            processing_time_ms=processing_time_ms,
        )
        db.add(conversation)
        db.commit()
        timings["db"] = (time.time() - stage_start) * 1000

        logger.info(f"  Stage 6 - DB: saved id={conversation.id}, {timings['db']:.0f}ms")

        # === Pipeline Summary ===
        total_ms = (time.time() - pipeline_start) * 1000
        logger.info(
            f"  PIPELINE COMPLETE: {total_ms:.0f}ms total "
            f"| save={timings.get('save', 0):.0f}ms "
            f"| stt={timings.get('stt', 0):.0f}ms "
            f"| rag={timings.get('rag', 0):.0f}ms "
            f"| llm={timings.get('llm', 0):.0f}ms "
            f"| tts={timings.get('tts', 0):.0f}ms "
            f"| db={timings.get('db', 0):.0f}ms"
        )

        return ProcessResponse(
            transcript=transcript,
            reply_text=reply_text,
            audio_url=audio_url,
            target_language=detected_lang,
            context_used=context_chunks,
            processing_time_ms=total_ms,
        )

    except ValueError as e:
        # Input validation errors (bad format, too large, empty, etc.)
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except FileNotFoundError as e:
        logger.error(f"File error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for persona not found)
        raise

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during processing. Please try again.",
        )

    finally:
        # Always clean up temp files, even if an error occurred
        cleanup_temp_files(temp_path, wav_path)
