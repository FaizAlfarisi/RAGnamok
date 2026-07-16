"""Test health endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health(async_client):
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["services"]["database"] == "ok"
