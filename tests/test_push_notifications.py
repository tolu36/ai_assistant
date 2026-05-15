from app.services import push_notifications


def _subscription(endpoint: str = "https://push.example/subscription"):
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": "test-p256dh",
            "auth": "test-auth",
        },
    }


def test_local_push_subscription_round_trip(tmp_path, monkeypatch):
    db_path = tmp_path / "notifications.db"
    monkeypatch.setenv("NOTIFICATION_DB_PATH", str(db_path))

    saved = push_notifications.save_push_subscription(
        _subscription(),
        user_agent="pytest",
    )
    subscriptions = push_notifications.list_push_subscriptions()
    deleted = push_notifications.delete_push_subscription(_subscription()["endpoint"])

    assert saved["endpoint_hash"]
    assert len(subscriptions) == 1
    assert subscriptions[0]["subscription"]["endpoint"] == _subscription()["endpoint"]
    assert deleted is True
    assert push_notifications.list_push_subscriptions() == []


def test_notification_status_requires_vapid_keys(monkeypatch):
    monkeypatch.delenv("PUSH_VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("PUSH_VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.setattr(push_notifications, "PUSH_VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(push_notifications, "PUSH_VAPID_PRIVATE_KEY", "")

    status = push_notifications.notification_status(include_count=False)

    assert status["enabled"] is False
    assert status["configured"] is False


def test_send_notification_to_all_uses_saved_subscriptions(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_DB_PATH", str(tmp_path / "notifications.db"))
    monkeypatch.setenv("PUSH_VAPID_PUBLIC_KEY", "public-key")
    monkeypatch.setenv("PUSH_VAPID_PRIVATE_KEY", "private-key")
    push_notifications.save_push_subscription(_subscription())

    sent_payloads = []
    monkeypatch.setattr(
        push_notifications,
        "_send_web_push",
        lambda subscription, payload: sent_payloads.append((subscription, payload))
        or {"status": "sent", "stale": False},
    )

    result = push_notifications.send_notification_to_all(
        "Morning brief is ready",
        "Your morning brief is ready.",
        "/?brief_id=1",
    )

    assert result["sent"] == 1
    assert result["failed"] == 0
    assert sent_payloads[0][1]["url"] == "/?brief_id=1"


def test_send_notification_deletes_stale_subscriptions(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_DB_PATH", str(tmp_path / "notifications.db"))
    monkeypatch.setenv("PUSH_VAPID_PUBLIC_KEY", "public-key")
    monkeypatch.setenv("PUSH_VAPID_PRIVATE_KEY", "private-key")
    push_notifications.save_push_subscription(_subscription())

    monkeypatch.setattr(
        push_notifications,
        "_send_web_push",
        lambda subscription, payload: {
            "status": "failed",
            "status_code": 410,
            "stale": True,
        },
    )

    result = push_notifications.send_notification_to_all(
        "Morning brief is ready",
        "Your morning brief is ready.",
    )

    assert result["sent"] == 0
    assert result["failed"] == 1
    assert result["stale_deleted"] == 1
    assert push_notifications.list_push_subscriptions() == []
