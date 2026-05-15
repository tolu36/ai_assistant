from fastapi.testclient import TestClient

from app.services import push_notifications
from app.main import app


client = TestClient(app)


def test_notification_status_route_reports_unconfigured(monkeypatch):
    monkeypatch.setattr(push_notifications, "PUSH_VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(push_notifications, "PUSH_VAPID_PRIVATE_KEY", "")

    response = client.get("/notifications/status")

    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_notification_subscribe_route_saves_subscription(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_DB_PATH", str(tmp_path / "notifications.db"))
    payload = {
        "endpoint": "https://push.example/subscription",
        "keys": {
            "p256dh": "test-p256dh",
            "auth": "test-auth",
        },
    }

    response = client.post("/notifications/subscribe", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "subscribed"


def test_notification_public_key_route_requires_configuration(monkeypatch):
    monkeypatch.setattr(push_notifications, "PUSH_VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(push_notifications, "PUSH_VAPID_PRIVATE_KEY", "")

    response = client.get("/notifications/vapid-public-key")

    assert response.status_code == 503


def test_notification_public_key_route_returns_configured_key(monkeypatch):
    monkeypatch.setenv("PUSH_VAPID_PUBLIC_KEY", "public-key")
    monkeypatch.setenv("PUSH_VAPID_PRIVATE_KEY", "private-key")

    response = client.get("/notifications/vapid-public-key")

    assert response.status_code == 200
    assert response.json()["public_key"] == "public-key"
