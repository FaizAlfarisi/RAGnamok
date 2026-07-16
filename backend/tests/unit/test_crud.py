"""Test CRUD functions against real PostgreSQL."""

import pytest

from app.db.crud import (
    create_session,
    delete_document,
    delete_session,
    get_chat_history,
    get_messages,
    insert_chunks_batch,
    insert_document,
    list_documents,
    list_sessions,
    save_message,
    toggle_document,
    touch_session,
    update_document_status,
    update_session_title,
    vector_search,
)


@pytest.mark.asyncio
async def test_create_session(db_session):
    doc = await create_session(db_session, "Test Chat")
    assert "id" in doc
    assert doc["title"] == "Test Chat"


@pytest.mark.asyncio
async def test_list_sessions_empty(db_session):
    sessions = await list_sessions(db_session)
    assert isinstance(sessions, list)


@pytest.mark.asyncio
async def test_list_sessions_with_data(db_session):
    s1 = await create_session(db_session, "Alpha")
    s2 = await create_session(db_session, "Beta")
    sessions = await list_sessions(db_session)
    ids = [s["id"] for s in sessions]
    assert s1["id"] in ids
    assert s2["id"] in ids


@pytest.mark.asyncio
async def test_update_session_title(db_session):
    doc = await create_session(db_session, "Old Title")
    ok = await update_session_title(db_session, doc["id"], "New Title")
    assert ok is True
    sessions = await list_sessions(db_session)
    updated = [s for s in sessions if s["id"] == doc["id"]]
    assert len(updated) == 1
    assert updated[0]["title"] == "New Title"


@pytest.mark.asyncio
async def test_update_session_title_not_found(db_session):
    ok = await update_session_title(
        db_session, "00000000-0000-0000-0000-000000000000", "Nope"
    )
    assert ok is False


@pytest.mark.asyncio
async def test_touch_session(db_session):
    doc = await create_session(db_session, "Touchable")
    await touch_session(db_session, doc["id"])
    sessions = await list_sessions(db_session)
    updated = [s for s in sessions if s["id"] == doc["id"]]
    assert updated[0]["updated_at"] is not None


@pytest.mark.asyncio
async def test_delete_session(db_session):
    doc = await create_session(db_session, "To Delete")
    ok = await delete_session(db_session, doc["id"])
    assert ok is True
    sessions = await list_sessions(db_session)
    assert doc["id"] not in [s["id"] for s in sessions]


@pytest.mark.asyncio
async def test_delete_session_not_found(db_session):
    ok = await delete_session(
        db_session, "00000000-0000-0000-0000-000000000000"
    )
    assert ok is False


@pytest.mark.asyncio
async def test_save_and_get_messages(db_session):
    session = await create_session(db_session, "Msg Session")

    mid1 = await save_message(db_session, session["id"], "user", "Halo")
    mid2 = await save_message(
        db_session,
        session["id"],
        "assistant",
        "Hai juga",
        sources=["src1"],
        images=["img1"],
    )

    msgs = await get_messages(db_session, session["id"])
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Halo"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["sources"] == ["src1"]
    assert msgs[1]["images"] == ["img1"]


@pytest.mark.asyncio
async def test_get_messages_limit(db_session):
    session = await create_session(db_session, "Limit Session")
    for i in range(5):
        await save_message(db_session, session["id"], "user", f"msg {i}")

    msgs = await get_messages(db_session, session["id"], limit=3)
    assert len(msgs) == 3
    assert msgs[0]["content"] == "msg 0"
    assert msgs[-1]["content"] == "msg 2"


@pytest.mark.asyncio
async def test_get_chat_history(db_session):
    session = await create_session(db_session, "History Session")
    await save_message(db_session, session["id"], "user", "q1")
    await save_message(db_session, session["id"], "assistant", "a1")
    await save_message(db_session, session["id"], "user", "q2")
    await save_message(db_session, session["id"], "assistant", "a2")

    history = await get_chat_history(db_session, session["id"], depth=2)
    assert len(history) == 4  # depth*2 = 4
    assert history[0]["content"] == "q1"
    assert history[3]["content"] == "a2"


@pytest.mark.asyncio
async def test_get_chat_history_empty(db_session):
    session = await create_session(db_session, "Empty History")
    history = await get_chat_history(db_session, session["id"])
    assert history == []


@pytest.mark.asyncio
async def test_insert_document(db_session):
    doc_id = await insert_document(db_session, "test.pdf")
    assert doc_id is not None
    docs = await list_documents(db_session)
    ids = [d["id"] for d in docs]
    assert doc_id in ids


@pytest.mark.asyncio
async def test_list_documents_all(db_session):
    d1 = await insert_document(db_session, "keep.pdf")
    d2 = await insert_document(db_session, "keep2.pdf")

    docs = await list_documents(db_session)
    ids = [d["id"] for d in docs]
    assert d1 in ids
    assert d2 in ids


@pytest.mark.asyncio
async def test_delete_document(db_session):
    doc_id = await insert_document(db_session, "kill.pdf")
    ok = await delete_document(db_session, doc_id)
    assert ok
    docs = await list_documents(db_session)
    assert doc_id not in [d["id"] for d in docs]

    ok2 = await delete_document(db_session, doc_id)
    assert not ok2


@pytest.mark.asyncio
async def test_update_document_status(db_session):
    doc_id = await insert_document(db_session, "status.pdf")
    ok = await update_document_status(db_session, doc_id, "completed", enabled=True)
    assert ok
    docs = await list_documents(db_session)
    for d in docs:
        if d["id"] == doc_id:
            assert d["status"] == "completed"
            assert d["enabled"] is True
            break


@pytest.mark.asyncio
async def test_toggle_document(db_session):
    doc_id = await insert_document(db_session, "toggle.pdf")
    new_val = await toggle_document(db_session, doc_id)
    assert new_val is True
    new_val2 = await toggle_document(db_session, doc_id)
    assert new_val2 is False


@pytest.mark.asyncio
async def test_toggle_document_not_found(db_session):
    val = await toggle_document(
        db_session, "00000000-0000-0000-0000-000000000000"
    )
    assert val is None


@pytest.mark.asyncio
async def test_vector_search_empty(db_session):
    emb = [0.0] * 1024
    results = await vector_search(db_session, emb, top_k=5)
    assert results == []


@pytest.mark.asyncio
async def test_insert_chunks_batch_and_vector_search(db_session):
    doc_id = await insert_document(db_session, "chunk_test.pdf")

    # Need to enable and complete the doc for vector_search to find chunks
    await update_document_status(db_session, doc_id, "completed", enabled=True)

    chunks = [
        {
            "chunk_id": "00000001-0000-0000-0000-000000000001",
            "element_type": "CompositeElement",
            "content": "Ini adalah teks uji coba.",
            "page_number": 1,
            "summary": "Ringkasan teks uji coba.",
            "embedding": [0.1] * 1024,
        }
    ]
    count = await insert_chunks_batch(db_session, doc_id, chunks)
    assert count == 1

    emb = [0.1] * 1024
    results = await vector_search(db_session, emb, top_k=5)
    assert len(results) >= 1
    assert results[0]["element_type"] == "CompositeElement"
    assert "teks uji coba" in results[0]["original_content"]
