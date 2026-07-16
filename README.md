# RAGnamok — Local Privacy-First Multi-Vector RAG

**Na**tive **Mo**dule for **O**n-premise **K**nowledge.

*Absolute Privacy. Purely On-Premise RAG.*

RAGnamok ingests multi-modal PDF documents (text, tables, images), indexes them via a summary-based multi-vector retrieval pipeline, and surfaces answers through a natural language chat interface — all running 100% locally with zero external API calls.

## Features

- **Multi-modal ingestion** — extracts text, tables (HTML), and images (JPEG) from PDF documents using Unstructured
- **Local LLM inference** — uses Ollama — no data leaves your machine
- **Multi-vector retrieval** — generates summaries of each element, embeds them with Ollama (`blaifa/multilingual-e5-large-instruct:Q8_0`), and stores both summaries and originals in PostgreSQL/pgvector
- **Async PDF processing** — upload returns immediately with a `task_id`; background processing with progress polling
- **Streamlit chat UI** — upload PDFs and ask questions through a clean web interface
- **Three model tiers** — choose your LLM by hardware: Lightweight, Default, High-End
- **Fully configurable via environment variables** — LLM models, chunking params, DB credentials, all customizable

## Quick Start

```bash
# Prerequisites: Python ≥ 3.12, Docker/Podman
make setup           # Create .env and data directories
make up              # Start PostgreSQL + Ollama containers
make pull-models     # Pull LLM & embedding models into Ollama
make full            # Build & launch full stack (backend + frontend)
```

Open **http://localhost:8501**, upload a PDF, and start asking questions.

> ⏳ First-time startup pulls Docker images, builds the backend (~8-10 min), and pulls the LLM + embedding models. Allow 10-15 minutes.

### What each step does

| Command | What happens |
|---|---|
| `make setup` | Creates `backend/data/` dirs and `.env` with defaults |
| `make up` | Starts `db` (PostgreSQL + pgvector) and `ollama` containers |
| `make pull-models` | Pulls the configured LLM (from `.env`) + embedding model into Ollama |
| `make full` | Builds & runs the full stack: `docker compose --profile full up -d --build` |

### GPU Passthrough

```bash
make gpu-up   # Starts full stack with Nvidia GPU passthrough
```

## Model Choice Guide

RAGnamok supports three model tiers. Pick the one that fits your hardware.

| Tier | Model | Params | Size | When to use |
|---|---|---|---|---|
| **Lightweight** | MiniCPM-V 4.6 | 1B | 1.6 GB | Image-heavy PDFs, low-resource machines, or first-time test |
| **Default** (balanced) | Qwen3.5:4b | 4B | ~2.5 GB | General-purpose text RAG, best speed/quality trade-off |
| **High-End** (best quality) | Gemma3:12b | 12B | ~8 GB | Complex reasoning, dense academic PDFs, high-accuracy needs |

Switch between tiers in one command:

```bash
make pull-model-light     # Switch to MiniCPM-V (lightweight)
make pull-model-default   # Switch to Qwen3.5:4b (default)
make pull-model-high      # Switch to Gemma3:12b (best quality)
```

Each command pulls the model **and** updates `.env` so the backend uses it on restart. Run `make full` to rebuild the container with the new model — or set `GENERATION_MODEL` and `SUMMARIZATION_MODEL` manually in `.env` for fine-grained control.

### Think-model caveat

Qwen3.5 and other "think" models emit a long chain-of-thought (hundreds of blank tokens) before the actual content. If the generation timeout is too tight, the model exhausts its token budget on thinking and returns an empty response. If you hit empty responses:
- Raise `num_predict` (default: no limit — safe unless overridden)
- Increase the generation timeout in `docker-compose.yml`: set `OLLAMA_NUM_PARALLEL=1` and ensure no reverse proxy cuts the connection before ~300s
- Switch to a non-think model (Gemma3) which does not have this behavior

## Makefile Reference

```
make help                Show all targets
make setup               Create .env and data directories
make install             Install backend + frontend deps into .venv
make up                  Start DB + Ollama containers
make down                Stop all containers
make logs                Tail DB + Ollama container logs
make pull-models         Pull Ollama models (from .env or MODELS=)
make pull-model-light    Pull lightweight model (MiniCPM-V 4.6)
make pull-model-default  Pull default model (Qwen3.5:4b)
make pull-model-high     Pull high-end model (Gemma3:12b)
make full                Build & launch full Docker stack
make gpu-up              Start full stack with GPU passthrough
make backend-dev         Start FastAPI dev server (hot reload)
make frontend-dev        Start Streamlit UI
make migrate-db          Run DB migrations inside the db container
make test                Run all tests (unit + integration)
make clean               Remove .venv and backend/data directories
```

