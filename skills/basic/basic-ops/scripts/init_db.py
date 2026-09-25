"""Create an empty records database at the given path."""

import asyncio
import json
from pathlib import Path
import sqlite3
import sys
import traceback

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    embedding BLOB NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


async def run(db_path: str) -> str:
    """Create an empty records database at ``db_path``.

    Builds the parent directories if needed and initialises the ``notes``
    table. If the file already exists it is left untouched and reported as
    existing.

    Args:
        db_path: Absolute path to the records database file to create.
    """
    try:
        path = Path(db_path)
        if path.exists():
            return json.dumps({"path": str(path), "status": "exists"})
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        try:
            conn.execute(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()
        return json.dumps({"path": str(path), "status": "created"})
    except Exception:
        return json.dumps({"error": traceback.format_exc()})


if __name__ == "__main__":
    args = json.loads(sys.stdin.read())
    result = asyncio.run(run(**args))
    print(result)
