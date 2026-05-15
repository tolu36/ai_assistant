from app import aws_lambda


def test_send_morning_brief_skips_email_when_disabled(monkeypatch):
    saved = {
        "id": "brief-1",
        "brief": {
            "date": "2026-05-14",
            "news": [],
            "sports": [],
            "finance": [],
        },
    }
    notified = []

    monkeypatch.setattr(aws_lambda, "MORNING_BRIEF_EMAIL_ENABLED", False)
    monkeypatch.setattr(aws_lambda, "_latest_prepared_morning_brief", lambda: saved)
    monkeypatch.setattr(
        aws_lambda,
        "ensure_brief_audio",
        lambda brief, brief_id: {"available": True, "status": "ready"},
    )
    monkeypatch.setattr(
        aws_lambda,
        "send_morning_brief_email",
        lambda brief: (_ for _ in ()).throw(AssertionError("email should be disabled")),
    )
    monkeypatch.setattr(
        aws_lambda,
        "notify_morning_brief_ready",
        lambda brief, brief_id: notified.append((brief, brief_id))
        or {"status": "sent", "sent": 1},
    )

    result = aws_lambda._send_morning_brief()

    assert result["email"] == {"status": "disabled"}
    assert result["audio_status"] == {"available": True, "status": "ready"}
    assert notified[0][1] == "brief-1"


def test_send_morning_brief_still_allows_email_when_enabled(monkeypatch):
    saved = {
        "id": "brief-1",
        "brief": {
            "date": "2026-05-14",
            "news": [],
            "sports": [],
            "finance": [],
        },
    }

    monkeypatch.setattr(aws_lambda, "MORNING_BRIEF_EMAIL_ENABLED", True)
    monkeypatch.setattr(aws_lambda, "_latest_prepared_morning_brief", lambda: saved)
    monkeypatch.setattr(
        aws_lambda,
        "ensure_brief_audio",
        lambda brief, brief_id: {"available": True, "status": "ready"},
    )
    monkeypatch.setattr(
        aws_lambda,
        "send_morning_brief_email",
        lambda brief: {"status": "sent"},
    )
    monkeypatch.setattr(
        aws_lambda,
        "notify_morning_brief_ready",
        lambda brief, brief_id: {"status": "sent", "sent": 1},
    )

    result = aws_lambda._send_morning_brief()

    assert result["email"] == {"status": "sent"}
    assert result["notification"] == {"status": "sent", "sent": 1}


def test_send_morning_brief_requires_ready_audio_before_notification(monkeypatch):
    saved = {
        "id": "brief-1",
        "brief": {
            "date": "2026-05-14",
            "news": [],
            "sports": [],
            "finance": [],
        },
    }

    monkeypatch.setattr(aws_lambda, "MORNING_BRIEF_EMAIL_ENABLED", False)
    monkeypatch.setattr(aws_lambda, "_latest_prepared_morning_brief", lambda: saved)
    monkeypatch.setattr(
        aws_lambda,
        "ensure_brief_audio",
        lambda brief, brief_id: {"available": False, "status": "error"},
    )
    monkeypatch.setattr(
        aws_lambda,
        "notify_morning_brief_ready",
        lambda brief, brief_id: (_ for _ in ()).throw(
            AssertionError("notification should wait for audio")
        ),
    )

    try:
        aws_lambda._send_morning_brief()
    except RuntimeError as exc:
        assert "Morning brief audio is not ready" in str(exc)
    else:
        raise AssertionError("Expected missing audio to fail the scheduled send.")
