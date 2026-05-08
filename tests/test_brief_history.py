from app.services.brief_history import (
    get_morning_brief,
    list_morning_briefs,
    save_morning_brief,
)


def test_save_list_and_get_morning_brief(tmp_path):
    db_path = tmp_path / "brief_history.db"
    brief = {
        "date": "2026-05-07",
        "news": [{"title": "Headline", "summary": "Summary.", "link": ""}],
        "sports": [],
        "finance": [],
    }

    saved = save_morning_brief(brief, db_path=str(db_path))
    summaries = list_morning_briefs(db_path=str(db_path))
    loaded = get_morning_brief(saved["id"], db_path=str(db_path))

    assert saved["id"] == 1
    assert summaries == [
        {
            "id": 1,
            "brief_date": "2026-05-07",
            "created_at": saved["created_at"],
        }
    ]
    assert loaded["brief"] == brief


def test_get_morning_brief_returns_none_for_missing_id(tmp_path):
    db_path = tmp_path / "brief_history.db"

    assert get_morning_brief(999, db_path=str(db_path)) is None
