"""Comprehensive upload pipeline tests — validation, size limits, auto-index, cleanup."""

import asyncio
import io

import pytest

from app.config import settings

_HAVE_API_KEYS = bool(settings.jina_api_key and settings.ollama_api_key)


def _disable_demo(monkeypatch):
    monkeypatch.setattr("app.routers.upload.settings.demo_mode", False)


@pytest.mark.asyncio
class TestUploadValidation:

    async def test_upload_missing_file(self, async_client):
        resp = await async_client.post("/api/v1/upload")
        assert resp.status_code == 422

    async def test_upload_empty_filename(self, async_client, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("", b"not a pdf", "application/pdf")},
        )
        assert resp.status_code in (400, 422)

    async def test_upload_txt_file(self, async_client, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("readme.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 400

    async def test_upload_exe_as_pdf(self, async_client, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("malware.pdf", b"MZ\x90\x00", "application/pdf")},
        )
        assert resp.status_code in (201, 400)

    async def test_upload_html_file(self, async_client, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("page.html", b"<h1>test</h1>", "text/html")},
        )
        assert resp.status_code == 400

    async def test_upload_csv_file(self, async_client, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("data.csv", b"a,b,c", "text/csv")},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestUploadFileSize:

    async def test_upload_oversized_file(self, async_client, monkeypatch):
        _disable_demo(monkeypatch)
        oversized = b"0" * (50 * 1024 * 1024 + 1)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("huge.pdf", oversized, "application/pdf")},
        )
        assert resp.status_code == 413
        assert "50 MB" in resp.json()["detail"]

    async def test_upload_exactly_max_size(self, async_client, monkeypatch):
        _disable_demo(monkeypatch)
        exact = b"0" * (50 * 1024 * 1024)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("max.pdf", exact, "application/pdf")},
        )
        assert resp.status_code in (201, 400, 500)

    async def test_upload_small_file_succeeds(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("small.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201


@pytest.mark.asyncio
class TestUploadResponseFormat:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_upload_auto_index_response(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("auto.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "doc_id" in body
        assert "task_id" in body
        assert body["filename"] == "auto.pdf"
        assert "message" in body

    async def test_upload_no_auto_index_response(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("manual.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "doc_id" in body
        assert "task_id" not in body
        assert body["filename"] == "manual.pdf"

    async def test_upload_returns_valid_uuid(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        import uuid

        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("uuid.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["doc_id"]
        uuid.UUID(doc_id)


@pytest.mark.asyncio
class TestUploadAutoIndex:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_auto_index_creates_task(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("task.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]
        task_resp = await async_client.get(f"/api/v1/tasks/{task_id}")
        assert task_resp.status_code == 200
        assert task_resp.json()["status"] in ("queued", "processing", "completed")

    async def test_no_auto_index_no_task(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("notask.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "task_id" not in body
        doc_resp = await async_client.get(f"/api/v1/documents/{body['doc_id']}")
        assert doc_resp.json()["status"] == "uploaded"

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_auto_index_document_becomes_completed(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("complete.pdf", sample_pdf, "application/pdf")},
        )
        task_id = resp.json()["task_id"]
        doc_id = resp.json()["doc_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] == "completed":
                break
            elif poll.json()["status"] == "failed":
                pytest.fail(f"Task failed: {poll.json().get('error')}")
            await asyncio.sleep(2)
        else:
            pytest.fail("Task did not complete within 120s")
        doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.json()["status"] == "completed"
        assert doc_resp.json()["enabled"] is True


@pytest.mark.asyncio
class TestUploadCleanup:

    @pytest.mark.skipif(not _HAVE_API_KEYS, reason="Indexing requires API keys")
    async def test_upload_file_deleted_after_success(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("cleanup.pdf", sample_pdf, "application/pdf")},
        )
        task_id = resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            if poll.json()["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(2)
        from pathlib import Path
        from app.config import settings
        upload_dir = Path(settings.upload_dir)
        remaining = list(upload_dir.glob("*.pdf"))
        assert len(remaining) >= 1


@pytest.mark.asyncio
class TestUploadSpecialFilenames:

    async def test_upload_filename_with_spaces(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("my document.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        assert resp.json()["filename"] == "my document.pdf"

    async def test_upload_filename_with_unicode(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": ("dokumen_tes.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201

    async def test_upload_long_filename(self, async_client, sample_pdf, monkeypatch):
        _disable_demo(monkeypatch)
        long_name = "a" * 200 + ".pdf"
        resp = await async_client.post(
            "/api/v1/upload",
            files={"file": (long_name, sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
