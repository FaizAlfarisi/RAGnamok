"""Comprehensive task management tests — status, cancel, lifecycle."""

import asyncio

import pytest

from app.config import settings

_HAVE_API_KEYS = bool(settings.jina_api_key and settings.ollama_api_key)


def _disable_demo(monkeypatch):
    monkeypatch.setattr("app.routers.upload.settings.demo_mode", False)


@pytest.mark.asyncio
class TestTaskStatus:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_get_task_status(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("task.pdf", sample_pdf, "application/pdf")},
        )
        task_id = up_resp.json()["task_id"]
        resp = await async_client.get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == task_id
        assert body["status"] in ("queued", "processing", "completed", "failed")
        assert "progress" in body

    async def test_task_not_found(self, async_client):
        resp = await async_client.get(
            "/api/v1/tasks/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_task_invalid_uuid(self, async_client):
        resp = await async_client.get("/api/v1/tasks/not-a-uuid")
        assert resp.status_code in (400, 422)

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_task_has_doc_id(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("hasdoc.pdf", sample_pdf, "application/pdf")},
        )
        task_id = up_resp.json()["task_id"]
        doc_id = up_resp.json()["doc_id"]
        resp = await async_client.get(f"/api/v1/tasks/{task_id}")
        assert resp.json()["doc_id"] == doc_id

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_task_has_filename(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("hasname.pdf", sample_pdf, "application/pdf")},
        )
        task_id = up_resp.json()["task_id"]
        resp = await async_client.get(f"/api/v1/tasks/{task_id}")
        assert resp.json()["filename"] == "hasname.pdf"


@pytest.mark.asyncio
class TestTaskLifecycle:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_task_completes_after_upload(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("lifecycle.pdf", sample_pdf, "application/pdf")},
        )
        task_id = up_resp.json()["task_id"]
        statuses_seen = set()
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            status = poll.json()["status"]
            statuses_seen.add(status)
            if status == "completed":
                break
            elif status == "failed":
                pytest.fail(f"Task failed: {poll.json().get('error')}")
            await asyncio.sleep(2)
        else:
            pytest.fail("Task did not complete within 120s")
        assert "queued" in statuses_seen or "processing" in statuses_seen
        assert "completed" in statuses_seen

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_task_has_timestamps(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("timestamps.pdf", sample_pdf, "application/pdf")},
        )
        task_id = up_resp.json()["task_id"]
        resp = await async_client.get(f"/api/v1/tasks/{task_id}")
        body = resp.json()
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_completed_task_has_no_error(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("noerr.pdf", sample_pdf, "application/pdf")},
        )
        task_id = up_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)
        resp = await async_client.get(f"/api/v1/tasks/{task_id}")
        assert resp.json()["error"] is None


@pytest.mark.asyncio
class TestActiveTaskForDoc:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_get_active_task_for_doc(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("active.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        resp = await async_client.get(f"/api/v1/tasks/active-for-doc/{doc_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "task_id" in body
        assert body["status"] not in ("completed", "failed", "cancelled")

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_no_active_task_after_completion(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("done.pdf", sample_pdf, "application/pdf")},
        )
        doc_id = up_resp.json()["doc_id"]
        task_id = up_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)
        resp = await async_client.get(f"/api/v1/tasks/active-for-doc/{doc_id}")
        assert resp.status_code == 404

    async def test_active_task_for_nonexistent_doc(self, async_client):
        resp = await async_client.get(
            "/api/v1/tasks/active-for-doc/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_active_task_for_doc_without_task(self, async_client):
        resp = await async_client.get(
            "/api/v1/tasks/active-for-doc/00000000-0000-0000-0000-000000000001"
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestTaskCancel:

    async def test_cancel_nonexistent_task(self, async_client):
        resp = await async_client.post(
            "/api/v1/tasks/00000000-0000-0000-0000-000000000000/cancel"
        )
        assert resp.status_code == 404

    async def test_cancel_invalid_uuid(self, async_client):
        resp = await async_client.post("/api/v1/tasks/not-a-uuid/cancel")
        assert resp.status_code in (400, 422)

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_cancel_completed_task(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        up_resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("completed.pdf", sample_pdf, "application/pdf")},
        )
        task_id = up_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            await asyncio.sleep(2)
        resp = await async_client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()


import asyncio
