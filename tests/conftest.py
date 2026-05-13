import pytest
import config


@pytest.fixture(autouse=True)
def local_test_defaults(monkeypatch):
    monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(config, "APP_ACCESS_TOKEN", "")
    monkeypatch.setenv("STORAGE_PROVIDER", "sqlite")
    monkeypatch.setenv("MODEL_PROVIDER", "fallback")
    monkeypatch.setenv("FINANCE_INTELLIGENCE_PROVIDER", "off")
    monkeypatch.setenv("DAILY_NOTE_PROVIDER", "off")
