"""Comprehensive chat/query system tests — retrieval, top_k, edge cases.

Tests that hit the real LLM/embedder require API keys in .env and are
skipped when keys are missing.
"""

import pytest

from app.config import settings

_HAVE_API_KEYS = bool(settings.jina_api_key and settings.ollama_api_key)


def _disable_demo(monkeypatch):
    monkeypatch.setattr("app.routers.upload.settings.demo_mode", False)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _HAVE_API_KEYS,
    reason="Requires JINA_API_KEY and OLLAMA_API_KEY",
)
class TestChatEndpoint:
    """Test stateless /api/v1/chat endpoint."""

    async def test_chat_empty_query(self, async_client):
        resp = await async_client.post("/api/v1/chat", json={"query": ""})
        assert resp.status_code == 200

    async def test_chat_whitespace_query(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "   "}
        )
        assert resp.status_code == 200

    async def test_chat_long_query(self, async_client):
        long_query = "Apa itu " * 500
        resp = await async_client.post(
            "/api/v1/chat", json={"query": long_query}
        )
        assert resp.status_code == 200

    async def test_chat_special_characters(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat",
            json={"query": "SELECT * FROM users; DROP TABLE--"},
        )
        assert resp.status_code == 200

    async def test_chat_unicode_query(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat",
            json={"query": "Apa itu RAG? Jelaskan dalam Bahasa Indonesia"},
        )
        assert resp.status_code == 200

    async def test_chat_emoji_query(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Apa itu RAG? 🤔"}
        )
        assert resp.status_code == 200

    async def test_chat_newlines_in_query(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat",
            json={"query": "Apa itu\nRAG?\nJelaskan"},
        )
        assert resp.status_code == 200

    async def test_chat_tab_in_query(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Apa\titu\tRAG?"}
        )
        assert resp.status_code == 200

    async def test_chat_response_structure(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Apa itu RAG?"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert isinstance(body["answer"], str)
        assert "sources" in body
        assert isinstance(body["sources"], list)
        assert "images" in body
        assert isinstance(body["images"], list)

    async def test_chat_default_top_k(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Test"}
        )
        assert resp.status_code == 200

    async def test_chat_top_k_boundary_values(self, async_client):
        for top_k in [1, 25, 50]:
            resp = await async_client.post(
                "/api/v1/chat", json={"query": "Test", "top_k": top_k}
            )
            assert resp.status_code == 200

    async def test_chat_negative_top_k(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Test", "top_k": -5}
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestChatEndpointValidation:
    """Validation-only tests (always run, no API keys needed)."""

    async def test_chat_missing_body(self, async_client):
        resp = await async_client.post("/api/v1/chat")
        assert resp.status_code == 422

    async def test_chat_wrong_content_type(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat",
            content=b"not json",
            headers={"Content-Type": "application/octet-stream"},
        )
        assert resp.status_code in (400, 415, 422)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _HAVE_API_KEYS,
    reason="Requires JINA_API_KEY and OLLAMA_API_KEY",
)
class TestChatWithDocuments:
    """Test chat behavior with uploaded/indexed documents."""

    async def test_chat_without_documents(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Apa itu RAG?"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["answer"], str)
        assert isinstance(body["sources"], list)

    async def test_chat_with_uploaded_not_indexed(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("notindexed.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]

        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Apa itu RAG?"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sources"]) == 0

    async def test_chat_with_disabled_document(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("disabled.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        task_id = up_resp.json()["task_id"]

        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)

        await async_client.post(f"/api/v1/documents/{doc_id}/toggle")

        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Test content"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sources"]) == 0

    async def test_chat_with_deleted_document(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("deleted.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        task_id = up_resp.json()["task_id"]

        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)

        await async_client.delete(f"/api/v1/documents/{doc_id}")

        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Test content"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sources"]) == 0


import asyncio
