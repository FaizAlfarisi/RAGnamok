import os

import psycopg2
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "::1"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "ragdb"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "change-me"),
)
cur = conn.cursor()
cur.execute("SELECT id FROM document_chunks WHERE element_type = 'Image'")
active = {str(r[0]) for r in cur.fetchall()}
cur.close()
conn.close()

img_dir = Path(__file__).resolve().parent.parent / "data" / "images"
stale = [f for f in img_dir.iterdir() if f.suffix == ".jpg" and f.stem not in active]
print(f"Active images: {len(active)}")
print(f"Stale images: {len(stale)}")
for f in stale:
    f.unlink()
    print(f"  Deleted: {f.name}")
if not stale:
    print("  None to delete")
