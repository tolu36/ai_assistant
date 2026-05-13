import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services import brief_audio


def _sample_brief():
    return {
        "date": "2026-05-12",
        "daily_quote": [
            {
                "summary": "Protect your attention.",
                "reflection": "Name one thing you are grateful for today.",
            }
        ],
        "news": [
            {
                "title": "Market opens higher",
                "summary": "Investors are watching inflation data.",
            }
        ],
        "sports": ["Sports: No team-specific headlines found right now."],
        "finance": [
            {
                "title": "Bond yields move",
                "summary": "Rate-sensitive ETFs are in focus.",
                "section": "market_watch",
            }
        ],
    }


def test_generate_brief_audio_writes_section_manifest(monkeypatch):
    audio_root = Path("data") / "test_brief_audio" / uuid.uuid4().hex
    calls = []

    def fake_generate_speech(text):
        calls.append(text)
        return {
            "audio": f"audio-{len(calls)}".encode("ascii"),
            "media_type": "audio/mpeg",
            "response_format": "mp3",
        }

    monkeypatch.setenv("BRIEF_AUDIO_DIR", str(audio_root))
    monkeypatch.setenv("BRIEF_AUDIO_OBJECT_BUCKET", "")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(brief_audio, "generate_mistral_speech", fake_generate_speech)

    try:
        manifest = brief_audio.generate_brief_audio(_sample_brief(), "brief/1")

        assert manifest["brief_id"] == "brief/1"
        assert set(manifest["tracks"]) == {"daily_quote", "news", "sports", "finance"}
        assert manifest["tracks"]["news"]["chunks"][0]["filename"] == "news-001.mp3"
        assert len(calls) == 4

        chunk = brief_audio.get_brief_audio_chunk("brief/1", "news", 1)
        assert chunk is not None
        assert chunk["path"].read_bytes() == b"audio-2"
        assert chunk["metadata"]["media_type"] == "audio/mpeg"
    finally:
        shutil.rmtree(audio_root, ignore_errors=True)


def test_ensure_brief_audio_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("MORNING_BRIEF_PREGENERATE_AUDIO", "false")
    monkeypatch.setenv("BRIEF_AUDIO_OBJECT_BUCKET", "")

    result = brief_audio.ensure_brief_audio(_sample_brief(), "brief-1")

    assert result == {"available": False, "status": "disabled"}


def test_cleanup_expired_brief_audio_removes_old_directories(monkeypatch):
    audio_root = Path("data") / "test_brief_audio" / uuid.uuid4().hex
    old_dir = audio_root / "old"
    new_dir = audio_root / "new"
    old_dir.mkdir(parents=True)
    new_dir.mkdir(parents=True)

    old_manifest = {
        "created_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
        "tracks": {},
    }
    new_manifest = {
        "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "tracks": {},
    }
    (old_dir / "manifest.json").write_text(json.dumps(old_manifest), encoding="utf-8")
    (new_dir / "manifest.json").write_text(json.dumps(new_manifest), encoding="utf-8")

    monkeypatch.setenv("BRIEF_AUDIO_DIR", str(audio_root))
    monkeypatch.setenv("BRIEF_AUDIO_OBJECT_BUCKET", "")

    try:
        result = brief_audio.cleanup_expired_brief_audio(retention_days=7)

        assert result == {"deleted": 1, "kept": 1}
        assert not old_dir.exists()
        assert new_dir.exists()
    finally:
        shutil.rmtree(audio_root, ignore_errors=True)


def test_generate_brief_audio_can_use_object_storage(monkeypatch):
    objects = {}

    class FakeBody:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body

    class FakeObjectClient:
        def put_object(self, Bucket, Key, Body, ContentType):
            objects[(Bucket, Key)] = {
                "body": Body,
                "content_type": ContentType,
            }

        def get_object(self, Bucket, Key):
            item = objects[(Bucket, Key)]
            return {"Body": FakeBody(item["body"])}

    monkeypatch.setenv("BRIEF_AUDIO_OBJECT_BUCKET", "audio-bucket")
    monkeypatch.setenv("BRIEF_AUDIO_OBJECT_PREFIX", "brief-audio")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(brief_audio, "_object_client", lambda: FakeObjectClient())
    monkeypatch.setattr(
        brief_audio,
        "generate_mistral_speech",
        lambda text: {
            "audio": b"object-audio",
            "media_type": "audio/mpeg",
            "response_format": "mp3",
        },
    )

    manifest = brief_audio.generate_brief_audio(_sample_brief(), "brief-1")
    loaded = brief_audio.load_brief_audio_manifest("brief-1")
    chunk = brief_audio.get_brief_audio_chunk("brief-1", "news", 1)

    assert manifest["brief_id"] == "brief-1"
    assert loaded["brief_id"] == "brief-1"
    assert chunk["audio"] == b"object-audio"
    assert ("audio-bucket", "brief-audio/brief-1/manifest.json") in objects


def test_cleanup_expired_brief_audio_removes_old_object_storage_items(monkeypatch):
    deleted = []
    now = datetime.now(timezone.utc)
    objects = [
        {
            "Key": "brief-audio/old/news-001.mp3",
            "LastModified": now - timedelta(days=8),
        },
        {
            "Key": "brief-audio/new/news-001.mp3",
            "LastModified": now - timedelta(days=2),
        },
    ]

    class FakeObjectClient:
        def list_objects_v2(self, **kwargs):
            assert kwargs["Bucket"] == "audio-bucket"
            assert kwargs["Prefix"] == "brief-audio/"
            return {"Contents": objects, "IsTruncated": False}

        def delete_object(self, Bucket, Key):
            deleted.append((Bucket, Key))

    monkeypatch.setenv("BRIEF_AUDIO_OBJECT_BUCKET", "audio-bucket")
    monkeypatch.setenv("BRIEF_AUDIO_OBJECT_PREFIX", "brief-audio")
    monkeypatch.setattr(brief_audio, "_object_client", lambda: FakeObjectClient())

    result = brief_audio.cleanup_expired_brief_audio(retention_days=7)

    assert result == {"deleted": 1, "kept": 1}
    assert deleted == [("audio-bucket", "brief-audio/old/news-001.mp3")]
