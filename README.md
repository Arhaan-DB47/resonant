# Resonant

> **A Self-Hosted AI Digital Twin for Multilingual Personal Presence**

Resonant creates an AI "digital twin" of a real person — a voice-powered assistant that listens to your question, thinks like the real person using a locally-run LLM grounded in their actual documents (RAG), and speaks back in their voice, in any language.

## Architecture

```
User Audio → Local Whisper STT → RAG (ChromaDB) → Local LLM (Ollama) → TTS → Audio Response
                                       ↑
                                  PostgreSQL
                              (personas, history,
                               knowledge docs)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) |
| STT | faster-whisper (local, CPU) |
| LLM | Ollama + Llama 3.1 (Google Colab GPU) |
| TTS | gTTS (local) / Coqui XTTS (Colab GPU) |
| RAG | ChromaDB + sentence-transformers |
| Database | PostgreSQL + SQLAlchemy |
| Frontend | Vanilla HTML/CSS/JS |

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
cp .env.example .env
# Edit .env with your database credentials

# 5. Create database tables
python scripts/setup_db.py

# 6. Run the server
uvicorn backend.main:app --reload

# 7. Open in browser
# API docs: http://localhost:8000/docs
# Frontend: http://localhost:8000/
```

## API Endpoints

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| `GET` | `/api/health` | Server health check | ✅ |
| `POST` | `/api/process` | Main pipeline: audio in → audio out | 🔧 Skeleton |
| `GET` | `/api/personas` | List all personas | ✅ |
| `POST` | `/api/personas` | Create a persona | ✅ |
| `GET` | `/api/personas/{id}` | Get a persona | ✅ |
| `PUT` | `/api/personas/{id}` | Update a persona | ✅ |
| `DELETE` | `/api/personas/{id}` | Delete a persona | ✅ |

## Project Status

- [x] Week 1: Environment, database, project scaffold
- [ ] Week 2: Speech-to-Text (faster-whisper)
- [ ] Week 3: LLM + Persona prompt (Ollama on Colab)
- [ ] Week 4: TTS + Full pipeline
- [ ] Week 5: RAG with ChromaDB
- [ ] Week 6: Frontend UI
- [ ] Week 7: Voice cloning + polish
- [ ] Week 8: Presentation

## Author

**Arhaan Khan** — Solo Developer
