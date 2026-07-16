import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "::1"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "ragdb"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "change-me"),
)
cur = conn.cursor()

cur.execute("SELECT id, filename, created_at FROM documents ORDER BY created_at")
docs = cur.fetchall()
print(f"Documents: {len(docs)}")
for d in docs:
    print(f"  {d[0]} {d[1]} {d[2]}")

if len(docs) > 1:
    # Keep only the latest document, delete older ones
    keep = docs[-1][0]
    for d in docs[:-1]:
        old_id = d[0]
        cur.execute("DELETE FROM chunk_summaries WHERE chunk_id IN (SELECT id FROM document_chunks WHERE doc_id = %s)", (old_id,))
        cur.execute("DELETE FROM document_chunks WHERE doc_id = %s", (old_id,))
        cur.execute("DELETE FROM documents WHERE id = %s", (old_id,))
        print(f"Deleted old document: {old_id}")
    conn.commit()
    print("Cleanup done")

cur.execute("SELECT id, filename, created_at FROM documents ORDER BY created_at")
for d in cur.fetchall():
    print(f"Remaining: {d[0]} {d[1]} {d[2]}")
cur.execute("SELECT COUNT(*) FROM document_chunks")
print(f"Chunks: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM chunk_summaries")
print(f"Summaries: {cur.fetchone()[0]}")

cur.close()
conn.close()
