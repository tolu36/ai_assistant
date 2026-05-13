import base64

from fastapi.testclient import TestClient

from app.main import app
from app.services import tts


client = TestClient(app)


def test_tts_status_reports_mistral_configuration(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("MISTRAL_TTS_MODEL", "voxtral-mini-tts-2603")

    status = tts.tts_status()

    assert status["provider"] == "mistral"
    assert status["enabled"] is True
    assert status["model"] == "voxtral-mini-tts-2603"
    assert status["voice_configured"] is True
    assert status["response_format"] == "mp3"


def test_generate_mistral_speech_decodes_audio(monkeypatch):
    audio = b"fake-mp3"
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"audio_data": base64.b64encode(audio).decode("ascii")}

    class FakeClient:
        def __init__(self, timeout, trust_env):
            captured["timeout"] = timeout
            captured["trust_env"] = trust_env

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(tts.httpx, "Client", FakeClient)

    result = tts.generate_mistral_speech("Hello from the assistant.")

    assert result["audio"] == audio
    assert result["media_type"] == "audio/mpeg"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "voxtral-mini-tts-2603"
    assert captured["json"]["input"] == "Hello from the assistant."
    assert captured["json"]["response_format"] == "mp3"
    assert captured["json"]["voice_id"] == "gb_oliver_confident"
    assert captured["trust_env"] is False


def test_tts_route_returns_audio(monkeypatch):
    monkeypatch.setattr(
        "app.routes.tts.generate_mistral_speech",
        lambda text: {
            "audio": b"audio-bytes",
            "media_type": "audio/mpeg",
            "response_format": "mp3",
        },
    )

    response = client.post("/tts/speech", json={"text": "Read this."})

    assert response.status_code == 200
    assert response.content == b"audio-bytes"
    assert response.headers["content-type"] == "audio/mpeg"
