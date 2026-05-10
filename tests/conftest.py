import pytest


@pytest.fixture(autouse=True)
def local_test_defaults(monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "sqlite")
    monkeypatch.setenv("APP_ACCESS_TOKEN", "")
    monkeypatch.setenv("MODEL_PROVIDER", "fallback")
    monkeypatch.setenv("FINANCE_INTELLIGENCE_PROVIDER", "off")
    monkeypatch.setenv("DAILY_NOTE_PROVIDER", "off")
