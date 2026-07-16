import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.db.connection import async_session
from app.db.crud import (
    delete_chunks_by_doc_id,
    delete_document,
    get_active_task_for_doc,
    get_chunk_ids_for_doc,
    get_document,
    get_task,
    insert_task,
    list_documents,
    toggle_document,
    update_document_status,
    update_task,
)
from app.schemas.models import (
    DeleteResponse,
    DocumentResponse,
    IndexResponse,
    ToggleResponse,
)
from app.utils.file_handler import get_uploaded_file_path
from app.utils.validators import valid_uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

from app.routers.upload import _processing_tasks, _process_pdf
from app.config import settings

UPLOAD_DIR = settings.upload_dir


@router.get("", response_model=list[DocumentResponse])
async def list_docs(limit: int = 20, offset: int = 0):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    async with async_session() as session:
        docs = await list_documents(session, limit=limit, offset=offset)
    return docs


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_doc(doc_id: str):
    if not valid_uuid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    async with async_session() as session:
        doc = await get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_doc(doc_id: str):
    if not valid_uuid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    # Cancel any active processing first
    async with async_session() as session:
        active = await get_active_task_for_doc(session, doc_id)
    if active and active["task_id"] in _processing_tasks:
        _processing_tasks[active["task_id"]].cancel()

    async with async_session() as session:
        ok = await delete_document(session, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clean up associated images
    async with async_session() as session:
        chunk_ids = await get_chunk_ids_for_doc(session, doc_id)
    from app.utils.file_handler import IMAGE_DIR
    for cid in chunk_ids:
        img_path = IMAGE_DIR / f"{cid}.jpg"
        try:
            img_path.unlink(missing_ok=True)
        except OSError:
            pass

    logger.info("Deleted document: %s", doc_id)
    return {"message": "Document deleted", "document_id": doc_id}


@router.post("/{doc_id}/index", response_model=IndexResponse)
async def index_document(doc_id: str):
    if not valid_uuid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    async with async_session() as session:
        doc = await get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["status"] == "processing":
        raise HTTPException(status_code=409, detail="Document is already being indexed")
    if doc["status"] != "uploaded":
        # Re-index: clean existing chunks first
        async with async_session() as session:
            await delete_chunks_by_doc_id(session, doc_id)

    filename = doc["filename"]
    file_path = get_uploaded_file_path(filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=400, detail="Uploaded file not found")

    task_id = str(uuid.uuid4())
    async with async_session() as session:
        await insert_task(session, task_id, filename, doc_id)
        await update_document_status(session, doc_id, "processing")

    task = asyncio.create_task(
        _process_pdf(task_id, doc_id, str(file_path), filename)
    )
    _processing_tasks[task_id] = task

    return {
        "task_id": task_id,
        "message": "Indexing started",
        "doc_id": doc_id,
    }


@router.post("/{doc_id}/toggle", response_model=ToggleResponse)
async def toggle_doc(doc_id: str):
    if not valid_uuid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    async with async_session() as session:
        new_val = await toggle_document(session, doc_id)
    if new_val is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"enabled": new_val, "doc_id": doc_id}
