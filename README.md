# Resonant

> **A Self-Hosted AI Digital Twin for Multilingual Personal Presence**

Resonant creates an AI "digital twin" of a real person — a voice-powered assistant that listens to your question, thinks like the real person using a locally-run LLM grounded in their actual documents (RAG), and speaks back in their voice, in any language.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        PIPELINE                              │
│                                                              │
│  🎤 Audio  →  📝 STT  →  📚 RAG  →  🤖 LLM  →  🔊 TTS    │
│  (upload)    (Whisper)  (ChromaDB)  (Ollama)   (gTTS/XTTS)  │
│                                                              │
│              Local CPU    Local     Colab GPU   Local/Colab  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │ PostgreSQL  │
                    │  personas   │
                    │  history    │
                    │  documents  │
                    └─────────────┘
```

## Tech Stack

| Layer | Technology | Runs On |
|-------|-----------|:-------:|
| Backend | FastAPI (Python 3.14) | 🖥️ Local |
| STT | faster-whisper (`tiny` model, int8 quantization) | 🖥️ Local CPU |
| LLM | Ollama + Llama 3.1 8B | ☁️ Google Colab GPU |
| TTS | gTTS (Google Text-to-Speech) | 🖥️ Local |
| RAG | ChromaDB + all-MiniLM-L6-v2 embeddings | 🖥️ Local |
| Database | PostgreSQL 18 + SQLAlchemy 2.0 | 🖥️ Local |
| Frontend | Vanilla HTML/CSS/JS (dark glassmorphism theme) | 🖥️ Local |

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Arhaan-DB47/resonant.git
cd resonant

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up PostgreSQL
# Create a database called "resonant", then:
copy .env.example .env
# Edit .env with your database credentials

# 5. Create database tables
python scripts/setup_db.py

# 6. Run the server
uvicorn backend.main:app --reload

# 7. Open in browser
# Frontend:  http://localhost:8000/
# API docs:  http://localhost:8000/docs
# Health:    http://localhost:8000/api/health
```

> 📖 For detailed setup instructions, see [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Server health + LLM availability check |
| `POST` | `/api/process` | **Full pipeline:** audio → STT → RAG → LLM → TTS → audio |
| `GET` | `/api/personas` | List all personas |
| `POST` | `/api/personas` | Create a persona |
| `GET` | `/api/personas/{id}` | Get a specific persona |
| `PUT` | `/api/personas/{id}` | Update a persona |
| `DELETE` | `/api/personas/{id}` | Delete a persona (cascades) |
| `GET` | `/api/personas/{id}/history` | Get conversation history |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation |
| `POST` | `/api/personas/{id}/knowledge` | Upload a knowledge document |
| `GET` | `/api/personas/{id}/knowledge` | List knowledge documents |
| `DELETE` | `/api/personas/{id}/knowledge` | Delete all knowledge documents |

> 📖 For curl examples and schemas, see [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

## The Pipeline

Every call to `POST /api/process` runs this 6-stage pipeline with per-stage timing:

| Stage | What Happens | Service | Time* |
|:-----:|-------------|---------|:-----:|
| 1 | Save + convert uploaded audio to 16kHz mono WAV | `audio_utils.py` | ~50ms |
| 2 | Transcribe speech → text | `stt_service.py` (faster-whisper) | ~2s |
| 3 | Retrieve relevant document chunks | `rag_service.py` (ChromaDB) | ~20ms |
| 4 | Load persona → build prompt → generate reply | `llm_service.py` (Ollama) | ~5s |
| 5 | Convert reply text → audio file | `tts_service.py` (gTTS) | ~1s |
| 6 | Save conversation to PostgreSQL | `database.py` | ~10ms |

*Approximate times for a 5-second audio clip with Colab LLM.

## Project Structure

```
resonant/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Pydantic settings from .env
│   ├── database.py              # SQLAlchemy engine + sessions
│   ├── models/
│   │   ├── db_models.py         # ORM: Persona, Conversation, KnowledgeDoc
│   │   └── schemas.py           # Pydantic request/response models
│   ├── routes/
│   │   ├── health.py            # GET /api/health
│   │   ├── process.py           # POST /api/process (the pipeline)
│   │   ├── personas.py          # Persona CRUD
│   │   ├── conversations.py     # Conversation history
│   │   └── knowledge.py         # Knowledge document upload/list/delete
│   ├── services/
│   │   ├── stt_service.py       # Speech-to-Text (faster-whisper)
│   │   ├── llm_service.py       # LLM client (Ollama + fallback)
│   │   ├── tts_service.py       # Text-to-Speech (gTTS + Coqui XTTS)
│   │   └── rag_service.py       # RAG retrieval (ChromaDB)
│   ├── prompts/
│   │   ├── system_prompt.yaml   # Persona prompt template
│   │   └── prompt_loader.py     # YAML → compiled prompt
│   ├── utils/
│   │   ├── audio_utils.py       # Audio conversion + cleanup
│   │   └── logger.py            # Loguru logging
│   └── tests/
│       ├── test_stt.py          # 16 tests
│       ├── test_llm.py          # 11 tests
│       ├── test_tts.py          # 13 tests
│       └── test_rag.py          # 14 tests
├── frontend/
│   ├── index.html               # Main page (persona card, chat, recorder)
│   └── assets/
│       ├── styles.css           # Dark glassmorphism theme
│       ├── api.js               # Backend API client
│       ├── recorder.js          # MediaRecorder (hold-to-record)
│       ├── player.js            # Audio playback
│       └── ui.js                # Main UI controller
├── rag/
│   ├── ingest.py                # Document chunking + ChromaDB ingestion
│   └── sample_docs/             # Sample lecture notes + syllabus
├── outputs/                     # Generated audio files
├── docs/
│   ├── API_REFERENCE.md         # Endpoint documentation with examples
│   └── SETUP_GUIDE.md           # Step-by-step setup instructions
└── scripts/
    ├── setup_db.py              # Create database tables
    └── colab_llm_setup.py       # Colab notebook reference
```

## Testing

```bash
# Run all 54 tests
pytest backend/tests/ -v

# Run specific test suites
pytest backend/tests/test_stt.py -v    # Speech-to-Text (16 tests)
pytest backend/tests/test_llm.py -v    # LLM + Prompts (11 tests)
pytest backend/tests/test_tts.py -v    # TTS + Full Pipeline (13 tests)
pytest backend/tests/test_rag.py -v    # RAG + Knowledge API (14 tests)
```

## Project Status

- [x] **Week 1:** Environment, database, project scaffold — `v0.0-scaffold`
- [x] **Week 2:** Speech-to-Text (faster-whisper) — `v0.1-stt-working`
- [x] **Week 3:** LLM + Persona prompt (Ollama on Colab) — `v0.2-llm-working`
- [x] **Week 4:** TTS + Full pipeline complete — `v0.3-pipeline-complete`
- [x] **Week 5:** RAG with ChromaDB — `v0.4-rag-working`
- [x] **Week 6:** Frontend UI — `v0.5-frontend-complete`
- [x] **Week 7:** Bug fixes, performance logging, documentation — `v0.9-polished`
- [ ] **Week 8:** Presentation

## Hardware Requirements

| Component | Minimum |
|-----------|---------|
| CPU | Any modern CPU (tested on i3-1115G4) |
| RAM | 8 GB |
| GPU | **Not required** — heavy models run on Google Colab |
| Storage | ~2 GB (for Python packages + Whisper tiny model) |
| Internet | Required for gTTS and Colab connection |

## Author

**Arhaan Khan** — Solo Developer
