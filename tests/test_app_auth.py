from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_private_api_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_TOKEN", "test-token")

    response = client.get("/status")

    assert response.status_code == 401
    assert response.json()["detail"] == "App access token is required."


def test_private_api_accepts_app_token_header(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_TOKEN", "test-token")

    response = client.get("/status", headers={"X-App-Token": "test-token"})

    assert response.status_code == 200


def test_public_shell_does_not_require_token(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_TOKEN", "test-token")

    response = client.get("/")

    assert response.status_code == 200
