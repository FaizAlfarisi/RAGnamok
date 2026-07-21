import logging

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)
JINA_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"


async def _embed(inputs: list[str], task: str) -> list[list[float]]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(
                JINA_URL,
                headers={
                    "Authorization": f"Bearer {settings.jina_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": JINA_MODEL,
                    "input": inputs,
                    "task": task,
                    "dimensions": 1024,
                },
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return [item["embedding"] for item in data["data"]]
    except Exception as e:
        logger.error("Jina embedding failed: %s", e)
        return [[0.0] * 1024 for _ in inputs]


async def embed_text(text: str) -> list[float]:
    return (await _embed([text], "retrieval.query"))[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    return await _embed(texts, "retrieval.passage")
