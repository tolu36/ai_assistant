from datetime import datetime

from app.services import brief_history, dynamodb_store, preferences


class FakeTable:
    def __init__(self):
        self.items = {}

    def get_item(self, Key):
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.items[(Item["pk"], Item["sk"])] = Item
        return {}


def test_preferences_use_dynamodb_when_enabled(monkeypatch):
    table = FakeTable()
    monkeypatch.setenv("STORAGE_PROVIDER", "dynamodb")
    monkeypatch.setenv("DYNAMODB_USER_ID", "test-user")
    monkeypatch.setattr(dynamodb_store, "_table", lambda: table)

    saved = preferences.save_preferences(
        {
            "sports_interests": ["NBA"],
            "sports_teams": ["OKC Thunder"],
            "finance_topics": ["Bank of Canada"],
            "finance_watchlist": ["AAPL"],
        }
    )
    loaded = preferences.load_preferences()

    assert saved["sports_teams"] == ["OKC Thunder"]
    assert loaded == saved
    assert ("USER#test-user", "PREFERENCES") in table.items


def test_brief_history_uses_dynamodb_when_enabled(monkeypatch):
    table = FakeTable()
    monkeypatch.setenv("STORAGE_PROVIDER", "dynamodb")
    monkeypatch.setattr(dynamodb_store, "_table", lambda: table)
    brief = {
        "date": "2026-05-08",
        "news": [],
        "sports": [],
        "finance": [],
    }

    saved = brief_history.save_morning_brief(brief)
    loaded = brief_history.get_morning_brief(saved["id"])

    assert saved["brief"] == brief
    assert loaded["id"] == saved["id"]
    assert loaded["brief"] == brief


def test_dynamodb_proposal_restores_parsed_datetimes(monkeypatch):
    table = FakeTable()
    monkeypatch.setenv("STORAGE_PROVIDER", "dynamodb")
    monkeypatch.setattr(dynamodb_store, "_table", lambda: table)

    slot = {"start": datetime(2099, 1, 5, 18, 0), "end": datetime(2099, 1, 5, 20, 0)}
    created = dynamodb_store.create_proposal(
        "Study for 2 hours",
        {
            "title": "Study",
            "duration_minutes": 120,
            "start_datetime": slot["start"],
            "end_datetime": slot["end"],
        },
        [slot],
    )
    loaded = dynamodb_store.get_proposal(created["id"])

    assert loaded["parsed"]["start_datetime"] == slot["start"]
    assert loaded["parsed"]["end_datetime"] == slot["end"]
