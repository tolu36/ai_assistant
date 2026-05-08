from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_schedule_task_uses_mock_calendar(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "fallback")
    monkeypatch.setenv("CALENDAR_PROVIDER", "mock")

    response = client.post(
        "/schedule/task",
        json={"task": "Study for 2 hours tonight"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "scheduled"
    assert data["task"] == "Study for 2 hours tonight"
    assert data["duration_minutes"] == 120
    assert data["event"]["id"] == "mock-event"
    assert data["event"]["summary"] == "Study for 2 hours tonight"
    assert data["event"]["start"] == data["scheduled_start"]
    assert data["event"]["end"] == data["scheduled_end"]


def test_schedule_task_rejects_empty_task(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "mock")

    response = client.post("/schedule/task", json={"task": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Task text must not be empty."


def test_propose_schedule_returns_recurring_slots(monkeypatch):
    from app.routes import schedule

    monkeypatch.setattr(
        schedule,
        "propose_slots",
        lambda parsed: [
            {
                "start": __import__("datetime").datetime(2099, 1, 5, 18, 0),
                "end": __import__("datetime").datetime(2099, 1, 5, 20, 0),
            }
        ],
    )
    monkeypatch.setattr(
        schedule,
        "create_proposal",
        lambda task_text, parsed, slots: {
            "id": "proposal-1",
            "task_text": task_text,
            "parsed": parsed,
            "slots": [
                {
                    "start": slots[0]["start"].isoformat(),
                    "end": slots[0]["end"].isoformat(),
                }
            ],
            "status": "proposed",
        },
    )

    response = client.post(
        "/schedule/propose",
        json={"task": "Set up time to study for 2 hours 5 days a week"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "proposal"
    assert data["proposal_id"] == "proposal-1"
    assert data["duration_minutes"] == 120
    assert data["frequency_days_per_week"] == 5
    assert data["suggested_slots"][0]["start"] == "2099-01-05T18:00:00"


def test_confirm_schedule_proposal_creates_events(monkeypatch):
    from app.routes import schedule

    monkeypatch.setattr(
        schedule,
        "get_proposal",
        lambda proposal_id: {
            "id": proposal_id,
            "parsed": {"title": "Study", "description": "Study"},
            "slots": [
                {"start": "2099-01-05T18:00:00", "end": "2099-01-05T20:00:00"}
            ],
        },
    )
    monkeypatch.setattr(schedule, "mark_proposal_confirmed", lambda proposal_id: None)
    monkeypatch.setattr(
        schedule,
        "create_event",
        lambda title, start, end, description: {
            "id": "mock-event",
            "summary": title,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )

    response = client.post("/schedule/proposal/proposal-1/confirm", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["created_events"][0]["id"] == "mock-event"


def test_revise_schedule_proposal_returns_new_slots(monkeypatch):
    from app.routes import schedule

    monkeypatch.setattr(
        schedule,
        "get_proposal",
        lambda proposal_id: {
            "id": proposal_id,
            "parsed": {"title": "Study", "description": "Study", "duration_minutes": 120},
            "slots": [],
        },
    )
    monkeypatch.setattr(
        schedule,
        "remember_feedback_constraint",
        lambda feedback: {"reason": "avoid_sleep_hours", "start_hour": 22, "end_hour": 9},
    )
    monkeypatch.setattr(
        schedule,
        "propose_slots",
        lambda parsed: [
            {
                "start": __import__("datetime").datetime(2099, 1, 6, 18, 0),
                "end": __import__("datetime").datetime(2099, 1, 6, 20, 0),
            }
        ],
    )
    monkeypatch.setattr(
        schedule,
        "update_proposal_slots",
        lambda proposal_id, slots, feedback: {
            "slots": [
                {
                    "start": slots[0]["start"].isoformat(),
                    "end": slots[0]["end"].isoformat(),
                }
            ]
        },
    )

    response = client.post(
        "/schedule/proposal/proposal-1/revise",
        json={"feedback": "That is too late, I am sleeping then."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "revised"
    assert data["learned_constraint"]["reason"] == "avoid_sleep_hours"
    assert data["suggested_slots"][0]["start"] == "2099-01-06T18:00:00"


def test_mock_calendar_does_not_load_google_service(monkeypatch):
    from app.services import calendar

    monkeypatch.setenv("CALENDAR_PROVIDER", "mock")
    monkeypatch.setattr(
        calendar,
        "_get_service",
        lambda: (_ for _ in ()).throw(AssertionError("Google service should not load")),
    )

    response = client.post(
        "/schedule/task",
        json={"task": "Study for 2 hours tonight"},
    )

    assert response.status_code == 200
    assert response.json()["event"]["id"] == "mock-event"


def test_morning_brief_route_returns_sections(monkeypatch):
    from app.services import brief_generator

    monkeypatch.setenv("NEWS_SUMMARY_PROVIDER", "off")
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_headlines",
        lambda feed_urls, limit=6, per_feed_limit=2: [
            {
                "source": "Mock News",
                "title": "Mock RSS headline",
                "summary": "This is a short test summary.",
                "link": "https://example.com/mock",
            }
        ],
    )
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": ["NBA"],
            "sports_teams": [],
            "finance_watchlist": [],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls: [
            {
                "source": "ESPN NBA",
                "title": "Mock sports headline",
                "summary": "Sports sentence one. Sports sentence two. Sports sentence three.",
                "link": "https://example.com/sports",
            }
        ],
    )

    response = client.get("/brief/morning")

    assert response.status_code == 200
    data = response.json()
    assert "date" in data
    assert data["news"][0]["title"] == "Mock RSS headline"
    assert data["news"][0]["link"] == "https://example.com/mock"
    assert data["sports"][0]["title"] == "Mock sports headline"
    assert data["sports"][0]["summary"] == "Sports sentence one. Sports sentence two."
    assert len(data["finance"]) >= 2


def test_preferences_route_updates_preferences(monkeypatch, tmp_path):
    from app.services import preferences

    db_path = tmp_path / "preferences.db"
    monkeypatch.setattr(preferences, "PREFERENCES_DB_PATH", str(db_path))

    response = client.post(
        "/preferences",
        json={
            "sports_interests": ["NBA"],
            "sports_teams": ["Toronto Raptors"],
            "finance_watchlist": ["AAPL"],
        },
    )

    assert response.status_code == 200
    assert response.json()["sports_interests"] == ["NBA"]

    get_response = client.get("/preferences")
    assert get_response.status_code == 200
    assert get_response.json()["sports_teams"] == ["Toronto Raptors"]


def test_llm_status_route(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "fallback")

    response = client.get("/llm/status")

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "fallback"
    assert data["enabled"] is False
