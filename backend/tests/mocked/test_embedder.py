"""Unit tests for Jina AI embedder — no external calls needed."""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embedder import embed_text, embed_batch


def _mock_jina_client(
    data_length: int = 1,
    status_code: int = 200,
    dim: int = 1024,
    post_side_effect: Exception | None = None,
) -> tuple[patch, MagicMock]:
    """Patch httpx.AsyncClient so the embedder talks to a mock instead of Jina.

    Returns (patcher, mock_client) where mock_client can be used for call
    assertions.  Caller MUST invoke patcher.stop() in a finally block.
    """
    patcher = patch("app.services.embedder.httpx.AsyncClient")
    mock_ctor = patcher.start()

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status_code
    mock_response.json.return_value = {
        "data": [
            {"embedding": [0.42] * dim, "index": i, "object": "embedding"}
            for i in range(data_length)
        ],
        "model": "jina-embeddings-v3",
        "object": "list",
        "usage": {"total_tokens": data_length, "prompt_tokens": data_length},
    }

    mock_client = mock_ctor.return_value
    mock_client.__aenter__.return_value = mock_client

    if post_side_effect:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_client.post = AsyncMock(return_value=mock_response)

    return patcher, mock_client


@pytest.mark.asyncio
async def test_embed_text_returns_1024_floats():
    patcher, _ = _mock_jina_client(data_length=1)
    try:
        result = await embed_text("halo")
    finally:
        patcher.stop()

    assert isinstance(result, list)
    assert len(result) == 1024
    assert all(isinstance(v, float) for v in result)


@pytest.mark.asyncio
async def test_embed_text_values_are_distinct():
    patcher, _ = _mock_jina_client(data_length=1)
    try:
        result = await embed_text("halo")
    finally:
        patcher.stop()

    assert all(v == 0.42 for v in result), "all dims should be 0.42"
    assert len(set(result)) == 1


@pytest.mark.asyncio
async def test_embed_batch_returns_multiple_embeddings():
    patcher, _ = _mock_jina_client(data_length=3)
    try:
        results = await embed_batch(["a", "b", "c"])
    finally:
        patcher.stop()

    assert isinstance(results, list)
    assert len(results) == 3
    assert all(len(e) == 1024 for e in results)


@pytest.mark.asyncio
async def test_embed_batch_single_item():
    patcher, _ = _mock_jina_client(data_length=1)
    try:
        results = await embed_batch(["single"])
    finally:
        patcher.stop()

    assert len(results) == 1
    assert len(results[0]) == 1024


@pytest.mark.asyncio
async def test_sends_correct_headers_and_payload():
    patcher, mock_client = _mock_jina_client()
    try:
        await embed_text("test query")
    finally:
        patcher.stop()

    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args

    url = args[0]
    assert url == "https://api.jina.ai/v1/embeddings"

    headers = kwargs["headers"]
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Bearer ")
    assert "Content-Type" in headers
    assert headers["Content-Type"] == "application/json"

    body = kwargs["json"]
    assert body["model"] == "jina-embeddings-v3"
    assert body["input"] == ["test query"]
    assert body["task"] == "retrieval.query"
    assert body["dimensions"] == 1024


@pytest.mark.asyncio
async def test_embed_batch_uses_passage_task():
    patcher, mock_client = _mock_jina_client(data_length=2)
    try:
        await embed_batch(["passage1", "passage2"])
    finally:
        patcher.stop()

    body = mock_client.post.call_args[1]["json"]
    assert body["task"] == "retrieval.passage"
    assert body["input"] == ["passage1", "passage2"]


@pytest.mark.asyncio
async def test_raise_on_http_error():
    err = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=MagicMock(),
        response=MagicMock(status_code=401),
    )
    patcher, _ = _mock_jina_client(post_side_effect=err)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await embed_text("halo")
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_raise_on_network_error():
    patcher, _ = _mock_jina_client(
        post_side_effect=httpx.ConnectError("connection refused")
    )
    try:
        with pytest.raises(httpx.ConnectError):
            await embed_text("halo")
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_raise_on_timeout():
    patcher, _ = _mock_jina_client(post_side_effect=httpx.TimeoutException("timed out"))
    try:
        with pytest.raises(httpx.TimeoutException):
            await embed_text("halo")
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_empty_batch_returns_empty_list():
    patcher, _ = _mock_jina_client(data_length=0)
    try:
        results = await embed_batch([])
    finally:
        patcher.stop()

    assert results == []


@pytest.mark.asyncio
async def test_raises_on_malformed_response():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}

    patcher = patch("app.services.embedder.httpx.AsyncClient")
    mock_ctor = patcher.start()
    mock_ctor.return_value.__aenter__.return_value = mock_ctor.return_value
    mock_ctor.return_value.post = AsyncMock(return_value=mock_response)
    try:
        with pytest.raises(IndexError):
            await embed_text("halo")
    finally:
        patcher.stop()
