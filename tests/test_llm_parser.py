from app.services import llm_parser
from app.services.llm_parser import get_llm_status, parse_task


def test_parse_task_fallback():
    result = parse_task("Study for 2 hours tonight")

    assert result["title"] == "Study for 2 hours tonight"
    assert result["description"] == "Study for 2 hours tonight"
    assert result["duration_minutes"] == 120
    assert result["start_datetime"] is not None
    assert result["end_datetime"] is not None
    assert result["end_datetime"] > result["start_datetime"]
    assert result["ambiguity_flags"] == []
    assert result["parser_provider"] == "fallback"


def test_parse_tomorrow_morning_duration():
    result = parse_task("Workout tomorrow morning for 45 minutes")

    assert result["duration_minutes"] == 45
    assert result["start_datetime"].hour == 9
    assert result["start_datetime"].minute == 0
    assert result["end_datetime"] > result["start_datetime"]
    assert result["ambiguity_flags"] == []


def test_parse_half_hour_after_work():
    result = parse_task("Read for half an hour after work")

    assert result["duration_minutes"] == 30
    assert result["start_datetime"].hour == 17
    assert result["start_datetime"].minute == 30
    assert result["ambiguity_flags"] == []


def test_parse_missing_duration_marks_ambiguity():
    result = parse_task("Call mom Friday at 6pm")

    assert result["duration_minutes"] == 60
    assert "missing_duration" in result["ambiguity_flags"]
    assert result["start_datetime"] is not None
    assert result["end_datetime"] > result["start_datetime"]


def test_parse_empty_task_rejected():
    try:
        parse_task("   ")
    except ValueError as exc:
        assert str(exc) == "Task text is required"
    else:
        raise AssertionError("Expected empty task to raise ValueError")


def test_parse_weekly_frequency():
    result = parse_task("Set up time to study for 2 hours 5 days a week")

    assert result["duration_minutes"] == 120
    assert result["frequency_days_per_week"] == 5


def test_llm_status_reports_fallback_by_default(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "fallback")

    status = get_llm_status()

    assert status["provider"] == "fallback"
    assert status["enabled"] is False
    assert status["loaded"] is False


def test_parser_falls_back_when_model_unavailable(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "transformers")
    monkeypatch.setattr(llm_parser, "_load_model", lambda: None)

    result = parse_task("Study for 2 hours tonight")

    assert result["duration_minutes"] == 120
    assert result["parser_provider"] == "fallback"


def test_llm_status_reports_mistral(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "mistral")
    monkeypatch.setenv("MODEL_FALLBACK_PROVIDER", "transformers")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-small-latest")

    status = get_llm_status()

    assert status["provider"] == "mistral"
    assert status["enabled"] is True
    assert status["model_name"] == "mistral-small-latest"
    assert status["device"] == "api"
    assert status["provider_chain"] == ["mistral", "transformers", "deterministic"]


def test_mistral_text_generation(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "Mistral response"}}]}

    class FakeClient:
        def __init__(self, timeout, trust_env):
            assert timeout == 30
            assert trust_env is False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers, json):
            assert headers["Authorization"] == "Bearer test-key"
            assert json["model"] == "mistral-small-latest"
            return FakeResponse()

    import httpx

    monkeypatch.setenv("MODEL_PROVIDER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-small-latest")
    monkeypatch.setattr(httpx, "Client", FakeClient)

    assert llm_parser.generate_llm_text("hello") == "Mistral response"


def test_llm_text_generation_falls_back_to_transformers(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "mistral")
    monkeypatch.setenv("MODEL_FALLBACK_PROVIDER", "transformers")

    def fake_generate_text(prompt, provider=None):
        if provider == "mistral":
            raise RuntimeError("rate limited")
        if provider == "transformers":
            return "Qwen response"
        raise AssertionError(f"unexpected provider {provider}")

    monkeypatch.setattr(llm_parser, "_generate_text", fake_generate_text)

    assert llm_parser.generate_llm_text("hello") == "Qwen response"


def test_parse_task_falls_back_from_mistral_to_transformers(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "mistral")
    monkeypatch.setenv("MODEL_FALLBACK_PROVIDER", "transformers")

    def fake_generate_text(prompt, provider=None):
        if provider == "mistral":
            raise RuntimeError("rate limited")
        return """
        {"title":"Study","description":"Study","start_datetime":null,"end_datetime":null,"duration_minutes":120,"frequency_days_per_week":5}
        """

    monkeypatch.setattr(llm_parser, "_generate_text", fake_generate_text)

    result = parse_task("Set up time to study for 2 hours 5 days a week")

    assert result["duration_minutes"] == 120
    assert result["frequency_days_per_week"] == 5
    assert result["parser_provider"] == "transformers"


def test_llm_parse_keeps_explicit_duration_and_missing_start(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "transformers")
    monkeypatch.setattr(
        llm_parser,
        "_generate_text",
        lambda prompt, provider=None: """
        {"title":"Study","description":"Study","start_datetime":"2026-05-07T19:49:00","end_datetime":"2026-05-07T22:14:00","duration_minutes":145,"frequency_days_per_week":5}
        """,
    )

    result = parse_task("Set up time to study for 2 hours 5 days a week")

    assert result["duration_minutes"] == 120
    assert result["frequency_days_per_week"] == 5
    assert "missing_start" in result["ambiguity_flags"]
    assert result["parser_provider"] == "transformers"
