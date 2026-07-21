"""Test health endpoint — accepts both ok and degraded states."""

import os

import pytest


@pytest.mark.asyncio
async def test_health(async_client):
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["services"]["database"] == "ok"


@pytest.mark.asyncio
async def test_health_contains_ollama_check(async_client):
    """Health endpoint now pings Ollama Cloud (not localhost)."""
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "ollama" in data["services"]
    assert (
        "error" in data["services"]["ollama"]
        if not os.getenv("OLLAMA_API_KEY")
        else True
    )
