"""Comprehensive health check tests."""

import pytest


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test /api/v1/health endpoint."""

    async def test_health_returns_ok(self, async_client):
        resp = await async_client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    async def test_health_has_services(self, async_client):
        resp = await async_client.get("/api/v1/health")
        body = resp.json()
        assert "services" in body
        assert isinstance(body["services"], dict)

    async def test_health_database_ok(self, async_client):
        resp = await async_client.get("/api/v1/health")
        body = resp.json()
        assert body["services"]["database"] == "ok"

    async def test_health_has_ollama_status(self, async_client):
        resp = await async_client.get("/api/v1/health")
        body = resp.json()
        assert "ollama" in body["services"]

    async def test_health_status_field_values(self, async_client):
        resp = await async_client.get("/api/v1/health")
        body = resp.json()
        assert body["status"] in ("ok", "degraded")

    async def test_health_method_not_allowed(self, async_client):
        resp = await async_client.post("/api/v1/health")
        assert resp.status_code == 405

    async def test_health_no_request_body(self, async_client):
        resp = await async_client.get("/api/v1/health")
        assert resp.status_code == 200
        assert "status" in resp.json()
