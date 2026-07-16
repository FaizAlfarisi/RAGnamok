COMPOSE = $(ENGINE) compose

# Platform detection
ifeq ($(OS),Windows_NT)
ENGINE := $(shell where podman 2>nul && echo podman || echo docker)
VENV_PYTHON := .venv/Scripts/python
VENV_PIP   := .venv/Scripts/pip
VENV_UVICORN := .venv/Scripts/uvicorn
VENV_STREAMLIT := .venv/Scripts/streamlit
SEP        := /
MKDIR      := powershell -Command New-Item -ItemType Directory -Force -Path
CP         := powershell -Command Copy-Item -Path
RM         := powershell -Command Remove-Item -Force -Path
RMDIR      := powershell -Command Remove-Item -Recurse -Force -Path
SETUP_COPY := powershell -Command "if (-not (Test-Path .env)) { Copy-Item -Path backend/.env.example -Destination .env }"
PULL_MODELS := powershell -ExecutionPolicy Bypass -File scripts/pull-ollama-model.ps1
else
ENGINE := $(shell command -v podman >/dev/null 2>&1 && echo podman || echo docker)
VENV_PYTHON := .venv/bin/python
VENV_PIP   := .venv/bin/pip
VENV_UVICORN := .venv/bin/uvicorn
VENV_STREAMLIT := .venv/bin/streamlit
SEP        := /
MKDIR      := mkdir -p
CP         := cp -n
RM         := rm -f
RMDIR      := rm -rf
SETUP_COPY := test -f .env || cp -n backend/.env.example .env
PULL_MODELS := ./scripts/pull-ollama-model.sh
endif

# Ollama model tiers
LIGHT_MODEL       := minicpm-v4.6:latest
DEFAULT_MODEL   := qwen3.5:4b
HIGH_MODEL      := gemma3:12b

.PHONY: setup install install-backend install-frontend up down logs backend-dev frontend-dev migrate-db gpu-up pull-models pull-model-light pull-model-default pull-model-high full clean prune help

.venv:
	python -m venv .venv
	@echo "Virtual environment created."

setup:
	python -c "from pathlib import Path; [p.mkdir(parents=True, exist_ok=True) for p in (Path('backend/data/docs'), Path('backend/data/images'))]"
	$(SETUP_COPY)
	@echo "Setup complete. Run 'make install' to install dependencies (dev mode)."

install: install-backend install-frontend

install-backend: .venv
	$(VENV_PIP) install -r backend$(SEP)requirements.txt

install-frontend: .venv
	$(VENV_PIP) install -r frontend-local$(SEP)requirements.txt

up:
	$(COMPOSE) up -d db ollama

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f db ollama

backend-dev: .venv
	$(VENV_UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend

frontend-dev: .venv
	$(VENV_STREAMLIT) run frontend-local$(SEP)app.py

migrate-db:
	$(COMPOSE) exec -T db psql -U postgres -d ragdb < backend/db/migrations/001_init_schema.sql

gpu-up:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml --profile full up -d

pull-models:
	$(PULL_MODELS) $(MODELS)

pull-model-light:
	$(PULL_MODELS) $(LIGHT_MODEL)

pull-model-default:
	$(PULL_MODELS) $(DEFAULT_MODEL)

pull-model-high:
	$(PULL_MODELS) $(HIGH_MODEL)

full:
	$(COMPOSE) --profile full up -d --build

clean:
	$(RMDIR) .venv
	$(RMDIR) backend$(SEP)data
	@echo "Cleaned."

prune:
	$(ENGINE) system prune --all --force
	@echo "Pruned."

install-test-deps: .venv
	$(VENV_PIP) install -r backend$(SEP)tests$(SEP)requirements-dev.txt

test: .venv
	$(VENV_PYTHON) -m pytest backend$(SEP)tests -v --tb=short

test-unit: .venv
	$(VENV_PYTHON) -m pytest backend$(SEP)tests$(SEP)unit -v --tb=short

test-integration: .venv
	$(VENV_PYTHON) -m pytest backend$(SEP)tests$(SEP)integration -v --tb=short

test-cov: .venv
	$(VENV_PYTHON) -m pytest backend$(SEP)tests -v --tb=short --cov=app --cov-report=term-missing

help:
	@echo "Targets:"
	@echo "  setup            - Create .env and data directories"
	@echo "  install          - Install backend + frontend deps into .venv"
	@echo "  install-test-deps - Install test dependencies"
	@echo "  test             - Run all tests (unit + integration)"
	@echo "  test-unit        - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-cov         - Run all tests with coverage"
	@echo "  up               - Start DB + Ollama containers"
	@echo "  down             - Stop all containers"
	@echo "  logs             - Tail DB + Ollama container logs"
	@echo "  backend-dev      - Start FastAPI dev server (hot reload)"
	@echo "  frontend-dev     - Start Streamlit UI"
	@echo "  migrate-db       - Run DB migrations"
	@echo "  gpu-up           - Start full stack with GPU passthrough"
	@echo "  pull-models      - Pull Ollama models (from .env or MODELS=)"
	@echo "  pull-model-light  - Pull lightweight model (MiniCPM-V 4.6)"
	@echo "  pull-model-default - Pull default model (Qwen3.5:4b)"
	@echo "  pull-model-high  - Pull high-end model (Gemma3:12b)"
	@echo "  full             - Build & launch full Docker stack (db + ollama + backend + frontend)"
	@echo "  clean            - Remove .venv and data dirs"
