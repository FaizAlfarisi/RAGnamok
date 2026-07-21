import logging
import socket

import aiohttp
import httpx
from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["diagnose"])


async def _resolve(host: str) -> str:
    try:
        info = socket.getaddrinfo(host, 443)
        ips = list({addr[4][0] for addr in info})
        return f"ok ({', '.join(ips)})"
    except Exception as e:
        return f"error: {e}"


async def _httpx_get(url: str, **kw) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, **kw)
            return f"HTTP {r.status_code}"
    except Exception as e:
        return f"error: {e}"


async def _httpx_post(url: str, **kw) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, **kw)
            return f"HTTP {r.status_code}"
    except Exception as e:
        return f"error: {e}"


async def _httpx_post_stream(url: str, **kw) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            async with c.stream("POST", url, **kw) as r:
                return f"HTTP {r.status_code}"
    except Exception as e:
        return f"error: {e}"


async def _aiohttp_get(url: str, **kw) -> str:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
            async with s.get(url, **kw) as r:
                return f"HTTP {r.status}"
    except Exception as e:
        return f"error: {e}"


@router.get("/diagnose")
async def diagnose():
    ollama_url = settings.ollama_cloud_base_url.rstrip("/")
    auth = {"Authorization": f"Bearer {settings.ollama_api_key}"}

    return {
        "ollama": {
            "dns": await _resolve("ollama.com"),
            "httpx_get_tags": await _httpx_get(f"{ollama_url}/api/tags", headers=auth),
            "httpx_post_chat_nostream": await _httpx_post(
                f"{ollama_url}/api/chat",
                headers={**auth, "Content-Type": "application/json"},
                json={"model": settings.generation_model, "messages": [{"role": "user", "content": "hi"}], "stream": False},
            ),
            "httpx_post_chat_stream": await _httpx_post_stream(
                f"{ollama_url}/api/chat",
                headers={**auth, "Content-Type": "application/json"},
                json={"model": settings.generation_model, "messages": [{"role": "user", "content": "hi"}], "stream": True},
            ),
            "aiohttp_get_tags": await _aiohttp_get(f"{ollama_url}/api/tags", headers=auth),
        },
        "jina": {
            "dns": await _resolve("api.jina.ai"),
            "httpx_post_embed": await _httpx_post(
                "https://api.jina.ai/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.jina_api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": "jina-embeddings-v3", "input": ["test"], "task": "retrieval.query", "dimensions": 1024},
            ),
            "aiohttp_post_embed": await _aiohttp_post_embed(),
        },
    }


async def _aiohttp_post_embed() -> str:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
            async with s.post(
                "https://api.jina.ai/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.jina_api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": "jina-embeddings-v3", "input": ["test"], "task": "retrieval.query", "dimensions": 1024},
            ) as r:
                return f"HTTP {r.status}"
    except Exception as e:
        return f"error: {e}"
