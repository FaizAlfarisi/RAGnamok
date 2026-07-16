import json
import logging
from uuid import uuid4

from sqlalchemy import text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


async def insert_document(session, filename: str) -> str:
    doc_id = str(uuid4())
    await session.execute(
        text(
            "INSERT INTO documents (id, filename, status, enabled) "
            "VALUES (:id, :filename, 'uploaded', false)"
        ),
        {"id": doc_id, "filename": filename},
    )
    await session.commit()
    logger.info("Inserted document: %s (%s)", filename, doc_id)
    return doc_id


async def list_documents(
    session, limit: int = 20, offset: int = 0
) -> list[dict]:
    rows = await session.execute(
        text(
            "SELECT d.id, d.filename, d.created_at, d.status, d.enabled, "
            "COUNT(dc.id) AS chunk_count "
            "FROM documents d "
            "LEFT JOIN document_chunks dc ON dc.doc_id = d.id "
            "WHERE d.deleted_at IS NULL "
            "GROUP BY d.id "
            "ORDER BY d.created_at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"limit": limit, "offset": offset},
    )
    return [
        {
            "id": str(row[0]),
            "filename": row[1],
            "created_at": row[2].isoformat() if row[2] else None,
            "status": row[3],
            "enabled": row[4],
            "chunk_count": row[5],
        }
        for row in rows.fetchall()
    ]


async def get_document(session, doc_id: str) -> dict | None:
    row = await session.execute(
        text(
            "SELECT d.id, d.filename, d.created_at, d.status, d.enabled, "
            "COUNT(dc.id) AS chunk_count "
            "FROM documents d "
            "LEFT JOIN document_chunks dc ON dc.doc_id = d.id "
            "WHERE d.id = :id AND d.deleted_at IS NULL "
            "GROUP BY d.id"
        ),
        {"id": doc_id},
    )
    row = row.fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "filename": row[1],
        "created_at": row[2].isoformat() if row[2] else None,
        "status": row[3],
        "enabled": row[4],
        "chunk_count": row[5],
    }


async def delete_document(session, doc_id: str) -> bool:
    result = await session.execute(
        text("UPDATE documents SET deleted_at = NOW() WHERE id = :id AND deleted_at IS NULL"),
        {"id": doc_id},
    )
    await session.commit()
    return result.rowcount > 0


async def update_document_status(
    session, doc_id: str, status: str, enabled: bool | None = None
) -> bool:
    if enabled is not None:
        result = await session.execute(
            text(
                "UPDATE documents SET status = :status, enabled = :enabled "
                "WHERE id = :id"
            ),
            {"id": doc_id, "status": status, "enabled": enabled},
        )
    else:
        result = await session.execute(
            text("UPDATE documents SET status = :status WHERE id = :id"),
            {"id": doc_id, "status": status},
        )
    await session.commit()
    return result.rowcount > 0


async def toggle_document(session, doc_id: str) -> bool | None:
    row = await session.execute(
        text("SELECT enabled FROM documents WHERE id = :id"),
        {"id": doc_id},
    )
    row = row.fetchone()
    if not row:
        return None
    new_val = not row[0]
    await session.execute(
        text("UPDATE documents SET enabled = :val WHERE id = :id"),
        {"id": doc_id, "val": new_val},
    )
    await session.commit()
    return new_val


async def delete_chunks_by_doc_id(session, doc_id: str):
    await session.execute(
        text("DELETE FROM document_chunks WHERE doc_id = :id"),
        {"id": doc_id},
    )
    await session.commit()


async def get_chunk_ids_for_doc(session, doc_id: str) -> list[str]:
    rows = await session.execute(
        text("SELECT id FROM document_chunks WHERE doc_id = :id"),
        {"id": doc_id},
    )
    return [str(row[0]) for row in rows.fetchall()]


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------


async def insert_chunks_batch(
    session, doc_id: str, chunks: list[dict]
) -> int:
    await session.execute(
        text(
            "INSERT INTO document_chunks "
            "(id, doc_id, element_type, original_content, page_number) "
            "VALUES (:chunk_id, :doc_id, :element_type, :content, :page_number)"
        ),
        [
            {
                "chunk_id": c["chunk_id"],
                "doc_id": doc_id,
                "element_type": c["element_type"],
                "content": c["content"],
                "page_number": c["page_number"],
            }
            for c in chunks
        ],
    )
    await session.execute(
        text(
            "INSERT INTO chunk_summaries "
            "(id, chunk_id, summary_text, embedding) "
            "VALUES (:id, :chunk_id, :summary, CAST(:embedding AS vector))"
        ),
        [
            {
                "id": str(uuid4()),
                "chunk_id": c["chunk_id"],
                "summary": c["summary"],
                "embedding": "[" + ",".join(str(x) for x in c["embedding"]) + "]",
            }
            for c in chunks
        ],
    )
    await session.commit()
    return len(chunks)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


async def insert_task(session, task_id: str, filename: str, doc_id: str):
    await session.execute(
        text(
            "INSERT INTO tasks (id, filename, doc_id, status, progress) "
            "VALUES (:id, :filename, :doc_id, 'queued', 'Queued')"
        ),
        {"id": task_id, "filename": filename, "doc_id": doc_id},
    )
    await session.commit()


async def update_task(
    session,
    task_id: str,
    status: str,
    progress: str | None = None,
    error: str | None = None,
):
    await session.execute(
        text(
            "UPDATE tasks SET status = :status, "
            "progress = COALESCE(:progress, progress), "
            "error = COALESCE(:error, error), "
            "updated_at = NOW() "
            "WHERE id = :id"
        ),
        {"id": task_id, "status": status, "progress": progress, "error": error},
    )
    await session.commit()


