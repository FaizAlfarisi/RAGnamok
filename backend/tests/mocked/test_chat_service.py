"""Unit tests for handle_chat_message — mocks every external dependency."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.chat_service import handle_chat_message


def _mock_context(texts: list[str] | None = None, images: list[str] | None = None):
    return {"texts": texts or [], "images": images or []}


@pytest.mark.asyncio
async def test_demo_mode_skips_history():
    """When demo_mode=True, get_chat_history should NOT be called."""
    mock_history = AsyncMock()
    with (
        patch("app.services.chat_service.settings.demo_mode", True),
        patch(
            "app.services.chat_service.retrieve_context",
            new=AsyncMock(return_value=_mock_context()),
        ),
        patch(
            "app.services.chat_service.generate_answer",
            new=AsyncMock(return_value="demo answer"),
        ),
        patch(
            "app.services.chat_service.save_message",
            new=AsyncMock(side_effect=["msg-user", "msg-assistant"]),
        ),
        patch("app.services.chat_service.touch_session", new=AsyncMock()),
        patch("app.services.chat_service.get_chat_history", new=mock_history),
    ):
        result = await handle_chat_message(
            AsyncMock(), "session-1", "halo", top_k=5, history_depth=6
        )

    mock_history.assert_not_called()
    assert result["answer"] == "demo answer"


@pytest.mark.asyncio
async def test_normal_mode_loads_history():
    """When demo_mode=False, get_chat_history should be called with correct depth."""
    mock_history = AsyncMock(return_value=[{"role": "user", "content": "prev"}])
    with (
        patch("app.services.chat_service.settings.demo_mode", False),
        patch(
            "app.services.chat_service.retrieve_context",
            new=AsyncMock(return_value=_mock_context(texts=["ctx"])),
        ),
        patch(
            "app.services.chat_service.generate_answer",
            new=AsyncMock(return_value="answer"),
        ),
        patch(
            "app.services.chat_service.save_message",
            new=AsyncMock(side_effect=["m1", "m2"]),
        ),
        patch("app.services.chat_service.touch_session", new=AsyncMock()),
        patch("app.services.chat_service.get_chat_history", new=mock_history),
    ):
        result = await handle_chat_message(
            AsyncMock(), "sid", "query", top_k=3, history_depth=4
        )

    mock_history.assert_called_once()
    assert mock_history.call_args[1]["depth"] == 4
    assert result["answer"] == "answer"


@pytest.mark.asyncio
async def test_history_depth_default():
    """history_depth parameter flows through to get_chat_history."""
    mock_history = AsyncMock(return_value=[])
    with (
        patch("app.services.chat_service.settings.demo_mode", False),
        patch(
            "app.services.chat_service.retrieve_context",
            new=AsyncMock(return_value=_mock_context()),
        ),
        patch(
            "app.services.chat_service.generate_answer",
            new=AsyncMock(return_value="ans"),
        ),
        patch(
            "app.services.chat_service.save_message",
            new=AsyncMock(side_effect=["x", "y"]),
        ),
        patch("app.services.chat_service.touch_session", new=AsyncMock()),
        patch("app.services.chat_service.get_chat_history", new=mock_history),
    ):
        await handle_chat_message(AsyncMock(), "s", "q")

    assert mock_history.call_args[1]["depth"] == 6


@pytest.mark.asyncio
async def test_history_depth_zero_in_demo():
    """Even with depth=0, demo mode still skips history."""
    mock_history = AsyncMock()
    with (
        patch("app.services.chat_service.settings.demo_mode", True),
        patch(
            "app.services.chat_service.retrieve_context",
            new=AsyncMock(return_value=_mock_context()),
        ),
        patch(
            "app.services.chat_service.generate_answer",
            new=AsyncMock(return_value="ans"),
        ),
        patch(
            "app.services.chat_service.save_message",
            new=AsyncMock(side_effect=["x", "y"]),
        ),
        patch("app.services.chat_service.touch_session", new=AsyncMock()),
        patch("app.services.chat_service.get_chat_history", new=mock_history),
    ):
        await handle_chat_message(AsyncMock(), "s", "q", history_depth=0)

    mock_history.assert_not_called()


@pytest.mark.asyncio
async def test_passes_context_to_generate():
    """retrieve_context output feeds into generate_answer as context."""
    mock_retrieve = AsyncMock(
        return_value=_mock_context(texts=["src1"], images=["img1"])
    )
    mock_generate = AsyncMock(return_value="ans")
    with (
        patch("app.services.chat_service.settings.demo_mode", False),
        patch("app.services.chat_service.retrieve_context", new=mock_retrieve),
        patch("app.services.chat_service.generate_answer", new=mock_generate),
        patch(
            "app.services.chat_service.save_message",
            new=AsyncMock(side_effect=["x", "y"]),
        ),
        patch("app.services.chat_service.touch_session", new=AsyncMock()),
        patch(
            "app.services.chat_service.get_chat_history",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await handle_chat_message(AsyncMock(), "s", "q")

    mock_generate.assert_called_once()
    ctx_arg = mock_generate.call_args[0][0]
    assert ctx_arg["texts"] == ["src1"]
    assert ctx_arg["images"] == ["img1"]
    assert result["sources"] == ["src1"]
    assert result["images"] == ["img1"]


@pytest.mark.asyncio
async def test_handles_generation_failure():
    """When generate_answer raises, a fallback message is returned."""
    with (
        patch("app.services.chat_service.settings.demo_mode", False),
        patch(
            "app.services.chat_service.retrieve_context",
            new=AsyncMock(return_value=_mock_context()),
        ),
        patch(
            "app.services.chat_service.generate_answer",
            new=AsyncMock(side_effect=Exception("LLM unavailable")),
        ),
        patch(
            "app.services.chat_service.save_message",
            new=AsyncMock(side_effect=["m1", "m2"]),
        ),
        patch("app.services.chat_service.touch_session", new=AsyncMock()),
        patch(
            "app.services.chat_service.get_chat_history",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await handle_chat_message(AsyncMock(), "s", "q")

    assert result["answer"] == "_Maaf, gagal menghasilkan jawaban. Silakan coba lagi._"


@pytest.mark.asyncio
async def test_saves_both_messages():
    """User query and assistant answer are both persisted."""
    mock_save = AsyncMock()
    with (
        patch("app.services.chat_service.settings.demo_mode", True),
        patch(
            "app.services.chat_service.retrieve_context",
            new=AsyncMock(return_value=_mock_context()),
        ),
        patch(
            "app.services.chat_service.generate_answer",
            new=AsyncMock(return_value="hello back"),
        ),
        patch("app.services.chat_service.save_message", new=mock_save),
        patch("app.services.chat_service.touch_session", new=AsyncMock()),
        patch("app.services.chat_service.get_chat_history", new=AsyncMock()),
    ):
        await handle_chat_message(AsyncMock(), "s", "hai", top_k=5, history_depth=6)

    assert mock_save.call_count == 2
    first_call_args = mock_save.call_args_list[0]
    assert first_call_args[0][2] == "user"
    assert first_call_args[0][3] == "hai"

    second_call_args = mock_save.call_args_list[1]
    assert second_call_args[0][2] == "assistant"
    assert second_call_args[0][3] == "hello back"


@pytest.mark.asyncio
async def test_touches_session_on_success():
    """Session timestamp is updated after successful generation."""
    mock_touch = AsyncMock()
    db_session = AsyncMock()
    with (
        patch("app.services.chat_service.settings.demo_mode", True),
        patch(
            "app.services.chat_service.retrieve_context",
            new=AsyncMock(return_value=_mock_context()),
        ),
        patch(
            "app.services.chat_service.generate_answer",
            new=AsyncMock(return_value="ok"),
        ),
        patch(
            "app.services.chat_service.save_message",
            new=AsyncMock(side_effect=["a", "b"]),
        ),
        patch("app.services.chat_service.touch_session", new=mock_touch),
        patch("app.services.chat_service.get_chat_history", new=AsyncMock()),
    ):
        await handle_chat_message(db_session, "s", "q")

    mock_touch.assert_called_once_with(db_session, "s")


@pytest.mark.asyncio
async def test_returns_message_id():
    """Return dict includes the assistant message ID."""
    mock_save = AsyncMock(side_effect=["user-msg-id", "assistant-msg-id"])
    with (
        patch("app.services.chat_service.settings.demo_mode", True),
        patch(
            "app.services.chat_service.retrieve_context",
            new=AsyncMock(return_value=_mock_context()),
        ),
        patch(
            "app.services.chat_service.generate_answer",
            new=AsyncMock(return_value="ans"),
        ),
        patch("app.services.chat_service.save_message", new=mock_save),
        patch("app.services.chat_service.touch_session", new=AsyncMock()),
        patch("app.services.chat_service.get_chat_history", new=AsyncMock()),
    ):
        result = await handle_chat_message(AsyncMock(), "s", "q")

    assert result["message_id"] == "assistant-msg-id"
