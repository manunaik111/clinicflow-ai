"""
database.py: saves every processed patient message to a local SQLite database.

The dashboard will read from here to show a history of what ClinicFlow AI did.
SQLite is built into Python, so there is nothing extra to install. The database
is one file (clinicflow.db) created automatically the first time it is needed.

Note: use synthetic (fake) messages only. This is a demo project.

Check the database from the main clinicflow-ai folder:
    python -m app.database
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DATABASE_PATH


@contextmanager
def _connect():
    """Open the database, save changes when done, and always close it."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the requests table if it does not exist yet."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at         TEXT    NOT NULL,
                prompt_version     TEXT,
                message            TEXT    NOT NULL,
                category           TEXT,
                needs_human        INTEGER NOT NULL DEFAULT 0,
                reply              TEXT,
                staff_alert        TEXT,
                details            TEXT,
                retrieved_sections TEXT
            )
            """
        )


def log_request(result: dict, prompt_version: str) -> int:
    """Save one finished workflow result and return its new row id."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO requests
                (created_at, prompt_version, message, category, needs_human,
                 reply, staff_alert, details, retrieved_sections)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                prompt_version,
                result.get("message", ""),
                result.get("category"),
                1 if result.get("needs_human") else 0,
                result.get("reply"),
                result.get("staff_alert"),
                json.dumps(result.get("details", {})),
                json.dumps(result.get("retrieved_sections", [])),
            ),
        )
        return cursor.lastrowid


def get_recent_requests(limit: int = 50) -> list[dict]:
    """Return the most recent requests, newest first, as plain dictionaries."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    requests = []
    for row in rows:
        item = dict(row)
        item["needs_human"] = bool(item["needs_human"])
        item["details"] = json.loads(item["details"] or "{}")
        item["retrieved_sections"] = json.loads(item["retrieved_sections"] or "[]")
        requests.append(item)
    return requests


def get_stats() -> dict:
    """Summary numbers for the top of the dashboard."""
    init_db()
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        needs_human = conn.execute(
            "SELECT COUNT(*) FROM requests WHERE needs_human = 1"
        ).fetchone()[0]
        by_category = conn.execute(
            "SELECT category, COUNT(*) AS n FROM requests GROUP BY category"
        ).fetchall()

    return {
        "total": total,
        "needs_human": needs_human,
        "by_category": {row["category"]: row["n"] for row in by_category},
    }


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DATABASE_PATH}")
    print(f"Stats: {get_stats()}")
