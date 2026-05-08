from datetime import datetime

from app.services.schedule_store import (
    add_constraint,
    create_proposal,
    get_proposal,
    list_constraints,
    proposal_slots_as_datetimes,
)


def test_create_and_load_proposal(tmp_path):
    db_path = tmp_path / "scheduler.db"
    slot = {"start": datetime(2099, 1, 5, 18, 0), "end": datetime(2099, 1, 5, 20, 0)}

    created = create_proposal(
        "Study for 2 hours",
        {"title": "Study", "duration_minutes": 120},
        [slot],
        db_path=str(db_path),
    )
    loaded = get_proposal(created["id"], db_path=str(db_path))

    assert loaded["id"] == created["id"]
    assert loaded["status"] == "proposed"
    assert proposal_slots_as_datetimes(loaded)[0] == slot


def test_add_and_list_constraints(tmp_path):
    db_path = tmp_path / "scheduler.db"

    add_constraint(
        reason="avoid_sleep_hours",
        start_hour=22,
        end_hour=9,
        raw_feedback="I am sleeping then",
        db_path=str(db_path),
    )

    constraints = list_constraints(db_path=str(db_path))
    assert constraints[0]["reason"] == "avoid_sleep_hours"
    assert constraints[0]["start_hour"] == 22
    assert constraints[0]["end_hour"] == 9
