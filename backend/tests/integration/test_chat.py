"""Test the simple stateless chat endpoint and upload pipeline.

Tests that require Jina AI or Ollama Cloud API keys are conditionally
skipped when keys are not configured in .env.
"""

import asyncio

import pytest

from app.config import settings

_HAVE_API_KEYS = bool(settings.jina_api_key and settings.ollama_api_key)


@pytest.mark.asyncio
class TestSimpleChat:

    @pytest.mark.skipif(
        not _HAVE_API_KEYS,
        reason="Requires JINA_API_KEY and OLLAMA_API_KEY",
    )
    async def test_chat_basic(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Apa itu RAG?", "top_k": 3}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert isinstance(body["answer"], str)
        assert len(body["answer"]) > 0
        assert "sources" in body
        assert "images" in body

    @pytest.mark.skipif(
        not _HAVE_API_KEYS,
        reason="Requires JINA_API_KEY and OLLAMA_API_KEY",
    )
    async def test_chat_top_k_clamped(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Test", "top_k": 0}
        )
        assert resp.status_code == 200

        resp = await async_client.post(
            "/api/v1/chat", json={"query": "Test", "top_k": 999}
        )
        assert resp.status_code == 200

    async def test_chat_missing_query(self, async_client):
        resp = await async_client.post("/api/v1/chat", json={})
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestUpload:

    async def test_upload_non_pdf(self, async_client, monkeypatch):
        monkeypatch.setattr("app.routers.upload.settings.demo_mode", False)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert resp.status_code == 400

    async def test_upload_in_demo_mode(self, async_client, monkeypatch):
        monkeypatch.setattr("app.routers.upload.settings.demo_mode", True)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("test.pdf", b"%PDF-some content", "application/pdf")},
        )
        assert resp.status_code == 503
        assert "demo" in resp.json()["detail"].lower()

    @pytest.mark.skipif(
        not _HAVE_API_KEYS,
        reason="Requires JINA_API_KEY and OLLAMA_API_KEY",
    )
    async def test_upload_valid_pdf(self, async_client, sample_pdf, monkeypatch):
        monkeypatch.setattr("app.routers.upload.settings.demo_mode", False)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "task_id" in body
        assert body["filename"] == "test.pdf"

        # Poll task until completion (with timeout)
        task_id = body["task_id"]

        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            assert poll.status_code == 200
            status = poll.json()["status"]
            if status == "completed":
                return
            elif status == "failed":
                pytest.fail(f"Task failed: {poll.json().get('error')}")
            await asyncio.sleep(2)

        pytest.fail("Task did not complete within 120s")

    async def test_task_not_found(self, async_client):
        resp = await async_client.get(
            "/api/v1/tasks/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404
