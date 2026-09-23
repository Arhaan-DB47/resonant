# Resonant — Step-by-Step Setup Guide

> **Resonant** is a self-hosted AI Digital Twin platform for multilingual personal presence. It captures voice input, transcribes speech with faster-whisper, retrieves contextual persona knowledge via ChromaDB (RAG), generates responses with an LLM (Ollama / Llama 3.1 8B), and synthesizes spoken replies in the persona's voice (gTTS / XTTS).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step-by-Step Installation](#step-by-step-installation)
   - [Step 1: Clone Repository](#step-1-clone-repository)
   - [Step 2: Create & Activate Virtual Environment](#step-2-create--activate-virtual-environment)
   - [Step 3: Install Dependencies](#step-3-install-dependencies)
   - [Step 4: Python 3.13+ Compatibility (audioop-lts)](#step-4-python-313-compatibility-audioop-lts)
   - [Step 5: Create PostgreSQL Database](#step-5-create-postgresql-database)
   - [Step 6: Configure Environment (.env)](#step-6-configure-environment-env)
   - [Step 7: Initialize Database Tables](#step-7-initialize-database-tables)
   - [Step 8: Create Outputs Directory](#step-8-create-outputs-directory)
   - [Step 9: Run the FastAPI Server](#step-9-run-the-fastapi-server)
   - [Step 10: Access the Web UI & API](#step-10-access-the-web-ui--api)
   - [Step 11: Create a Persona](#step-11-create-a-persona)
   - [Step 12: Ingest Knowledge Documents (RAG)](#step-12-ingest-knowledge-documents-rag)
   - [Step 13: Voice Interaction](#step-13-voice-interaction)
3. [Optional: Google Colab LLM Setup (Cloud GPU)](#optional-google-colab-llm-setup)
4. [Running Tests](#running-tests)
5. [Project Structure Overview](#project-structure-overview)
6. [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

## Prerequisites

Before starting, ensure your system has the following installed:

| Tool | Minimum Version | Tested Version | Purpose |
|------|-----------------|----------------|---------|
| **Python** | 3.12+ | 3.14.2 | Backend API runtime & services |
| **PostgreSQL** | 15+ | 18.6 | Relational storage for personas, docs, history |
| **ffmpeg** | Any recent build | 7.x+ | Audio format conversion (16 kHz mono WAV) |
| **Git** | 2.x+ | 2.45+ | Version control |

### Installing Prerequisites

#### 1. Python (3.12 or newer)
- **Windows**: Download from [python.org](https://www.python.org/downloads/) (check *"Add python.exe to PATH"* during installation).
- **macOS**: `brew install python`
- **Linux**: `sudo apt update && sudo apt install -y python3 python3-venv python3-pip`

#### 2. PostgreSQL (15 or newer)
- **Windows**: Download installer from [enterprisedb.com](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads) or use `winget install PostgreSQL.PostgreSQL.18`.
- **macOS**: `brew install postgresql@16 && brew services start postgresql@16`
- **Linux**: `sudo apt install -y postgresql postgresql-contrib && sudo systemctl start postgresql`

#### 3. ffmpeg
- **Windows**:
  ```powershell
  winget install Gyan.FFmpeg
  ```
  *Or download the release build from [ffmpeg.org](https://ffmpeg.org/download.html) and add the `bin` directory to your System PATH.*
- **macOS**:
  ```bash
  brew install ffmpeg
  ```
- **Linux**:
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```
- **Verify installation**:
  ```bash
  ffmpeg -version
  ```

---

## Step-by-Step Installation

### Step 1: Clone Repository

Open your terminal or PowerShell and clone the Resonant repository:

```bash
git clone https://github.com/Arhaan-DB47/resonant.git
cd resonant
```

---

### Step 2: Create & Activate Virtual Environment

Create an isolated virtual environment to manage project dependencies:

**On Windows (PowerShell / Command Prompt):**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

> **Note for Windows PowerShell:** If you see an error saying `running scripts is disabled on this system`, run:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> and re-run `.venv\Scripts\activate`.

**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### Step 3: Install Dependencies

Upgrade pip and install all required Python packages:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 4: Python 3.13+ Compatibility (audioop-lts)

Starting with Python 3.13, the built-in `audioop` module was removed from the standard library (PEP 594). If you are running Python 3.13 or 3.14 (such as 3.14.2), install `audioop-lts` to restore compatibility for audio packages (`pydub`, `gtts`):

```bash
pip install audioop-lts
```

---

### Step 5: Create PostgreSQL Database

Make sure your PostgreSQL server is running. Create a new database called `resonant`:

#### Using psql (CLI):
```bash
psql -U postgres
```
Enter your PostgreSQL password when prompted, then run:
```sql
CREATE DATABASE resonant;
\q
```

#### Using pgAdmin (GUI):
1. Open **pgAdmin** and connect to your server.
2. Right-click **Databases** → **Create** → **Database...**.
3. Set the database name to `resonant` and click **Save**.

---

### Step 6: Configure Environment (.env)

Copy the sample environment file to create your `.env` configuration:

**On Windows:**
```powershell
copy .env.example .env
```

**On Linux / macOS:**
```bash
cp .env.example .env
```

Open `.env` in your text editor and ensure the values match your local setup:

```env
# === Database ===
# Replace YOUR_PASSWORD with your actual PostgreSQL postgres password
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/resonant

# === LLM & TTS Endpoints ===
# Default points to local Ollama. For Google Colab, see Colab section below.
COLAB_LLM_URL=http://localhost:11434
COLAB_TTS_URL=http://localhost:5002

# === Local STT Model ===
WHISPER_MODEL_SIZE=tiny

# === Application Settings ===
DEFAULT_LANGUAGE=en
LOG_LEVEL=DEBUG
OUTPUT_DIR=outputs
```

---

### Step 7: Initialize Database Tables

Run the following command to create all database tables (`personas`, `conversations`, `knowledge_docs`):

```bash
python -c "from backend.database import engine; from backend.models.db_models import Base; Base.metadata.create_all(engine)"
```

Alternatively, you can run the helper script:

```bash
python scripts/setup_db.py
```

Expected output:
```text
Creating database tables...
  Database: postgresql://postgres:***@localhost:5432/resonant

  [OK] Table 'personas' ready
  [OK] Table 'conversations' ready
  [OK] Table 'knowledge_docs' ready

Done! All tables created successfully.
```

---

### Step 8: Create Outputs Directory

Ensure the audio output directory exists for temporary and synthesized audio recordings:

**On Windows:**
```powershell
mkdir outputs
```

**On Linux / macOS:**
```bash
mkdir -p outputs
```

---

### Step 9: Run the FastAPI Server

Start the development server with live reload:

```bash
uvicorn backend.main:app --reload
```

You should see log output similar to:
```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Starting Resonant API server...
INFO:       Whisper model: tiny
INFO:       LLM endpoint: http://localhost:11434
INFO:       Database: postgresql://postgres:***@localhost:5432/resonant
INFO:     Server ready!
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

### Step 10: Access the Web UI & API

Open your web browser and navigate to:

- **Frontend Web UI**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### Step 11: Create a Persona

1. On the web dashboard, locate the persona selector sidebar.
2. Click the **`+ New`** button.
3. Fill in the persona details:
   - **Name**: e.g., `Prof. Alan Turing`
   - **Bio & Style**: e.g., `You are Alan Turing, British mathematician and computer scientist. You speak thoughtfully, clearly, and with analytical precision.`
   - **Default Language**: `en`
4. Click **Save Persona**.

---

### Step 12: Ingest Knowledge Documents (RAG)

1. Select your newly created persona.
2. Click the **`Upload Doc`** button.
3. Choose a `.txt`, `.md`, or `.pdf` file with reference material, notes, or essays.
4. The system will chunk the text, compute vector embeddings, and store them in the local ChromaDB collection associated with that persona.

---

### Step 13: Voice Interaction

1. Allow your browser microphone permissions when prompted.
2. **Hold the Microphone button** to record your voice question or prompt.
3. **Release the button** to stop recording and send the audio to `/api/process`.
4. The pipeline executes:
   - **STT**: Transcribes your voice query using `faster-whisper`.
   - **RAG**: Queries ChromaDB for context relevant to your question.
   - **LLM**: Generates a persona-aligned answer.
   - **TTS**: Converts the text reply to an audio waveform.
5. The audio automatically plays in your browser, and the conversation is recorded in the chat history.

---

## Optional: Google Colab LLM Setup

If your local computer has limited GPU or RAM, you can run Ollama with the **Llama 3.1 8B** model on a **free Google Colab T4 GPU** and tunnel the connection to your local machine.

### Colab Notebook Instructions

1. Go to [Google Colab](https://colab.research.google.com/) and create a **New Notebook**.
2. Switch to GPU runtime: **Runtime** → **Change runtime type** → select **T4 GPU** → **Save**.
3. Run the following cells in Colab:

#### Cell 1: Install `zstd` & Ollama, then start server
```bash
!apt-get install -y zstd
!curl -fsSL https://ollama.com/install.sh | sh
!OLLAMA_ORIGINS="*" OLLAMA_HOST="0.0.0.0" nohup ollama serve > ollama.log 2>&1 &
```

#### Cell 2: Pull the Llama 3.1 8B model
```bash
!ollama pull llama3.1:8b
```

#### Cell 3: Install and start Cloudflare Tunnel (`cloudflared`)
```bash
!wget -q -nc https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
!dpkg -i cloudflared-linux-amd64.deb
!nohup cloudflared tunnel --url http://localhost:11434 --logfile cloudflared.log 2>&1 &
```

#### Cell 4: Extract the public tunnel URL
```python
import time, re

time.sleep(3)
with open("cloudflared.log") as f:
    log_content = f.read()
    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", log_content)

if match:
    public_url = match.group(0)
    print("=" * 60)
    print(f"YOUR PUBLIC COLAB LLM URL: {public_url}")
    print("=" * 60)
    print(f"\nUpdate your local .env file:")
    print(f"COLAB_LLM_URL={public_url}")
else:
    print("Tunnel URL not found yet. Check cloudflared.log:")
    print(log_content[-500:])
```

#### Cell 5: Keep the notebook session active
```python
import time
while True:
    time.sleep(60)
    print(".", end="", flush=True)
```

4. Copy the generated `https://xxxx.trycloudflare.com` URL into your local `.env`:
   ```env
   COLAB_LLM_URL=https://your-tunnel-subdomain.trycloudflare.com
   ```
5. Restart your local FastAPI server to apply the updated endpoint.

---

## Running Tests

Resonant includes an automated test suite covering STT, LLM services, TTS synthesis, RAG vector retrieval, and pipeline integration.

Run all tests from the repository root:

```bash
pytest backend/tests/ -v
```

> **Current status:** 54 passing tests.

### Running Specific Test Suites

```bash
# STT (faster-whisper transcription & audio normalization)
pytest backend/tests/test_stt.py -v

# LLM (Prompt templates, Ollama client & fallback mode)
pytest backend/tests/test_llm.py -v

# TTS (gTTS synthesis & pipeline audio generation)
pytest backend/tests/test_tts.py -v

# RAG (ChromaDB vector store & document chunking)
pytest backend/tests/test_rag.py -v
```

---

## Project Structure Overview

```
resonant/
├── backend/                  # FastAPI backend server
│   ├── main.py               # Application entry point & lifespan setup
│   ├── config.py             # Pydantic environment configuration
│   ├── database.py           # PostgreSQL SQLAlchemy engine & sessions
│   ├── models/
│   │   ├── db_models.py      # SQLAlchemy ORM schemas (Persona, Conversation, Doc)
│   │   └── schemas.py        # Pydantic request / response schemas
│   ├── routes/
│   │   ├── health.py         # GET /api/health
│   │   ├── process.py        # POST /api/process (Full voice-to-voice pipeline)
│   │   ├── personas.py       # CRUD endpoints for digital personas
│   │   ├── conversations.py  # Conversation history management
│   │   └── knowledge.py      # Document upload and RAG indexing
│   ├── services/
│   │   ├── stt_service.py    # Speech-to-Text (faster-whisper)
│   │   ├── llm_service.py    # LLM inference client & fallback handler
│   │   ├── tts_service.py    # Text-to-Speech synthesis (gTTS / XTTS)
│   │   └── rag_service.py    # ChromaDB RAG retrieval service
│   ├── prompts/
│   │   ├── system_prompt.yaml# Persona prompt template definition
│   │   └── prompt_loader.py  # Prompt formatter with guardrails & constraints
│   ├── utils/
│   │   ├── audio_utils.py    # Audio format converter (ffmpeg wrapper)
│   │   └── logger.py         # Structured logging (loguru)
│   └── tests/                # Automated pytest suite (54 tests)
├── frontend/                 # Clean, responsive web interface
│   ├── index.html            # Main single-page interface
│   ├── css/                  # Styling & design system
│   └── js/                   # Audio recording, API calls, chat rendering
├── rag/                      # Document ingestion & vector indexing
│   ├── ingest.py             # Document parser, chunker, and embedding generator
│   └── chroma_data/          # Persistent ChromaDB vector database directory
├── outputs/                  # Ephemeral audio files generated by TTS pipeline
├── scripts/                  # Utilities for DB migration and Colab hosting
└── docs/                     # Project documentation and setup guides
```

---

## Troubleshooting Common Issues

### 1. `ModuleNotFoundError: No module named 'audioop'`
- **Cause**: Python 3.13 and Python 3.14 removed the legacy `audioop` module from the standard library.
- **Solution**: Install the drop-in replacement package:
  ```bash
  pip install audioop-lts
  ```

### 2. `ffmpeg not found` or `FileNotFoundError` during audio conversion
- **Cause**: `ffmpeg` is not installed or its binary directory is not on your system's `PATH`.
- **Solution**:
  - Download and install ffmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) or run:
    - **Windows**: `winget install Gyan.FFmpeg`
    - **macOS**: `brew install ffmpeg`
    - **Linux**: `sudo apt install -y ffmpeg`
  - Restart your terminal after installation and verify with:
    ```bash
    ffmpeg -version
    ```

### 3. Database connection refused (`Connection refused` or `Is PostgreSQL running?`)
- **Cause**: The PostgreSQL service is stopped or `.env` credentials are incorrect.
- **Solution**:
  - Verify that the PostgreSQL service is active:
    - **Windows**: Open `services.msc` and check `postgresql-x64-18` (or run `net start postgresql-x64-18` as Administrator).
    - **Linux**: `sudo systemctl status postgresql` (start with `sudo systemctl start postgresql`).
    - **macOS**: `brew services list` (start with `brew services start postgresql`).
  - Verify that the database exists:
    ```bash
    psql -U postgres -c "SELECT datname FROM pg_database WHERE datname='resonant';"
    ```
  - Check your password and port in `.env`:
    ```env
    DATABASE_URL=postgresql://postgres:YOUR_ACTUAL_PASSWORD@localhost:5432/resonant
    ```

### 4. LLM is running in fallback mode
- **Cause**: The backend cannot reach the Ollama service at `COLAB_LLM_URL` within the 3-second connection timeout.
- **Symptom**: Responses are prefixed with `[Resonant Fallback Mode]` or `/api/health` reports `"llm_connected": false`.
- **Solution**:
  - If running locally: Ensure Ollama is installed and running (`ollama serve` and `ollama run llama3.1:8b`).
  - If using Google Colab: Ensure the Colab notebook is active, Ollama is running, and the active `cloudflared` tunnel URL matches `COLAB_LLM_URL` in `.env`.
  - Check `/api/health` in your browser to verify connectivity.
