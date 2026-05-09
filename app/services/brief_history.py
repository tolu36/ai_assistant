import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services import dynamodb_store
from config import BRIEF_HISTORY_DB_PATH


def _db_path(db_path: str | None = None) -> str:
    return db_path or os.getenv("BRIEF_HISTORY_DB_PATH", BRIEF_HISTORY_DB_PATH)


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    resolved = _db_path(db_path)
    directory = os.path.dirname(resolved)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return sqlite3.connect(resolved)


def _ensure_db(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS morning_briefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brief_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    connection.commit()


def save_morning_brief(
    brief: Dict[str, Any],
    db_path: str | None = None,
) -> Dict[str, Any]:
    if db_path is None and dynamodb_store.is_dynamodb_enabled():
        return dynamodb_store.save_morning_brief(brief)

    created_at = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(brief, sort_keys=True, default=str)

    with _connect(db_path) as connection:
        _ensure_db(connection)
        cursor = connection.execute(
            """
            INSERT INTO morning_briefs (brief_date, created_at, payload_json)
            VALUES (?, ?, ?)
            """,
            (brief.get("date", ""), created_at, payload_json),
        )
        connection.commit()
        brief_id = int(cursor.lastrowid)

    return {
        "id": brief_id,
        "brief_date": brief.get("date", ""),
        "created_at": created_at,
        "brief": brief,
    }


def list_morning_briefs(
    limit: int = 10,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    if db_path is None and dynamodb_store.is_dynamodb_enabled():
        return dynamodb_store.list_morning_briefs(limit=limit)

    with _connect(db_path) as connection:
        _ensure_db(connection)
        rows = connection.execute(
            """
            SELECT id, brief_date, created_at
            FROM morning_briefs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(100, int(limit))),),
        ).fetchall()

    return [
        {"id": row[0], "brief_date": row[1], "created_at": row[2]}
        for row in rows
    ]


def get_morning_brief(
    brief_id: int | str,
    db_path: str | None = None,
) -> Dict[str, Any] | None:
    if db_path is None and dynamodb_store.is_dynamodb_enabled():
        return dynamodb_store.get_morning_brief(str(brief_id))

    try:
        sqlite_brief_id = int(brief_id)
    except (TypeError, ValueError):
        return None

    with _connect(db_path) as connection:
        _ensure_db(connection)
        row = connection.execute(
            """
            SELECT id, brief_date, created_at, payload_json
            FROM morning_briefs
            WHERE id = ?
            """,
            (sqlite_brief_id,),
        ).fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "brief_date": row[1],
        "created_at": row[2],
        "brief": json.loads(row[3]),
    }
