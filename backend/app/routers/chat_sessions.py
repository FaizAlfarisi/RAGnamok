import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db.connection import async_session
from app.db.crud import (
    create_session,
    delete_session,
    get_messages,
    list_sessions,
    update_session_title,
)
from app.schemas.models import (
    ChatHistoryRequest,
    ChatHistoryResponse,
    MessageResponse,
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
)
from app.services.chat_service import handle_chat_message
from app.utils.validators import valid_uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# --- Sessions ---


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_chat_session(body: SessionCreateRequest):
    async with async_session() as session:
        doc = await create_session(session, body.title)
        return {"id": doc["id"], "title": doc["title"], "message_count": 0}


@router.get("/sessions", response_model=list[SessionResponse])
async def list_chat_sessions():
    async with async_session() as session:
        return await list_sessions(session)


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_chat_session(session_id: str, body: SessionUpdateRequest):
    if not valid_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    async with async_session() as session:
        ok = await update_session_title(session, session_id, body.title)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        docs = await list_sessions(session)
        for d in docs:
            if d["id"] == session_id:
                return d
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_chat_session(session_id: str):
    if not valid_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    async with async_session() as session:
        ok = await delete_session(session, session_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")


# --- Messages ---


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(session_id: str, limit: int = 50):
    if not valid_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    limit = max(1, min(limit, 200))
    async with async_session() as session:
        msgs = await get_messages(session, session_id, limit)
    return msgs


@router.post(
    "/sessions/{session_id}/messages", response_model=ChatHistoryResponse
)
async def send_message(session_id: str, body: ChatHistoryRequest):
    if not valid_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    top_k = max(1, min(body.top_k, 50))
    async with async_session() as db_session:
        sessions = await list_sessions(db_session)
        if not any(s["id"] == session_id for s in sessions):
            raise HTTPException(status_code=404, detail="Session not found")
        result = await handle_chat_message(
            db_session,
            session_id,
            body.query,
            top_k=top_k,
            history_depth=settings.chat_history_depth,
        )
    return result
