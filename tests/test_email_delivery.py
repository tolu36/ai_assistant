from app.services import email_delivery
from config import _load_dotenv


def _brief():
    return {
        "date": "2026-05-07",
        "daily_quote": [
            {
                "source": "Daily Note",
                "category": "Mindset",
                "title": "Daily Quote",
                "summary": "Small steady actions compound into meaningful progress.",
                "reflection": "Name one thing you are grateful for today.",
            }
        ],
        "news": [
            {
                "source": "Mock News",
                "title": "Headline",
                "summary": "Useful summary.",
                "link": "https://example.com/news",
            }
        ],
        "sports": ["Sports: no update"],
        "finance": [
            {
                "source": "Mock Finance",
                "category": "Finance",
                "title": "AAPL earnings",
                "summary": "Apple reported earnings.",
                "link": "https://example.com/aapl",
                "matched_ticker": "AAPL",
                "why_it_matters": "ETF context.",
                "watch_for": "earnings guidance",
            }
        ],
    }


def test_render_morning_brief_text_includes_sections_and_links():
    text = email_delivery.render_morning_brief_text(_brief())

    assert "Morning brief for 2026-05-07" in text
    assert "Daily Note" in text
    assert "Daily Note - Daily Quote" in text
    assert "Reflection: Name one thing you are grateful for today." in text
    assert "News" in text
    assert "Mock News - Headline" in text
    assert "Read more: https://example.com/news" in text
    assert "Tags: Finance, AAPL" in text
    assert "Why it matters: ETF context." in text
    assert "Watch for: earnings guidance" in text


def test_build_morning_brief_message_uses_email_settings(monkeypatch):
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("MORNING_BRIEF_FROM_EMAIL", "sender@example.com")
    monkeypatch.setenv("MORNING_BRIEF_TO_EMAIL", "reader@example.com")
    monkeypatch.setenv("MORNING_BRIEF_SUBJECT_PREFIX", "Assistant")

    message = email_delivery.build_morning_brief_message(_brief())

    assert message["From"] == "sender@example.com"
    assert message["To"] == "reader@example.com"
    assert message["Subject"] == "Assistant: Morning Brief 2026-05-07"


def test_build_morning_brief_message_has_clear_sender_error(monkeypatch):
    monkeypatch.setattr(email_delivery, "SMTP_USERNAME", "")
    monkeypatch.setattr(email_delivery, "MORNING_BRIEF_FROM_EMAIL", "")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("MORNING_BRIEF_FROM_EMAIL", raising=False)
    monkeypatch.setenv("MORNING_BRIEF_TO_EMAIL", "reader@example.com")

    try:
        email_delivery.build_morning_brief_message(_brief())
    except email_delivery.EmailConfigurationError as exc:
        assert "Set MORNING_BRIEF_FROM_EMAIL or SMTP_USERNAME" in str(exc)
    else:
        raise AssertionError("Expected EmailConfigurationError")


def test_send_message_uses_smtp(monkeypatch):
    sent = {}

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, message):
            sent["subject"] = message["Subject"]

    monkeypatch.setattr(email_delivery.smtplib, "SMTP", FakeSmtp)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("MORNING_BRIEF_TO_EMAIL", "reader@example.com")

    message = email_delivery.build_morning_brief_message(_brief())
    result = email_delivery.send_message(message)

    assert result["status"] == "sent"
    assert sent["host"] == "smtp.example.com"
    assert sent["port"] == 587
    assert sent["tls"] is True
    assert sent["login"] == ("sender@example.com", "secret")
    assert sent["subject"] == "Personal AI Assistant: Morning Brief 2026-05-07"


def test_validate_email_settings_reports_configured_values(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("MORNING_BRIEF_FROM_EMAIL", "sender@example.com")
    monkeypatch.setenv("MORNING_BRIEF_TO_EMAIL", "reader@example.com")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setenv("SMTP_USE_SSL", "false")

    result = email_delivery.validate_email_settings()

    assert result == {
        "status": "configured",
        "host": "smtp.example.com",
        "port": 587,
        "from": "sender@example.com",
        "to": "reader@example.com",
        "use_tls": True,
        "use_ssl": False,
    }


def test_validate_email_settings_requires_password(monkeypatch):
    monkeypatch.setattr(email_delivery, "SMTP_PASSWORD", "")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("MORNING_BRIEF_FROM_EMAIL", "sender@example.com")
    monkeypatch.setenv("MORNING_BRIEF_TO_EMAIL", "reader@example.com")

    try:
        email_delivery.validate_email_settings()
    except email_delivery.EmailConfigurationError as exc:
        assert "SMTP_PASSWORD" in str(exc)
    else:
        raise AssertionError("Expected EmailConfigurationError")


def test_send_message_reports_gmail_app_password_error(monkeypatch):
    class FakeSmtp:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            raise email_delivery.SMTPAuthenticationError(
                534,
                b"Application-specific password required.",
            )

    monkeypatch.setattr(email_delivery.smtplib, "SMTP", FakeSmtp)
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "normal-password")
    monkeypatch.setenv("MORNING_BRIEF_TO_EMAIL", "reader@example.com")

    message = email_delivery.build_morning_brief_message(_brief())

    try:
        email_delivery.send_message(message)
    except email_delivery.EmailConfigurationError as exc:
        assert "Google App Password" in str(exc)
    else:
        raise AssertionError("Expected EmailConfigurationError")


def test_load_dotenv_does_not_override_existing_env(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DOTENV_TEST_FROM_FILE=from-file\nDOTENV_TEST_EXISTING=file\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DOTENV_TEST_FROM_FILE", raising=False)
    monkeypatch.setenv("DOTENV_TEST_EXISTING", "existing")

    _load_dotenv(str(env_file))

    assert email_delivery.os.getenv("DOTENV_TEST_FROM_FILE") == "from-file"
    assert email_delivery.os.getenv("DOTENV_TEST_EXISTING") == "existing"
