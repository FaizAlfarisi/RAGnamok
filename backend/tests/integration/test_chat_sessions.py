"""Test chat session and message endpoints."""

import pytest


@pytest.mark.asyncio
class TestChatSessions:
    async def test_create_session(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "New Chat"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["title"] == "New Chat"
        assert body["message_count"] == 0

    async def test_list_sessions(self, async_client):
        resp = await async_client.get("/api/v1/chat/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_update_session(self, async_client):
        # Create
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Old"}
        )
        sid = create_resp.json()["id"]
        # Update
        resp = await async_client.patch(
            f"/api/v1/chat/sessions/{sid}", json={"title": "Updated"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    async def test_update_session_invalid_uuid(self, async_client):
        resp = await async_client.patch(
            "/api/v1/chat/sessions/not-a-uuid", json={"title": "X"}
        )
        assert resp.status_code == 400

    async def test_update_session_not_found(self, async_client):
        resp = await async_client.patch(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000",
            json={"title": "X"},
        )
        assert resp.status_code == 404

    async def test_delete_session(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Delete Me"}
        )
        sid = create_resp.json()["id"]
        resp = await async_client.delete(f"/api/v1/chat/sessions/{sid}")
        assert resp.status_code == 204

    async def test_delete_session_invalid_uuid(self, async_client):
        resp = await async_client.delete("/api/v1/chat/sessions/bad-uuid")
        assert resp.status_code == 400

    async def test_delete_session_not_found(self, async_client):
        resp = await async_client.delete(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_get_messages_empty(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Empty Msgs"}
        )
        sid = create_resp.json()["id"]
        resp = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_send_message(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Chat Test"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Apa itu RAG?", "top_k": 3},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "message_id" in body
        assert "answer" in body
        assert isinstance(body["answer"], str)
        assert len(body["answer"]) > 0

    async def test_send_message_then_check_messages(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Two Msgs"}
        )
        sid = create_resp.json()["id"]

        await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Pertanyaan pertama", "top_k": 3},
        )

        msgs_resp = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages"
        )
        msgs = msgs_resp.json()
        assert len(msgs) >= 2  # user + assistant
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Pertanyaan pertama"
        assert msgs[-1]["role"] == "assistant"

    async def test_send_message_invalid_uuid(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions/bad-uuid/messages",
            json={"query": "Test", "top_k": 3},
        )
        assert resp.status_code == 400

    async def test_top_k_clamped(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "TopK Test"}
        )
        sid = create_resp.json()["id"]

        # top_k=0 should be clamped to 1
        resp = await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Test", "top_k": 0},
        )
        assert resp.status_code == 200

        # top_k=999 should be clamped to 50
        resp = await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Test", "top_k": 999},
        )
        assert resp.status_code == 200

    async def test_message_limit_clamped(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Limit Test"}
        )
        sid = create_resp.json()["id"]
        resp = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages",
            params={"limit": 999},
        )
        assert resp.status_code == 200
        # Should return at most 200 (not crash)
        assert len(resp.json()) <= 200

    async def test_session_count_increments(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Count Test"}
        )
        sid = create_resp.json()["id"]

        await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Test", "top_k": 3},
        )

        sessions = await async_client.get("/api/v1/chat/sessions")
        for s in sessions.json():
            if s["id"] == sid:
                assert s["message_count"] >= 2  # user + assistant
                break
        else:
            pytest.fail("Session not found")
