"""Unit-test-only conftest — clears document/chunk data before each test."""

import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(autouse=True)
async def _clean_test_data(db_session):
    """Remove data left by integration tests so unit tests start clean."""
    await db_session.execute(text("DELETE FROM chunk_summaries"))
    await db_session.execute(text("DELETE FROM document_chunks"))
    await db_session.execute(text("DELETE FROM documents"))
    await db_session.commit()
    yield