## Env Vars

Config lives in `.env` (created by `make setup` from `backend/.env.example`).
All variables have sensible defaults — only override what differs.

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `ragdb` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `change-me` | Database password |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `SUMMARIZATION_MODEL` | `qwen3.5:4b` | LLM for summarization |
| `GENERATION_MODEL` | `qwen3.5:4b` | LLM for answer generation |
| `SUMMARIZATION_TEMPERATURE` | `0.3` | Temperature for summarization LLM |
| `GENERATION_TEMPERATURE` | `0.1` | Temperature for generation LLM |
| `EMBEDDING_MODEL_NAME` | `blaifa/multilingual-e5-large-instruct:Q8_0` | Embedding model |
| `CORS_ORIGINS` | `http://localhost:8501,http://127.0.0.1:8501` | Comma-separated allowed origins |
| `MAX_CONCURRENCY` | `3` | Max parallel LLM calls |
| `MAX_CHARACTERS` | `3000` | Max chars per chunk |
| `NEW_AFTER_N_CHARS` | `2500` | Chunking: start new chunk after N chars |
| `COMBINE_TEXT_UNDER_N_CHARS` | `500` | Chunking: combine elements under N chars |
| `MIN_CHUNK_SIZE_FOR_MERGE` | `200` | Post-process: merge orphaned chunks smaller than this |
| `TOP_K_RETRIEVAL` | `5` | Chunks retrieved per query |
| `CHAT_HISTORY_DEPTH` | `6` | Number of past Q&A pairs injected as context |

## For Developers

If you want to run the backend natively (hot reload) instead of in Docker:

```bash
make install        # Install deps into .venv
make backend-dev    # Terminal 1: FastAPI on :8000
make frontend-dev   # Terminal 2: Streamlit on :8501
```

### Running tests

```bash
make install-test-deps  # Install pytest, httpx, etc.
make test               # All tests (unit + integration)
make test-unit          # Unit tests only
make test-cov           # With coverage report
```

Tests hit real infrastructure (PostgreSQL, Ollama). Requires `docker compose up -d db ollama`.

## Architecture

```
┌─────────────────────────────────────────┐
│          Streamlit Frontend             │
│    Upload PDF  |  Chat Interface        │
└──────────────────┬──────────────────────┘
                   │ REST API (HTTP)
┌──────────────────┴──────────────────────┐
│           Backend (FastAPI)             │
│  ┌──────────────────────────────────┐   │
│  │          RAG Pipeline            │   │
│  │  Parse → Summarize → Embed →     │   │
│  │         Retrieve → Generate      │   │
│  └──────────────────────────────────┘   │
│  Upload | Chat | Task Status | Health   │
└───────────┬──────────────┬──────────────┘
            │              │
     ┌──────┴──────┐  ┌────┴───────┐
     │  PostgreSQL │  │   Ollama   │
     │  + pgvector │  │  (LLMs +   │
     │  (vectors + │  │   vision)  │
     │   docstore) │  └────────────┘
     └─────────────┘
```

```
RAGnamok/
├── Makefile                         # Development workflow automation
├── .env                             # Single config file (auto-created)
├── docker-compose.yml               # Docker orchestration
├── docker-compose.gpu.yml           # GPU passthrough override
├── scripts/
│   ├── pull-ollama-model.sh         # Pull models into Ollama (Linux/macOS)
│   └── pull-ollama-model.ps1        # PowerShell version (Windows)
├── backend/
│   ├── .env.example                 # Template for all configurable vars
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── config.py                # pydantic-settings
│   │   ├── db/                      # connection, crud, migrations
│   │   ├── routers/                 # API endpoints
│   │   ├── services/                # parser, embedder, summarizer, retriever, generator
│   │   ├── schemas/                 # Pydantic models
│   │   └── utils/                   # file_handler, image_formatter, model_checker
│   └── db/migrations/
│       └── 001_init_schema.sql      # pgvector schema + HNSW index
├── frontend-local/
│   ├── app.py                       # Streamlit UI
│   ├── Dockerfile
│   └── requirements.txt
```

