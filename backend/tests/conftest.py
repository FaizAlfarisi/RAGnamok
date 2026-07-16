"""Pytest configuration — real PostgreSQL + real Ollama + real Embeddings.

Creates a dedicated test database `ragdb_test`, runs all migrations,
and provides async test fixtures. Database is dropped after the session.
"""

import os

# ---------------------------------------------------------------------------
# CRITICAL: Override DB before ANY app module is imported.
# ---------------------------------------------------------------------------
os.environ["DB_NAME"] = "ragdb_test"

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

# Must come after env var is set
from app.config import settings  # noqa: E402

settings.db_name = "ragdb_test"


def _test_db_url() -> str:
    host = f"[{settings.db_host}]" if ":" in settings.db_host else settings.db_host
    return (
        f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}"
        f"@{host}:{settings.db_port}/{settings.db_name}"
    )


def _admin_db_url() -> str:
    host = f"[{settings.db_host}]" if ":" in settings.db_host else settings.db_host
    return (
        f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}"
        f"@{host}:{settings.db_port}/postgres"
    )


# Fresh engine with NullPool — no connection-reuse issues between tests
test_engine = create_async_engine(
    _test_db_url(), echo=False, poolclass=NullPool
)
test_async_session = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_test_db():
    admin_engine = create_async_engine(
        _admin_db_url(), isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as conn:
        for attempt in range(3):
            try:
                await conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                        "FROM pg_stat_activity "
                        "WHERE pg_stat_activity.datname = 'ragdb_test' "
                        "AND pid <> pg_backend_pid()"
                    )
                )
            except Exception:
                pass
            try:
                await conn.execute(text("DROP DATABASE IF EXISTS ragdb_test"))
            except Exception:
                pass
            try:
                await conn.execute(text("CREATE DATABASE ragdb_test"))
                break
            except Exception as e:
                if attempt == 2:
                    raise
    await admin_engine.dispose()


async def _drop_test_db():
    admin_engine = create_async_engine(
        _admin_db_url(), isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as conn:
        try:
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                    "FROM pg_stat_activity "
                    "WHERE pg_stat_activity.datname = 'ragdb_test' "
                    "AND pid <> pg_backend_pid()"
                )
            )
        except Exception:
            pass
        try:
            await conn.execute(text("DROP DATABASE IF EXISTS ragdb_test"))
        except Exception:
            pass
    await admin_engine.dispose()


async def _run_migrations():
    """Run all *.sql migration files against the test database."""
    base = Path(__file__).parent.parent / "db" / "migrations"
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        for fname in sorted(base.glob("*.sql")):
            sql = fname.read_text()
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    await conn.execute(text(stmt))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Session-scoped: create test DB, run migrations, dispose after."""
    await _create_test_db()
    await _run_migrations()
    yield
    await test_engine.dispose()
    await _drop_test_db()


@pytest_asyncio.fixture
async def db_session():
    """Per-test session. CRUD functions manage their own transactions."""
    async with test_async_session() as session:
        yield session


@pytest_asyncio.fixture
async def async_client():
    """FastAPI test client against the real app (patched with test engine)."""
    import app.db.connection as conn_mod

    conn_mod.engine = test_engine
    conn_mod.async_session = test_async_session
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Sample PDF
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_pdf() -> bytes:
    return _make_minimal_pdf("Test Content \u2014 Hello RAGnamok")


def _make_minimal_pdf(text_content: str) -> bytes:
    content_hex = text_content.encode("latin-1", errors="replace").hex()
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Pages 2 0 R >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
        b"4 0 obj\n"
        b"<< /Length 44 >>\n"
        b"stream\n"
        b"BT /F1 12 Tf 100 700 Td <" + content_hex.encode() + b"> Tj ET\n"
        b"endstream\n"
        b"endobj\n"
        b"5 0 obj\n"
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
        b"endobj\n"
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000361 00000 n \n"
        b"trailer\n"
        b"<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n"
        b"437\n"
        b"%%EOF\n"
    )
    return pdf
