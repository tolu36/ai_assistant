import pytest


@pytest.fixture(autouse=True)
def local_test_defaults(monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "sqlite")
    monkeypatch.setenv("APP_ACCESS_TOKEN", "")