## API Overview

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness check |
| `POST` | `/api/v1/upload` | Upload PDF (returns `task_id`) |
| `GET` | `/api/v1/tasks/{task_id}` | Poll processing status |
| `POST` | `/api/v1/tasks/{task_id}/cancel` | Cancel a running task |
| `GET` | `/api/v1/tasks/active-for-doc/{doc_id}` | Get active task for a document |
| `GET` | `/api/v1/documents` | List documents |
| `DELETE` | `/api/v1/documents/{doc_id}` | Delete a document |
| `POST` | `/api/v1/documents/{doc_id}/toggle` | Enable/disable a document |
| `POST` | `/api/v1/chat/sessions` | Create a chat session |
| `GET` | `/api/v1/chat/sessions` | List chat sessions |
| `PATCH` | `/api/v1/chat/sessions/{session_id}` | Rename a session |
| `DELETE` | `/api/v1/chat/sessions/{session_id}` | Delete a session |
| `GET` | `/api/v1/chat/sessions/{session_id}/messages` | Get message history |
| `POST` | `/api/v1/chat/sessions/{session_id}/messages` | Send a message and get answer |
| `POST` | `/api/v1/chat` | Ask a question (no session) |

Full API spec at `http://localhost:8000/docs` (Swagger UI) when running.

## Design Decisions

| Decision | Rationale |
|---|---|
| **Embeddings as `vector(1024)`** | Native pgvector type with HNSW indexing via asyncpg codec registration |
| **HNSW index** | Faster and more accurate than IVFFlat for expected dataset size |
| **Images stored as base64 in DB** | Simplifies retrieval path — no separate image loading step needed |
| **Background task processing** | PDF ingestion can take several minutes; returning `task_id` immediately prevents HTTP timeout |
| **`by_title` chunking + post-process merge** | Table isolation in Unstructured creates orphaned tiny chunks; merging them post-hoc recovers context |
| **Async SQLAlchemy + asyncpg** | Non-blocking database operations align with FastAPI's async nature |
| **Environment variables everywhere** | Every tunable parameter is configurable via `.env` — no hardcoded values |
| **No ORM models** | Raw SQL via `sqlalchemy.text()`; embedding cast uses `CAST(:val AS vector)` with JSON string |
| **Soft-delete for documents** | `deleted_at` column; `vector_search` filters `WHERE d.deleted_at IS NULL` |
| **CPU-only torch** | Dockerfile installs from `https://download.pytorch.org/whl/cpu`; `opencv-python-headless` replaces `opencv-python` |
| **Tesseract OCR with Indonesian** | `tesseract-ocr-ind` for Indonesian language text extraction in PDFs |

## Docker Tips

### Pruning images

Default `docker image prune -f` (or `podman image prune -f`) does **not** remove dangling build layers. Use the full prune to reclaim space:

```bash
# Remove all unused images, containers, and networks
make prune
# Equivalent to:
docker system prune --all --force
# or:
podman system prune --all --force
```

Dangling build layers from repeated `make full` runs accumulate. Run `make prune` periodically if you rebuild frequently.

### GPU acceleration

```bash
make gpu-up
```

Uses `docker-compose.gpu.yml` with Nvidia container toolkit. Requires `nvidia-driver` and `nvidia-container-toolkit` installed on the host.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Empty response from chat | Think-model exhausted token budget on chain-of-thought | Raise `num_predict` or switch to Gemma3 (no think tokens). Increase backend timeout. |
| `Ollama not ready` | Container still starting | Run `make up` and wait 30s, then retry `make pull-models` |
| `pdftoppm.exe` not found (Windows) | Poppler not in PATH | Install Poppler via Chocolatey: `choco install poppler`. Or place `pdftoppm.exe` in `%LOCALAPPDATA%\poppler` |
| Upload fails with large PDF | File exceeds 50 MB limit | Split the PDF or raise the limit in config |
| `make full` rebuild takes forever | Docker layers not cached | Only rebuilds when Dockerfile or requirements.change. First build is slow (~8-10 min, torch dependency). |
| Document shows but returns no results | Document was soft-deleted (`deleted_at` set) | Toggle visibility via `POST /api/v1/documents/{doc_id}/toggle` |