async def get_task(session, task_id: str) -> dict | None:
    row = await session.execute(
        text(
            "SELECT id, filename, doc_id, status, progress, error, created_at, updated_at "
            "FROM tasks WHERE id = :id"
        ),
        {"id": task_id},
    )
    row = row.fetchone()
    if not row:
        return None
    return {
        "task_id": str(row[0]),
        "filename": row[1],
        "doc_id": str(row[2]) if row[2] else None,
        "status": row[3],
        "progress": row[4],
        "error": row[5],
        "created_at": row[6].isoformat() if row[6] else None,
        "updated_at": row[7].isoformat() if row[7] else None,
    }


async def get_active_task_for_doc(session, doc_id: str) -> dict | None:
    row = await session.execute(
        text(
            "SELECT id, status FROM tasks "
            "WHERE doc_id = :id AND status NOT IN ('completed', 'failed') "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"id": doc_id},
    )
    row = row.fetchone()
    if not row:
        return None
    return {"task_id": str(row[0]), "status": row[1]}


async def vector_search(
    session, query_embedding: list, top_k: int = 5
) -> list[dict]:
    rows = await session.execute(
        text(
            "SELECT c.element_type, c.original_content, c.page_number "
            "FROM chunk_summaries s "
            "JOIN document_chunks c ON s.chunk_id = c.id "
            "JOIN documents d ON c.doc_id = d.id "
            "WHERE d.enabled = true AND d.status = 'completed' AND d.deleted_at IS NULL "
            "ORDER BY s.embedding <=> CAST(:query AS vector) "
            "LIMIT :limit"
        ),
        {"query": str(query_embedding), "limit": top_k},
    )
    return [
        {
            "element_type": row[0],
            "original_content": row[1],
            "page_number": row[2],
        }
        for row in rows.fetchall()
    ]


# ---------------------------------------------------------------------------
# Chat sessions
# ---------------------------------------------------------------------------


async def create_session(session, title: str = "New Chat") -> dict:
    sid = str(uuid4())
    await session.execute(
        text(
            "INSERT INTO chat_sessions (id, title) VALUES (:id, :title)"
        ),
        {"id": sid, "title": title},
    )
    await session.commit()
    logger.info("Created chat session: %s", sid)
    return {"id": sid, "title": title}


async def list_sessions(session) -> list[dict]:
    rows = await session.execute(
        text(
            "SELECT s.id, s.title, s.created_at, s.updated_at, "
            "COUNT(m.id) AS message_count "
            "FROM chat_sessions s "
            "LEFT JOIN chat_messages m ON m.session_id = s.id "
            "GROUP BY s.id "
            "ORDER BY s.updated_at DESC"
        )
    )
    return [
        {
            "id": str(r[0]),
            "title": r[1],
            "created_at": r[2].isoformat() if r[2] else None,
            "updated_at": r[3].isoformat() if r[3] else None,
            "message_count": r[4],
        }
        for r in rows.fetchall()
    ]


async def update_session_title(session, session_id: str, title: str) -> bool:
    result = await session.execute(
        text(
            "UPDATE chat_sessions SET title = :title, updated_at = NOW() "
            "WHERE id = :id"
        ),
        {"id": session_id, "title": title},
    )
    await session.commit()
    return result.rowcount > 0


async def touch_session(session, session_id: str):
    await session.execute(
        text("UPDATE chat_sessions SET updated_at = NOW() WHERE id = :id"),
        {"id": session_id},
    )
    await session.commit()


async def delete_session(session, session_id: str) -> bool:
    result = await session.execute(
        text("DELETE FROM chat_sessions WHERE id = :id"),
        {"id": session_id},
    )
    await session.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Chat messages
# ---------------------------------------------------------------------------


async def save_message(
    session,
    session_id: str,
    role: str,
    content: str,
    sources: list | None = None,
    images: list | None = None,
) -> str:
    mid = str(uuid4())
    await session.execute(
        text(
            "INSERT INTO chat_messages "
            "(id, session_id, role, content, sources, images) "
            "VALUES (:id, :sid, :role, :content, :sources, :images)"
        ),
        {
            "id": mid,
            "sid": session_id,
            "role": role,
            "content": content,
            "sources": json.dumps(sources) if sources else None,
            "images": json.dumps(images) if images else None,
        },
    )
    await session.commit()
    return mid


async def get_messages(session, session_id: str, limit: int = 50) -> list[dict]:
    rows = await session.execute(
        text(
            "SELECT id, role, content, sources, images, created_at "
            "FROM chat_messages "
            "WHERE session_id = :sid "
            "ORDER BY created_at ASC "
            "LIMIT :limit"
        ),
        {"sid": session_id, "limit": limit},
    )
    result = []
    for r in rows.fetchall():
        sources = r[3]
        images = r[4]
        if isinstance(sources, str):
            sources = json.loads(sources)
        if isinstance(images, str):
            images = json.loads(images)
        msg = {
            "id": str(r[0]),
            "role": r[1],
            "content": r[2],
            "sources": sources,
            "images": images,
            "created_at": r[5].isoformat() if r[5] else None,
        }
        result.append(msg)
    return result


async def get_chat_history(session, session_id: str, depth: int = 6) -> list[dict]:
    rows = await session.execute(
        text(
            "SELECT role, content FROM ("
            "  SELECT role, content, created_at "
            "  FROM chat_messages "
            "  WHERE session_id = :sid "
            "  ORDER BY created_at DESC "
            "  LIMIT :limit"
            ") sub ORDER BY created_at ASC"
        ),
        {"sid": session_id, "limit": depth * 2},
    )
    return [{"role": r[0], "content": r[1]} for r in rows.fetchall()]
