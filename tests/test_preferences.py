from app.services.preferences import load_preferences, save_preferences


def test_save_and_load_preferences(tmp_path):
    db_path = tmp_path / "preferences.db"

    saved = save_preferences(
        {
            "sports_interests": ["NBA", "Tennis"],
            "sports_teams": ["Toronto Raptors"],
            "finance_topics": ["Interest rates", "Inflation"],
            "finance_watchlist": ["AAPL", "SPY"],
        },
        db_path=str(db_path),
    )

    assert saved == {
        "sports_interests": ["NBA", "Tennis"],
        "sports_teams": ["Toronto Raptors"],
        "finance_topics": ["Interest rates", "Inflation"],
        "finance_watchlist": ["AAPL", "SPY"],
    }
    assert load_preferences(db_path=str(db_path)) == saved
