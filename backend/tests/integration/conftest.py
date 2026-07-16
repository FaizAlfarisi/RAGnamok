"""Integration test conftest — clears document/chunk data before each test."""

import pytest_asyncio
from sqlalchemy import text

from tests.conftest import test_async_session


@pytest_asyncio.fixture(autouse=True)
async def _clean_integration_data():
    """Remove leftover document/chunk data between tests."""
    async with test_async_session() as session:
        await session.execute(text("DELETE FROM chunk_summaries"))
        await session.execute(text("DELETE FROM document_chunks"))
        await session.execute(text("DELETE FROM documents"))
        await session.commit()
    yield
