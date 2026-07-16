"""Test document management endpoints."""

import asyncio

import pytest


@pytest.mark.asyncio
class TestDocuments:

    async def test_list_documents(self, async_client):
        resp = await async_client.get("/api/v1/documents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_document_not_found(self, async_client):
        resp = await async_client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_delete_document_not_found(self, async_client):
        resp = await async_client.delete(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_toggle_document_not_found(self, async_client):
        resp = await async_client.post(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000/toggle"
        )
        assert resp.status_code == 404

    async def test_upload_without_auto_index(self, async_client, sample_pdf):
        """Upload without auto-index — doc should be 'uploaded' status."""
        resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("doc_test.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "doc_id" in data
        assert data["filename"] == "doc_test.pdf"

        doc_id = data["doc_id"]
        get_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "uploaded"
        assert get_resp.json()["enabled"] is False

    async def test_upload_then_index_then_toggle_then_delete(
        self, async_client, sample_pdf
    ):
        # Upload (no auto-index)
        up_resp = await async_client.post(
            "/api/v1/upload?auto_index=false",
            files={"file": ("doc_test.pdf", sample_pdf, "application/pdf")},
        )
        assert up_resp.status_code == 201
        doc_id = up_resp.json()["doc_id"]

        # Start indexing
        idx_resp = await async_client.post(f"/api/v1/documents/{doc_id}/index")
        assert idx_resp.status_code == 200
        assert "task_id" in idx_resp.json()

        # Wait for completion
        task_id = idx_resp.json()["task_id"]
        for _ in range(60):
            poll = await async_client.get(f"/api/v1/tasks/{task_id}")
            status = poll.json()["status"]
            if status == "completed":
                break
            elif status == "failed":
                pytest.fail(f"Indexing failed: {poll.json().get('error')}")
            await asyncio.sleep(2)
        else:
            pytest.fail("Indexing timed out")

        # Verify document is completed and enabled
        get_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "completed"
        assert get_resp.json()["enabled"] is True
        assert get_resp.json()["chunk_count"] > 0

        # Toggle off
        tog_resp = await async_client.post(f"/api/v1/documents/{doc_id}/toggle")
        assert tog_resp.status_code == 200
        assert tog_resp.json()["enabled"] is False

        # Toggle back on
        tog_resp2 = await async_client.post(f"/api/v1/documents/{doc_id}/toggle")
        assert tog_resp2.status_code == 200
        assert tog_resp2.json()["enabled"] is True

        # Delete
        del_resp = await async_client.delete(f"/api/v1/documents/{doc_id}")
        assert del_resp.status_code == 200

        # Verify gone
        list_resp = await async_client.get("/api/v1/documents")
        assert doc_id not in [d["id"] for d in list_resp.json()]

        # Get should 404
        get2 = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert get2.status_code == 404
