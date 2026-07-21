"""Seed the demo database from db_dump.sql.

Usage:
    python -m backend.scripts.seed_demo

Requires DB to be running and .env to have JINA_API_KEY and DB credentials set.
"""

import ast
import asyncio
import logging
import os
import re
import sys
from pathlib import Path

# Allow running as `python -m backend.scripts.seed_demo`
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text as sa_text

# Needs env before importing app modules
os.environ.setdefault("DEMO_MODE", "true")

from app.config import settings
from app.db.connection import async_session, engine
from app.services.embedder import embed_batch

logger = logging.getLogger(__name__)

DUMP_PATH = Path(__file__).parent.parent.parent / "db_dump.sql"

# ---------------------------------------------------------------------------
# COPY-format helpers
# ---------------------------------------------------------------------------


def _unescape(field: str) -> str | None:
    """Unescape a single PostgreSQL COPY text-format field."""
    if field == r"\N":
        return None
    chars = []
    i = 0
    while i < len(field):
        if field[i] == "\\" and i + 1 < len(field):
            n = field[i + 1]
            if n == "\\":
                chars.append("\\")
            elif n == "n":
                chars.append("\n")
            elif n == "t":
                chars.append("\t")
            elif n == "r":
                chars.append("\r")
            else:
                chars.append(field[i])
                i += 1
                continue
            i += 2
        else:
            chars.append(field[i])
            i += 1
    return "".join(chars)


def parse_copy_line(line: str) -> list:
    """Split a COPY data line into tab-separated, unescaped fields."""
    fields = []
    buf = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            buf.append(line[i : i + 2])
            i += 2
            continue
        if c == "\t":
            fields.append(_unescape("".join(buf)))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    fields.append(_unescape("".join(buf)))
    return fields


# ---------------------------------------------------------------------------
# Dump parser
# ---------------------------------------------------------------------------


def parse_dump(path: str | Path) -> dict:
    """Return {table_name: {columns: [...], rows: [field_lists...]}}."""
    text = Path(path).read_text(encoding="utf-8")

    sections: list[dict] = []
    # Split on COPY ... FROM stdin;
    # We need to locate COPY lines and their data up to \.
    lines = text.split("\n")

    i = 0
    in_data = False
    current = None

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # Detect COPY header
        m = re.match(
            r"^COPY public\.(\w+) \((.+)\) FROM stdin;", stripped
        )
        if m and not in_data:
            current = {
                "table": m.group(1),
                "columns": [c.strip() for c in m.group(2).split(",")],
                "rows": [],
            }
            in_data = True
            i += 1
            continue

        # Detect end of COPY data
        if stripped == r"\." and in_data and current is not None:
            sections.append(current)
            current = None
            in_data = False
            i += 1
            continue

        # Data line
        if in_data and current is not None:
            # Skip empty lines within data block
            if raw.strip():
                current["rows"].append(parse_copy_line(raw.rstrip("\n").rstrip("\r")))
            i += 1
            continue

        i += 1

    return sections


# ---------------------------------------------------------------------------
# Main seeder
# ---------------------------------------------------------------------------


async def seed():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    dump_path = DUMP_PATH
    if not dump_path.exists():
        logger.error("db_dump.sql not found at %s", dump_path)
        sys.exit(1)

    logger.info("Parsing dump: %s", dump_path)
    sections = parse_dump(str(dump_path))

    # Build a lookup of table -> section
    tables = {s["table"]: s for s in sections}

    # --- 1. Ensure extension ---
    async with engine.begin() as conn:
        await conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))

    # --- 2. Create tables via init_db (runs migrations) ---
    from app.db.connection import init_db

    await init_db()

    # --- 3. Truncate existing data in reverse dependency order ---
    async with async_session() as session:
        for tbl in ("chat_messages", "chat_sessions", "chunk_summaries",
                    "document_chunks", "tasks", "documents"):
            await session.execute(sa_text(f"TRUNCATE TABLE public.{tbl} RESTART IDENTITY CASCADE"))
        await session.commit()
    logger.info("Tables truncated")

    # --- 4. Helper: insert rows via raw SQL ---
    async def insert_rows(table: str, columns: list[str], rows: list[list]):
        if not rows:
            return
        col_list = ", ".join(columns)
        placeholders = ", ".join([f":{c}" for c in columns])
        stmt = sa_text(f"INSERT INTO public.{table} ({col_list}) VALUES ({placeholders})")
        async with async_session() as session:
            for row in rows:
                params = dict(zip(columns, row))
                await session.execute(stmt, params)
            await session.commit()
        logger.info("  Inserted %d rows into %s", len(rows), table)

    # --- 5. Insert non-chunk_summaries tables ---
    skip = {"chunk_summaries"}
    for tbl_name, section in tables.items():
        if tbl_name in skip:
            continue
        await insert_rows(tbl_name, section["columns"], section["rows"])

    # --- 6. Handle chunk_summaries: re-embed with Jina AI ---
    cs = tables.get("chunk_summaries")
    if cs is None:
        logger.warning("No chunk_summaries found in dump")
        return

    # Build a map: chunk_id -> (chunk_summary_id, summary_text)
    chunk_map = {}  # chunk_id -> (summary_id, summary_text)
    for row in cs["rows"]:
        summary_id, chunk_id, summary_text = row[0], row[1], row[2]
        chunk_map[chunk_id] = (summary_id, summary_text or "")

    # Fetch original_content from inserted document_chunks for context
    async def get_chunk_content(chunk_id: str) -> str:
        async with async_session() as session:
            r = await session.execute(
                sa_text("SELECT original_content FROM public.document_chunks WHERE id = :id"),
                {"id": chunk_id},
            )
            row = r.fetchone()
            if row:
                row0 = row[0]
                return row0 if row0 is not None else ""
        return chunk_map.get(chunk_id, ("", ""))[1]  # fallback to summary

    # We embed the summary_text (matches original pipeline behaviour)
    summary_texts = []
    chunk_ids = []
    summary_ids = []
    for row in cs["rows"]:
        summary_id, chunk_id, summary_text = row[0], row[1], row[2]
        summary_ids.append(summary_id)
        chunk_ids.append(chunk_id)
        summary_texts.append(summary_text or "")

    logger.info("Generating %d embeddings via Jina AI ...", len(summary_texts))
    embeddings = await embed_batch(summary_texts)
    logger.info("Embeddings generated")

    # Insert chunk_summaries with new embeddings
    col_list = "id, chunk_id, summary_text, embedding"
    stmt = sa_text(
        f"INSERT INTO public.chunk_summaries ({col_list}) "
        f"VALUES (:id, :chunk_id, :summary_text, CAST(:embedding AS vector))"
    )
    async with async_session() as session:
        for sid, cid, stext, emb in zip(summary_ids, chunk_ids, summary_texts, embeddings):
            await session.execute(
                stmt,
                {
                    "id": sid,
                    "chunk_id": cid,
                    "summary_text": stext,
                    "embedding": str(emb),
                },
            )
        await session.commit()
    logger.info("Inserted %d chunk_summaries", len(summary_texts))

    # --- 7. Rebuild HNSW index ---
    async with engine.begin() as conn:
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_summaries_hnsw ON public.chunk_summaries "
                "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200)"
            )
        )
    logger.info("HNSW index created")

    logger.info("Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
