import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def _run_with_retry(coro_factory, retries=3, delay=1.0):
    last_exc = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except OperationalError as e:
            last_exc = e
            if attempt < retries - 1:
                await asyncio.sleep(delay * (2 ** attempt))
    raise last_exc


async def init_db():
    await _run_with_retry(lambda: _init_db_once())


async def _init_db_once():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        base = Path(__file__).parent.parent.parent / "db" / "migrations"
        for fname in sorted(base.glob("*.sql")):
            sql = fname.read_text()
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    await conn.execute(text(stmt))
