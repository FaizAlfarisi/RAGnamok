import asyncio
import base64
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.db.connection import async_session
from app.db.crud import (
    delete_chunks_by_doc_id,
    get_task,
    insert_chunks_batch,
    insert_document,
    insert_task,
    update_document_status,
    update_task,
)
from app.services.embedder import embed_batch
from app.services.parser import parse_pdf
from app.services.summarizer import (
    summarize_images,
    summarize_tables,
    summarize_texts,
)
from app.utils.file_handler import ensure_dirs, save_image, save_uploaded_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["upload"])

MAX_FILE_SIZE = 50 * 1024 * 1024

# Track active asyncio tasks for cancellation
_processing_tasks: dict[str, asyncio.Task] = {}


async def _process_pdf(task_id: str, doc_id: str, file_path: str, filename: str):
    async with async_session() as session:
        try:
            await update_task(session, task_id, "processing", "Parsing PDF...")
            await session.commit()

            loop = asyncio.get_running_loop()
            parsed = await loop.run_in_executor(None, parse_pdf, file_path)

            await update_task(
                session, task_id, "processing", "Generating summaries..."
            )
            await session.commit()

            text_summaries = await summarize_texts(parsed["texts"])
            table_summaries = await summarize_tables(parsed["tables"])
            image_summaries = await summarize_images([img["base64"] for img in parsed["images"]])

            await update_task(
                session, task_id, "processing", "Generating embeddings..."
            )
            await session.commit()

            all_summaries = text_summaries + table_summaries + image_summaries
            all_embeddings = await embed_batch(all_summaries)

            chunks = []
            idx = 0

            for text_el, summary in zip(parsed["texts"], text_summaries):
                chunks.append(
                    {
                        "chunk_id": str(uuid.uuid4()),
                        "element_type": "CompositeElement",
                        "content": text_el.text,
                        "page_number": getattr(text_el.metadata, "page_number", 1),
                        "summary": summary,
                        "embedding": all_embeddings[idx],
                    }
                )
                idx += 1

            for table_el, summary in zip(parsed["tables"], table_summaries):
                chunks.append(
                    {
                        "chunk_id": str(uuid.uuid4()),
                        "element_type": "Table",
                        "content": table_el.metadata.text_as_html,
                        "page_number": getattr(table_el.metadata, "page_number", 1),
                        "summary": summary,
                        "embedding": all_embeddings[idx],
                    }
                )
                idx += 1

            for img_dict, summary in zip(parsed["images"], image_summaries):
                chunk_id = str(uuid.uuid4())
                img_bytes = base64.b64decode(img_dict["base64"])
                save_image(chunk_id, img_bytes)
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "element_type": "Image",
                        "content": chunk_id,
                        "page_number": img_dict["page_number"],
                        "summary": summary,
                        "embedding": all_embeddings[idx],
                    }
                )
                idx += 1

            await insert_chunks_batch(session, doc_id, chunks)
            await update_task(session, task_id, "completed", "Done")
            await update_document_status(
                session, doc_id, "completed", enabled=True
            )
            await session.commit()

            logger.info("PDF processed: %s (doc: %s)", filename, doc_id)

        except asyncio.CancelledError:
            logger.info("Task cancelled: %s (doc: %s)", task_id, doc_id)
            await delete_chunks_by_doc_id(session, doc_id)
            await update_document_status(session, doc_id, "uploaded", enabled=False)
            await update_task(session, task_id, "cancelled", "Cancelled")
            await session.commit()
            try:
                os.remove(file_path)
            except OSError:
                pass
            raise

        except Exception as e:
            logger.error("Failed to process PDF %s: %s", filename, e)
            try:
                os.remove(file_path)
            except OSError:
                pass
            await delete_chunks_by_doc_id(session, doc_id)
            await update_document_status(session, doc_id, "failed", enabled=False)
            await update_task(
                session, task_id, "failed", "PDF processing failed", "PDF processing failed"
            )
            await session.commit()
        finally:
            _processing_tasks.pop(task_id, None)


@router.post("/upload", status_code=201)
async def upload_pdf(
    file: UploadFile = File(...),
    auto_index: bool = True,
):
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail="File too large (max 50 MB)"
        )
    if not content[:4] == b"%PDF":
        raise HTTPException(status_code=400, detail="File is not a valid PDF (missing PDF header)")

    ensure_dirs()
    filename = Path(file.filename).name if file.filename else "upload.pdf"
    file_path = save_uploaded_file(filename, content)

    async with async_session() as session:
        doc_id = await insert_document(session, filename)

    if auto_index:
        task_id = str(uuid.uuid4())
        async with async_session() as session:
            await insert_task(session, task_id, filename, doc_id)

        task = asyncio.create_task(
            _process_pdf(task_id, doc_id, str(file_path), filename)
        )
        _processing_tasks[task_id] = task

        return {
            "doc_id": doc_id,
            "task_id": task_id,
            "message": "Upload queued for indexing",
            "filename": filename,
        }

    return {
        "doc_id": doc_id,
        "message": "Upload complete. Click Index to process.",
        "filename": filename,
    }
