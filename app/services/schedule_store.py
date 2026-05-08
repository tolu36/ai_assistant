import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List

from dateutil import parser as dateutil_parser

from config import SCHEDULER_DB_PATH


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    db_path = db_path or SCHEDULER_DB_PATH
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schedule_proposals (
            id TEXT PRIMARY KEY,
            task_text TEXT NOT NULL,
            parsed_json TEXT NOT NULL,
            slots_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            feedback TEXT NOT NULL DEFAULT ''
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduler_constraints (
            id TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            start_hour INTEGER,
            end_hour INTEGER,
            raw_feedback TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return connection


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _serialize_slots(slots: List[Dict[str, datetime]]) -> List[Dict[str, str]]:
    return [
        {
            "start": slot["start"].isoformat(),
            "end": slot["end"].isoformat(),
        }
        for slot in slots
    ]


def _deserialize_slots(slots: List[Dict[str, str]]) -> List[Dict[str, datetime]]:
    return [
        {
            "start": dateutil_parser.parse(slot["start"]),
            "end": dateutil_parser.parse(slot["end"]),
        }
        for slot in slots
    ]


def create_proposal(
    task_text: str,
    parsed: Dict[str, Any],
    slots: List[Dict[str, datetime]],
    db_path: str | None = None,
) -> Dict[str, Any]:
    proposal_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    stored_slots = _serialize_slots(slots)

    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO schedule_proposals
                (id, task_text, parsed_json, slots_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                task_text,
                json.dumps(parsed, default=_json_default),
                json.dumps(stored_slots),
                "proposed",
                now,
            ),
        )

    return {
        "id": proposal_id,
        "task_text": task_text,
        "parsed": parsed,
        "slots": stored_slots,
        "status": "proposed",
        "created_at": now,
        "feedback": "",
    }


def get_proposal(proposal_id: str, db_path: str | None = None) -> Dict[str, Any] | None:
    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, task_text, parsed_json, slots_json, status, created_at, feedback
            FROM schedule_proposals
            WHERE id = ?
            """,
            (proposal_id,),
        ).fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "task_text": row["task_text"],
        "parsed": json.loads(row["parsed_json"]),
        "slots": json.loads(row["slots_json"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "feedback": row["feedback"],
    }


def update_proposal_slots(
    proposal_id: str,
    slots: List[Dict[str, datetime]],
    feedback: str = "",
    db_path: str | None = None,
) -> Dict[str, Any] | None:
    stored_slots = _serialize_slots(slots)
    with _connect(db_path) as connection:
        connection.execute(
            """
            UPDATE schedule_proposals
            SET slots_json = ?, status = ?, feedback = ?
            WHERE id = ?
            """,
            (json.dumps(stored_slots), "revised", feedback, proposal_id),
        )

    return get_proposal(proposal_id, db_path=db_path)


def mark_proposal_confirmed(proposal_id: str, db_path: str | None = None) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE schedule_proposals SET status = ? WHERE id = ?",
            ("confirmed", proposal_id),
        )


def add_constraint(
    reason: str,
    raw_feedback: str,
    start_hour: int | None = None,
    end_hour: int | None = None,
    db_path: str | None = None,
) -> Dict[str, Any]:
    constraint_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO scheduler_constraints
                (id, reason, start_hour, end_hour, raw_feedback, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (constraint_id, reason, start_hour, end_hour, raw_feedback, now),
        )

    return {
        "id": constraint_id,
        "reason": reason,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "raw_feedback": raw_feedback,
        "created_at": now,
    }


def list_constraints(db_path: str | None = None) -> List[Dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, reason, start_hour, end_hour, raw_feedback, created_at
            FROM scheduler_constraints
            ORDER BY created_at
            """
        ).fetchall()

    return [dict(row) for row in rows]


def proposal_slots_as_datetimes(proposal: Dict[str, Any]) -> List[Dict[str, datetime]]:
    return _deserialize_slots(proposal["slots"])
