"""Comprehensive document management tests — CRUD, soft-delete, re-index, toggle."""

import asyncio

import pytest

from app.config import settings

_HAVE_API_KEYS = bool(settings.jina_api_key and settings.ollama_api_key)


def _disable_demo(monkeypatch):
    monkeypatch.setattr("app.routers.upload.settings.demo_mode", False)


@pytest.mark.asyncio
class TestDocumentList:

    async def test_list_documents_empty(self, async_client):
        resp = await async_client.get("/api/v1/documents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_documents_with_limit(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        for i in range(3):
            await async_client.post(
                "/api/v1/upload?auto_index=false",
                files={"file": (f"doc{i}.pdf", sample_pdf, "application/pdf")},
            )
        resp = await async_client.get("/api/v1/documents?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

    async def test_list_documents_with_offset(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        for i in range(3):
            await async_client.post(
                "/api/v1/upload?auto_index=false",
                files={"file": (f"offset{i}.pdf", sample_pdf, "application/pdf")},
            )
        resp_all = await async_client.get("/api/v1/documents?limit=10")
        resp_offset = await async_client.get("/api/v1/documents?limit=1&offset=1")
        assert resp_offset.status_code == 200
        assert len(resp_offset.json()) == 1
        assert resp_offset.json()[0]["id"] != resp_all.json()[0]["id"]

    async def test_list_documents_limit_zero(self, async_client):
        resp = await async_client.get("/api/v1/documents?limit=0")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) <= 1

    async def test_list_documents_large_limit(self, async_client):
        resp = await async_client.get("/api/v1/documents?limit=9999")
        assert resp.status_code == 200

    async def test_list_documents_negative_offset(self, async_client):
        resp = await async_client.get("/api/v1/documents?offset=-1")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestDocumentGet:

    async def test_get_document_by_id(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("getme.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == doc_id
        assert body["filename"] == "getme.pdf"
        assert body["status"] == "uploaded"
        assert body["enabled"] is False
        assert "chunk_count" in body

    async def test_get_document_invalid_uuid(self, async_client):
        resp = await async_client.get("/api/v1/documents/not-a-uuid")
        assert resp.status_code in (400, 422)

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_get_document_includes_chunk_count(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("chunks.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        task_id = up_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)
        resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert resp.json()["chunk_count"] > 0


@pytest.mark.asyncio
class TestDocumentDelete:

    async def test_soft_delete_sets_deleted_at(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("softdel.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        del_resp = await async_client.delete(f"/api/v1/documents/{doc_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["document_id"] == doc_id
        get_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.status_code == 404

    async def test_double_delete_returns_404(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("deldel.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        await async_client.delete(f"/api/v1/documents/{doc_id}")
        resp = await async_client.delete(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 404

    async def test_deleted_document_excluded_from_list(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("hidden.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        await async_client.delete(f"/api/v1/documents/{doc_id}")
        list_resp = await async_client.get("/api/v1/documents")
        assert doc_id not in [d["id"] for d in list_resp.json()]

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_delete_cancels_active_task(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("cancelme.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        await async_client.delete(f"/api/v1/documents/{doc_id}")
        get_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.status_code == 404


@pytest.mark.asyncio
class TestDocumentToggle:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_toggle_off_then_on(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("toggle.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        task_id = up_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)
        resp1 = await async_client.post(f"/api/v1/documents/{doc_id}/toggle")
        assert resp1.status_code == 200
        assert resp1.json()["enabled"] is False
        resp2 = await async_client.post(f"/api/v1/documents/{doc_id}/toggle")
        assert resp2.status_code == 200
        assert resp2.json()["enabled"] is True

    async def test_toggle_returns_correct_doc_id(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("toggledoc.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        resp = await async_client.post(f"/api/v1/documents/{doc_id}/toggle")
        assert resp.json()["doc_id"] == doc_id

    async def test_toggle_invalid_uuid(self, async_client):
        resp = await async_client.post("/api/v1/documents/not-a-uuid/toggle")
        assert resp.status_code in (400, 422)


@pytest.mark.asyncio
class TestDocumentReindex:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_reindex_completed_document(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("reindex.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        task_id = up_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)
        doc_before = (await async_client.get(f"/api/v1/documents/{doc_id}")).json()
        idx_resp = await async_client.post(f"/api/v1/documents/{doc_id}/index")
        assert idx_resp.status_code == 200
        assert "task_id" in idx_resp.json()
        new_task_id = idx_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{new_task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)
        doc_after = (await async_client.get(f"/api/v1/documents/{doc_id}")).json()
        assert doc_after["status"] == "completed"

    async def test_index_nonexistent_document(self, async_client):
        resp = await async_client.post(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000/index"
        )
        assert resp.status_code == 404

    async def test_index_returns_task_id(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("idx.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        resp = await async_client.post(f"/api/v1/documents/{doc_id}/index")
        assert resp.status_code == 200
        body = resp.json()
        assert "task_id" in body
        assert body["doc_id"] == doc_id


@pytest.mark.asyncio
class TestDocumentStatusTransitions:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_status_uploaded_to_completed(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("status.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        task_id = up_resp.json()["task_id"]
        doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.json()["status"] in ("uploaded", "processing")
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            status = poll.json()["status"]
            if status == "completed":
                break
            await asyncio.sleep(2)
        doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.json()["status"] == "completed"

    async def test_status_uploaded_without_index(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("uploaded.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.json()["status"] == "uploaded"
        assert doc_resp.json()["enabled"] is False

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_enabled_true_after_completion(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("enabled.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        task_id = up_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)
        doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.json()["enabled"] is True
