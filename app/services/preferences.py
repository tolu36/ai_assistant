import os
import sqlite3
from typing import Any, Dict, List

from app.services import dynamodb_store
from config import FINANCE_WATCHLIST, PREFERENCES_DB_PATH, SPORTS_INTERESTS, SPORTS_TEAMS


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_csv(name: str, default: str) -> List[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        value = default
    return _split_csv(value)


def _clean_values(values: Any) -> List[str]:
    cleaned = []
    seen = set()
    for value in values or []:
        item = str(value).strip()
        key = item.lower()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


def default_preferences() -> Dict[str, List[str]]:
    return {
        "sports_interests": _env_csv("SPORTS_INTERESTS", SPORTS_INTERESTS),
        "sports_teams": _env_csv("SPORTS_TEAMS", SPORTS_TEAMS),
        "finance_watchlist": _env_csv("FINANCE_WATCHLIST", FINANCE_WATCHLIST),
    }


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    db_path = db_path or PREFERENCES_DB_PATH
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            category TEXT NOT NULL,
            value TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (category, value)
        )
        """
    )
    return connection


def load_preferences(db_path: str | None = None) -> Dict[str, List[str]]:
    preferences = default_preferences()
    if db_path is None and dynamodb_store.is_dynamodb_enabled():
        return dynamodb_store.load_preferences(preferences)

    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT category, value
            FROM user_preferences
            ORDER BY category, position, value
            """
        ).fetchall()

    stored = {key: [] for key in preferences}
    for row in rows:
        category = row["category"]
        if category in stored:
            stored[category].append(row["value"])

    for key, values in stored.items():
        if values:
            preferences[key] = values

    return preferences


def save_preferences(preferences: Dict[str, Any], db_path: str | None = None) -> Dict[str, List[str]]:
    current = load_preferences(db_path)
    for key in current:
        if key in preferences:
            current[key] = _clean_values(preferences[key])

    if db_path is None and dynamodb_store.is_dynamodb_enabled():
        return dynamodb_store.save_preferences(current)

    with _connect(db_path) as connection:
        for category, values in current.items():
            connection.execute("DELETE FROM user_preferences WHERE category = ?", (category,))
            connection.executemany(
                """
                INSERT INTO user_preferences (category, value, position)
                VALUES (?, ?, ?)
                """,
                [(category, value, index) for index, value in enumerate(values)],
            )

    return current
