"""Edge case and security tests — SQL injection, path traversal, concurrent ops."""

import asyncio

import pytest


@pytest.mark.asyncio
class TestSQLInjection:
    """Test SQL injection prevention across endpoints."""

    async def test_sql_injection_in_chat_query(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat",
            json={"query": "'; DROP TABLE documents; --"},
        )
        assert resp.status_code == 200

        list_resp = await async_client.get("/api/v1/documents")
        assert list_resp.status_code == 200

    async def test_sql_injection_in_session_title(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions",
            json={"title": "'; DELETE FROM chat_sessions; --"},
        )
        assert resp.status_code == 201

        list_resp = await async_client.get("/api/v1/chat/sessions")
        assert list_resp.status_code == 200

    async def test_sql_injection_in_upload_filename(self, async_client):
        resp = await async_client.post(
            "/api/v1/upload",
            files={
                "file": ("'; DROP TABLE--.pdf", b"not pdf", "application/pdf")
            },
        )
        assert resp.status_code in (400, 201)

    async def test_sql_injection_in_message_content(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "SQLi"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={
                "query": "1' UNION SELECT * FROM users--",
                "top_k": 3,
            },
        )
        assert resp.status_code == 200

    async def test_boolean_sql_injection(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat",
            json={"query": "1' OR '1'='1"},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestPathTraversal:
    """Test path traversal prevention."""

    async def test_upload_path_traversal_filename(self, async_client):
        resp = await async_client.post(
            "/api/v1/upload",
            files={
                "file": ("../../etc/passwd.pdf", b"not pdf", "application/pdf")
            },
        )
        assert resp.status_code in (400, 201)

    async def test_upload_backslash_filename(self, async_client):
        resp = await async_client.post(
            "/api/v1/upload",
            files={
                "file": (
                    "..\\..\\Windows\\System32.pdf",
                    b"not pdf",
                    "application/pdf",
                )
            },
        )
        assert resp.status_code in (400, 201)

    async def test_upload_null_byte_filename(self, async_client):
        resp = await async_client.post(
            "/api/v1/upload",
            files={
                "file": ("test.pdf\x00.pdf", b"not pdf", "application/pdf")
            },
        )
        assert resp.status_code in (400, 201, 500)


@pytest.mark.asyncio
class TestConcurrentOperations:
    """Test concurrent upload and chat operations."""

    async def test_concurrent_uploads(self, async_client, sample_pdf):
        tasks = []
        for i in range(3):
            task = async_client.post(
                "/api/v1/upload?auto_index=false",
                files={
                    "file": (f"concurrent{i}.pdf", sample_pdf, "application/pdf")
                },
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        assert all(r.status_code == 201 for r in responses)

        doc_ids = [r.json()["doc_id"] for r in responses]
        assert len(set(doc_ids)) == 3

    async def test_concurrent_chat_queries(self, async_client):
        tasks = []
        for i in range(5):
            task = async_client.post(
                "/api/v1/chat",
                json={"query": f"Pertanyaan {i}", "top_k": 3},
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in responses)

    async def test_concurrent_session_creates(self, async_client):
        tasks = []
        for i in range(5):
            task = async_client.post(
                "/api/v1/chat/sessions",
                json={"title": f"Concurrent {i}"},
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        assert all(r.status_code == 201 for r in responses)

        ids = [r.json()["id"] for r in responses]
        assert len(set(ids)) == 5


@pytest.mark.asyncio
class TestUUIDValidation:
    """Test UUID format validation across endpoints."""

    async def test_get_document_invalid_uuid(self, async_client):
        resp = await async_client.get("/api/v1/documents/invalid-uuid")
        assert resp.status_code in (400, 422)

    async def test_delete_document_invalid_uuid(self, async_client):
        resp = await async_client.delete("/api/v1/documents/invalid-uuid")
        assert resp.status_code in (400, 422)

    async def test_toggle_document_invalid_uuid(self, async_client):
        resp = await async_client.post(
            "/api/v1/documents/invalid-uuid/toggle"
        )
        assert resp.status_code in (400, 422)

    async def test_index_document_invalid_uuid(self, async_client):
        resp = await async_client.post(
            "/api/v1/documents/invalid-uuid/index"
        )
        assert resp.status_code in (400, 422)

    async def test_get_task_invalid_uuid(self, async_client):
        resp = await async_client.get("/api/v1/tasks/invalid-uuid")
        assert resp.status_code in (400, 422)

    async def test_cancel_task_invalid_uuid(self, async_client):
        resp = await async_client.post("/api/v1/tasks/invalid-uuid/cancel")
        assert resp.status_code in (400, 422)

    async def test_get_active_task_invalid_uuid(self, async_client):
        resp = await async_client.get(
            "/api/v1/tasks/active-for-doc/invalid-uuid"
        )
        assert resp.status_code in (400, 422)

    async def test_update_session_invalid_uuid(self, async_client):
        resp = await async_client.patch(
            "/api/v1/chat/sessions/invalid-uuid", json={"title": "X"}
        )
        assert resp.status_code == 400

    async def test_delete_session_invalid_uuid(self, async_client):
        resp = await async_client.delete(
            "/api/v1/chat/sessions/invalid-uuid"
        )
        assert resp.status_code == 400

    async def test_get_messages_invalid_uuid(self, async_client):
        resp = await async_client.get(
            "/api/v1/chat/sessions/invalid-uuid/messages"
        )
        assert resp.status_code in (400, 422)

    async def test_send_message_invalid_uuid(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions/invalid-uuid/messages",
            json={"query": "Test", "top_k": 3},
        )
        assert resp.status_code in (400, 422)


@pytest.mark.asyncio
class TestMethodNotAllowed:
    """Test wrong HTTP methods on endpoints."""

    async def test_get_on_upload(self, async_client):
        resp = await async_client.get("/api/v1/upload")
        assert resp.status_code == 405

    async def test_put_on_upload(self, async_client):
        resp = await async_client.put("/api/v1/upload")
        assert resp.status_code == 405

    async def test_delete_on_upload(self, async_client):
        resp = await async_client.delete("/api/v1/upload")
        assert resp.status_code == 405

    async def test_post_on_health(self, async_client):
        resp = await async_client.post("/api/v1/health")
        assert resp.status_code == 405

    async def test_patch_on_documents(self, async_client):
        resp = await async_client.patch("/api/v1/documents")
        assert resp.status_code == 405

    async def test_get_on_chat(self, async_client):
        resp = await async_client.get("/api/v1/chat")
        assert resp.status_code == 405


@pytest.mark.asyncio
class TestContentTypeValidation:
    """Test content type handling."""

    async def test_chat_with_form_data(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat",
            data={"query": "Test"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code in (400, 415, 422)

    async def test_upload_with_json(self, async_client):
        resp = await async_client.post(
            "/api/v1/upload",
            json={"file": "test.pdf"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 415, 422)


@pytest.mark.asyncio
class TestEmptyBody:
    """Test endpoints with empty or missing request bodies."""

    async def test_chat_empty_body(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 422)

    async def test_create_session_empty_body(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    async def test_update_session_empty_body(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Test"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/v1/chat/sessions/{sid}",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestNonexistentRoutes:
    """Test 404 for nonexistent API routes."""

    async def test_nonexistent_endpoint(self, async_client):
        resp = await async_client.get("/api/v1/nonexistent")
        assert resp.status_code == 404

    async def test_nonexistent_chat_endpoint(self, async_client):
        resp = await async_client.post("/api/v1/chat/nonexistent", json={"query": "hi"})
        assert resp.status_code == 404

    async def test_nonexistent_documents_endpoint(self, async_client):
        resp = await async_client.post("/api/v1/documents")
        assert resp.status_code == 405
