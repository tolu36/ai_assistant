import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import quote

from app.services import dynamodb_store
from config import (
    NOTIFICATION_DB_PATH,
    PUSH_NOTIFICATIONS_ENABLED,
    PUSH_VAPID_PRIVATE_KEY,
    PUSH_VAPID_PUBLIC_KEY,
    PUSH_VAPID_SUBJECT,
)


class PushNotificationError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.lower() in ("1", "true", "yes")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _subscription_id(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:32]


def _db_path(db_path: str | None = None) -> str:
    return db_path or os.getenv("NOTIFICATION_DB_PATH", NOTIFICATION_DB_PATH)


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    resolved = _db_path(db_path)
    directory = os.path.dirname(resolved)
    if directory:
        os.makedirs(directory, exist_ok=True)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            endpoint_hash TEXT PRIMARY KEY,
            user_agent TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return connection


def _configured_public_key() -> str:
    return _env("PUSH_VAPID_PUBLIC_KEY", PUSH_VAPID_PUBLIC_KEY)


def _configured_private_key() -> str:
    return _env("PUSH_VAPID_PRIVATE_KEY", PUSH_VAPID_PRIVATE_KEY)


def _configured_subject() -> str:
    return _env("PUSH_VAPID_SUBJECT", PUSH_VAPID_SUBJECT)


def push_notifications_enabled() -> bool:
    return _env_bool("PUSH_NOTIFICATIONS_ENABLED", PUSH_NOTIFICATIONS_ENABLED)


def _normalize_subscription(subscription: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = str(subscription.get("endpoint", "")).strip()
    keys = subscription.get("keys")
    if not endpoint:
        raise PushNotificationError("Push subscription endpoint is missing.")
    if not isinstance(keys, dict):
        raise PushNotificationError("Push subscription keys are missing.")

    p256dh = str(keys.get("p256dh", "")).strip()
    auth = str(keys.get("auth", "")).strip()
    if not p256dh or not auth:
        raise PushNotificationError("Push subscription keys are incomplete.")

    normalized = {
        "endpoint": endpoint,
        "keys": {
            "p256dh": p256dh,
            "auth": auth,
        },
    }
    expiration = subscription.get("expirationTime")
    if expiration is not None:
        normalized["expirationTime"] = expiration
    return normalized


def notification_status(include_count: bool = True) -> Dict[str, Any]:
    configured = bool(_configured_public_key() and _configured_private_key())
    status = {
        "enabled": push_notifications_enabled() and configured,
        "configured": configured,
        "public_key_configured": bool(_configured_public_key()),
        "private_key_configured": bool(_configured_private_key()),
        "subject_configured": bool(_configured_subject()),
    }
    if include_count:
        try:
            status["subscription_count"] = len(list_push_subscriptions())
        except Exception:
            status["subscription_count"] = None
    return status


def save_push_subscription(
    subscription: Dict[str, Any],
    user_agent: str = "",
    db_path: str | None = None,
) -> Dict[str, Any]:
    normalized = _normalize_subscription(subscription)
    if db_path is None and dynamodb_store.is_dynamodb_enabled():
        return dynamodb_store.save_push_subscription(normalized, user_agent)

    endpoint_hash = _subscription_id(normalized["endpoint"])
    now = _now()
    payload_json = json.dumps(normalized, sort_keys=True)
    with _connect(db_path) as connection:
        existing = connection.execute(
            """
            SELECT created_at
            FROM push_subscriptions
            WHERE endpoint_hash = ?
            """,
            (endpoint_hash,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        connection.execute(
            """
            INSERT OR REPLACE INTO push_subscriptions (
                endpoint_hash, user_agent, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (endpoint_hash, user_agent, payload_json, created_at, now),
        )

    return {
        "id": endpoint_hash,
        "endpoint_hash": endpoint_hash,
        "user_agent": user_agent,
        "subscription": normalized,
        "updated_at": now,
    }


def list_push_subscriptions(db_path: str | None = None) -> List[Dict[str, Any]]:
    if db_path is None and dynamodb_store.is_dynamodb_enabled():
        return dynamodb_store.list_push_subscriptions()

    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT endpoint_hash, user_agent, payload_json, updated_at
            FROM push_subscriptions
            ORDER BY updated_at DESC
            """
        ).fetchall()

    subscriptions = []
    for row in rows:
        try:
            subscription = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            continue
        subscriptions.append(
            {
                "id": row["endpoint_hash"],
                "endpoint_hash": row["endpoint_hash"],
                "user_agent": row["user_agent"],
                "subscription": subscription,
                "updated_at": row["updated_at"],
            }
        )
    return subscriptions


def delete_push_subscription(endpoint: str, db_path: str | None = None) -> bool:
    if db_path is None and dynamodb_store.is_dynamodb_enabled():
        return dynamodb_store.delete_push_subscription(endpoint)

    endpoint_hash = _subscription_id(endpoint)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM push_subscriptions WHERE endpoint_hash = ?",
            (endpoint_hash,),
        )
    return cursor.rowcount > 0


def _send_web_push(subscription: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    if not notification_status(include_count=False)["enabled"]:
        return {"status": "skipped", "reason": "not_configured", "stale": False}

    try:
        from pywebpush import WebPushException, webpush
    except ModuleNotFoundError as exc:
        raise PushNotificationError(
            "pywebpush is not installed. Install requirements before sending push notifications."
        ) from exc

    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=_configured_private_key(),
            vapid_claims={"sub": _configured_subject()},
            ttl=3600,
        )
        return {"status": "sent", "stale": False}
    except WebPushException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return {
            "status": "failed",
            "status_code": status_code,
            "stale": status_code in (404, 410),
            "detail": str(exc),
        }


def send_notification_to_all(
    title: str,
    body: str,
    url: str = "/",
    tag: str = "personal-ai-assistant",
) -> Dict[str, Any]:
    status = notification_status(include_count=False)
    if not status["enabled"]:
        return {
            "status": "skipped",
            "reason": "not_configured",
            "subscription_count": 0,
            "sent": 0,
            "failed": 0,
            "stale_deleted": 0,
        }

    payload = {
        "title": title,
        "body": body,
        "url": url,
        "tag": tag,
    }
    subscriptions = list_push_subscriptions()
    sent = 0
    failed = 0
    stale_deleted = 0
    errors = []

    for stored in subscriptions:
        subscription = stored.get("subscription") or {}
        result = _send_web_push(subscription, payload)
        if result.get("status") == "sent":
            sent += 1
            continue

        failed += 1
        if result.get("stale"):
            endpoint = str(subscription.get("endpoint", ""))
            if endpoint and delete_push_subscription(endpoint):
                stale_deleted += 1
        errors.append(
            {
                "endpoint_hash": stored.get("endpoint_hash", ""),
                "status": result.get("status", "failed"),
                "status_code": result.get("status_code"),
            }
        )

    return {
        "status": "sent" if sent else "failed",
        "subscription_count": len(subscriptions),
        "sent": sent,
        "failed": failed,
        "stale_deleted": stale_deleted,
        "errors": errors[:5],
    }


def notify_morning_brief_ready(brief: Dict[str, Any], history_id: int | str) -> Dict[str, Any]:
    brief_date = str(brief.get("date", "")).strip()
    suffix = f" for {brief_date}" if brief_date else ""
    encoded_id = quote(str(history_id), safe="")
    return send_notification_to_all(
        title="Morning brief is ready",
        body=f"Your morning brief{suffix} is ready to read and play.",
        url=f"/?brief_id={encoded_id}",
        tag=f"morning-brief-{brief_date or history_id}",
    )
