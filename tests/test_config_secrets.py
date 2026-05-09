import pytest

import config


def test_get_secret_value_prefers_environment(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_TOKEN", "env-token")
    monkeypatch.setattr(config, "SECRETS_PROVIDER", "ssm")
    monkeypatch.setattr(
        config,
        "_get_ssm_secret",
        lambda name: pytest.fail("SSM should not be read when env is set"),
    )

    assert config.get_secret_value("APP_ACCESS_TOKEN") == "env-token"


def test_get_secret_value_reads_ssm_when_env_missing(monkeypatch):
    monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(config, "SECRETS_PROVIDER", "ssm")
    monkeypatch.setattr(config, "_get_ssm_secret", lambda name: "ssm-token")

    assert config.get_secret_value("APP_ACCESS_TOKEN") == "ssm-token"


def test_required_secret_raises_when_missing(monkeypatch):
    monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(config, "SECRETS_PROVIDER", "ssm")
    monkeypatch.setattr(
        config,
        "_get_ssm_secret",
        lambda name: (_ for _ in ()).throw(RuntimeError("missing")),
    )

    with pytest.raises(RuntimeError):
        config.get_secret_value("APP_ACCESS_TOKEN", required=True)
