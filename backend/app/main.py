import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import platform

_POPPLER_BIN = "pdftoppm.exe" if platform.system() == "Windows" else "pdftoppm"
_POPPLER_ENV = os.environ.get("POPPLER_PATH")
if _POPPLER_ENV:
    if Path(_POPPLER_ENV, _POPPLER_BIN).exists():
        os.environ["PATH"] = _POPPLER_ENV + os.pathsep + os.environ["PATH"]
elif platform.system() == "Windows":
    for _root in [os.path.expandvars(r"%LOCALAPPDATA%\poppler"),
                  os.path.expandvars(r"%ProgramData%\chocolatey\lib\poppler")]:
        _root_p = Path(_root)
        if _root_p.is_dir():
            for _sub in _root_p.rglob(_POPPLER_BIN):
                os.environ["PATH"] = str(_sub.parent) + os.pathsep + os.environ["PATH"]
                break

import logging

from app.config import settings
from app.db.connection import engine, init_db
from app.routers import chat, chat_sessions, diagnose, documents, health, tasks, upload
from app.utils.file_handler import ensure_dirs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.db_password in ("change-me", "password"):
        logger.warning(
            "Database password is set to default. "
            "Set DB_PASSWORD in backend/.env or .env to a secure value."
        )
    ensure_dirs()
    await init_db()
    yield
    from app.routers.upload import _processing_tasks
    if _processing_tasks:
        logger.warning(
            "Server shutting down with %d active tasks", len(_processing_tasks)
        )
    await engine.dispose()


app = FastAPI(
    title="RAGnamok API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

image_dir = Path(settings.image_dir)
image_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/api/v1/images",
    StaticFiles(directory=str(image_dir)),
    name="images",
)

app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(chat_sessions.router)
app.include_router(tasks.router)
app.include_router(documents.router)
app.include_router(health.router)
app.include_router(diagnose.router)
