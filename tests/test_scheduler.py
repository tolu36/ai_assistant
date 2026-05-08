from datetime import datetime, timedelta

from app.services import scheduler
from app.services.scheduler import find_best_slot, propose_slots


def test_find_best_slot_uses_requested_time_when_free(monkeypatch):
    requested = datetime(2099, 1, 5, 18, 0)
    monkeypatch.setattr(scheduler, "list_busy_slots", lambda start, end: [])

    slot = find_best_slot({"start_datetime": requested, "duration_minutes": 60})

    assert slot["start"] == requested
    assert slot["end"] == requested + timedelta(minutes=60)


def test_find_best_slot_moves_after_conflict(monkeypatch):
    requested = datetime(2099, 1, 5, 18, 0)
    busy_start = datetime(2099, 1, 5, 18, 0)
    busy_end = datetime(2099, 1, 5, 19, 0)
    monkeypatch.setattr(
        scheduler,
        "list_busy_slots",
        lambda start, end: [{"start": busy_start, "end": busy_end}],
    )

    slot = find_best_slot({"start_datetime": requested, "duration_minutes": 60})

    assert slot["start"] == busy_end
    assert slot["end"] == busy_end + timedelta(minutes=60)


def test_find_best_slot_moves_late_task_to_next_default(monkeypatch):
    requested = datetime(2099, 1, 5, 21, 30)
    monkeypatch.setattr(scheduler, "list_busy_slots", lambda start, end: [])

    slot = find_best_slot({"start_datetime": requested, "duration_minutes": 60})

    assert slot["start"] == datetime(2099, 1, 6, 18, 0)
    assert slot["end"] == datetime(2099, 1, 6, 19, 0)


def test_propose_slots_returns_requested_frequency(monkeypatch):
    requested = datetime(2099, 1, 5, 18, 0)
    monkeypatch.setattr(scheduler, "list_busy_slots", lambda start, end: [])

    slots = propose_slots(
        {
            "start_datetime": requested,
            "duration_minutes": 120,
            "frequency_days_per_week": 5,
        }
    )

    assert len(slots) == 5
    assert slots[0]["start"] == requested
    assert all(slot["end"] - slot["start"] == timedelta(minutes=120) for slot in slots)


def test_propose_slots_avoids_conflicts(monkeypatch):
    requested = datetime(2099, 1, 5, 18, 0)
    busy_start = datetime(2099, 1, 5, 18, 0)
    busy_end = datetime(2099, 1, 5, 20, 0)
    monkeypatch.setattr(
        scheduler,
        "list_busy_slots",
        lambda start, end: [{"start": busy_start, "end": busy_end}],
    )

    slots = propose_slots(
        {
            "start_datetime": requested,
            "duration_minutes": 120,
            "frequency_days_per_week": 2,
        }
    )

    assert slots[0]["start"] == busy_end
    assert len(slots) == 2


def test_propose_slots_avoids_learned_constraints(monkeypatch):
    requested = datetime(2099, 1, 5, 8, 0)
    monkeypatch.setattr(scheduler, "list_busy_slots", lambda start, end: [])
    monkeypatch.setattr(
        scheduler.schedule_store,
        "list_constraints",
        lambda: [
            {
                "reason": "avoid_early_morning",
                "start_hour": 0,
                "end_hour": 9,
            }
        ],
    )

    slots = propose_slots(
        {
            "start_datetime": requested,
            "duration_minutes": 60,
            "frequency_days_per_week": 1,
        }
    )

    assert slots[0]["start"].hour >= 9
