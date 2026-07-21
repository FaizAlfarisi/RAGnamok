"""Minimal conftest for mocked tests — no database or external infra needed.

Overrides the session-scoped root conftest fixtures so mocked tests can
run without Postgres, Ollama, or API keys.
"""

import pytest_asyncio


# ---------------------------------------------------------------------------
# Override root conftest's autouse DB fixture with a no-op
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """No-op override — skip DB creation for mocked tests."""
    yield
