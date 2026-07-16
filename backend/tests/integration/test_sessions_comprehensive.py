"""Comprehensive chat session tests — CRUD, history, message ordering."""

import asyncio

import pytest


@pytest.mark.asyncio
class TestSessionCreate:
    """Test session creation."""

    async def test_create_session_default_title(self, async_client):
        resp = await async_client.post("/api/v1/chat/sessions", json={})
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "New Chat"
        assert body["message_count"] == 0

    async def test_create_session_custom_title(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "My Custom Chat"}
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "My Custom Chat"

    async def test_create_session_returns_valid_uuid(self, async_client):
        import uuid

        resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "UUID Test"}
        )
        uuid.UUID(resp.json()["id"])

    async def test_create_session_empty_title(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": ""}
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == ""

    async def test_create_session_long_title(self, async_client):
        long_title = "A" * 500
        resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": long_title}
        )
        assert resp.status_code == 201

    async def test_create_session_unicode_title(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions",
            json={"title": "Sesi Chat Bahasa Indonesia"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Sesi Chat Bahasa Indonesia"

    async def test_create_multiple_sessions(self, async_client):
        ids = []
        for i in range(3):
            resp = await async_client.post(
                "/api/v1/chat/sessions", json={"title": f"Session {i}"}
            )
            ids.append(resp.json()["id"])

        assert len(set(ids)) == 3

    async def test_create_session_response_fields(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Fields Test"}
        )
        body = resp.json()
        assert "id" in body
        assert "title" in body
        assert "message_count" in body
        assert "created_at" in body


@pytest.mark.asyncio
class TestSessionUpdate:
    """Test session title updates."""

    async def test_update_title(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Old"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/v1/chat/sessions/{sid}", json={"title": "New"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    async def test_update_to_empty_title(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Has Title"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/v1/chat/sessions/{sid}", json={"title": ""}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == ""

    async def test_update_preserves_message_count(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Count"}
        )
        sid = create_resp.json()["id"]

        await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Test", "top_k": 3},
        )

        resp = await async_client.patch(
            f"/api/v1/chat/sessions/{sid}", json={"title": "Updated"}
        )
        assert resp.json()["message_count"] >= 2

    async def test_update_nonexistent_session(self, async_client):
        resp = await async_client.patch(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000",
            json={"title": "Nope"},
        )
        assert resp.status_code == 404

    async def test_update_missing_title_field(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Test"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/v1/chat/sessions/{sid}", json={}
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestSessionDelete:
    """Test session deletion and cascade."""

    async def test_delete_session(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Delete Me"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.delete(f"/api/v1/chat/sessions/{sid}")
        assert resp.status_code == 204

        list_resp = await async_client.get("/api/v1/chat/sessions")
        assert sid not in [s["id"] for s in list_resp.json()]

    async def test_delete_cascades_messages(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Cascade"}
        )
        sid = create_resp.json()["id"]

        await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Test", "top_k": 3},
        )

        await async_client.delete(f"/api/v1/chat/sessions/{sid}")

        resp = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_delete_nonexistent_session(self, async_client):
        resp = await async_client.delete(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_double_delete(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Double"}
        )
        sid = create_resp.json()["id"]

        await async_client.delete(f"/api/v1/chat/sessions/{sid}")
        resp = await async_client.delete(f"/api/v1/chat/sessions/{sid}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestSessionMessages:
    """Test message retrieval and ordering."""

    async def test_get_messages_returns_chronological_order(
        self, async_client
    ):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Order"}
        )
        sid = create_resp.json()["id"]

        for i in range(3):
            await async_client.post(
                f"/api/v1/chat/sessions/{sid}/messages",
                json={"query": f"Question {i}", "top_k": 3},
            )

        resp = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages"
        )
        msgs = resp.json()
        assert len(msgs) >= 6

        timestamps = [m["created_at"] for m in msgs]
        assert timestamps == sorted(timestamps)

    async def test_get_messages_limit_one(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Limit1"}
        )
        sid = create_resp.json()["id"]

        for i in range(3):
            await async_client.post(
                f"/api/v1/chat/sessions/{sid}/messages",
                json={"query": f"Q{i}", "top_k": 3},
            )

        resp = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages?limit=1"
        )
        assert len(resp.json()) == 1

    async def test_get_messages_limit_zero_clamped(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Limit0"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages?limit=0"
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_messages_invalid_session(self, async_client):
        resp = await async_client.get(
            "/api/v1/chat/sessions/not-a-uuid/messages"
        )
        assert resp.status_code in (400, 422)

    async def test_get_messages_nonexistent_session(self, async_client):
        resp = await async_client.get(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000/messages"
        )
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestSendMessages:
    """Test sending messages to sessions."""

    async def test_send_message_returns_answer(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Answer"}
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

    async def test_send_message_persists_user_message(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Persist"}
        )
        sid = create_resp.json()["id"]

        await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "My question", "top_k": 3},
        )

        msgs = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages"
        )
        user_msgs = [m for m in msgs.json() if m["role"] == "user"]
        assert len(user_msgs) >= 1
        assert user_msgs[0]["content"] == "My question"

    async def test_send_message_persists_assistant_message(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Assistant"}
        )
        sid = create_resp.json()["id"]

        await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Test", "top_k": 3},
        )

        msgs = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages"
        )
        asst_msgs = [m for m in msgs.json() if m["role"] == "assistant"]
        assert len(asst_msgs) >= 1

    async def test_send_multiple_messages(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Multi"}
        )
        sid = create_resp.json()["id"]

        for i in range(3):
            resp = await async_client.post(
                f"/api/v1/chat/sessions/{sid}/messages",
                json={"query": f"Question {i}", "top_k": 3},
            )
            assert resp.status_code == 200

        msgs = await async_client.get(
            f"/api/v1/chat/sessions/{sid}/messages"
        )
        assert len(msgs.json()) >= 6

    async def test_send_message_empty_query(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Empty"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "", "top_k": 3},
        )
        assert resp.status_code == 200

    async def test_send_message_nonexistent_session(self, async_client):
        resp = await async_client.post(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000/messages",
            json={"query": "Test", "top_k": 3},
        )
        assert resp.status_code == 404

    async def test_send_message_response_structure(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Structure"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Apa itu RAG?", "top_k": 3},
        )
        body = resp.json()
        assert "message_id" in body
        assert "answer" in body
        assert "sources" in body
        assert "images" in body
        assert isinstance(body["sources"], list)
        assert isinstance(body["images"], list)

    async def test_send_message_with_images_in_response(self, async_client):
        create_resp = await async_client.post(
            "/api/v1/chat/sessions", json={"title": "Images"}
        )
        sid = create_resp.json()["id"]

        resp = await async_client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"query": "Test", "top_k": 3},
        )
        body = resp.json()
        assert isinstance(body["images"], list)


import asyncio
