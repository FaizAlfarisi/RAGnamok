import logging

from fastapi import APIRouter, HTTPException

from app.db.connection import async_session
from app.db.crud import get_active_task_for_doc, get_task
from app.utils.validators import valid_uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["tasks"])

from app.routers.upload import _processing_tasks


@router.get("/tasks/active-for-doc/{doc_id}")
async def get_active_task_for_doc_endpoint(doc_id: str):
    if not valid_uuid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    async with async_session() as session:
        task = await get_active_task_for_doc(session, doc_id)
    if not task:
        raise HTTPException(status_code=404, detail="No active task for this document")
    return task


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    if not valid_uuid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    async with async_session() as session:
        task = await get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    if not valid_uuid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    async with async_session() as session:
        task = await get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Task already {task['status']}",
        )
    if task_id in _processing_tasks:
        _processing_tasks[task_id].cancel()
        return {"message": "Task cancellation requested", "task_id": task_id}
    raise HTTPException(
        status_code=500, detail="Task is not being tracked by this server"
    )
