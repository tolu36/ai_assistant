import pytest

import config


def test_get_secret_value_prefers_environment(monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "env-password")
    monkeypatch.setattr(config, "SECRETS_PROVIDER", "ssm")
    monkeypatch.setattr(
        config,
        "_get_ssm_secret",
        lambda name: pytest.fail("SSM should not be read when env is set"),
    )

    assert config.get_secret_value("SMTP_PASSWORD") == "env-password"


def test_get_secret_value_reads_ssm_when_env_missing(monkeypatch):
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setattr(config, "SECRETS_PROVIDER", "ssm")
    monkeypatch.setattr(config, "_get_ssm_secret", lambda name: "ssm-password")

    assert config.get_secret_value("SMTP_PASSWORD") == "ssm-password"


def test_required_secret_raises_when_missing(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setattr(config, "SECRETS_PROVIDER", "ssm")
    monkeypatch.setattr(
        config,
        "_get_ssm_secret",
        lambda name: (_ for _ in ()).throw(RuntimeError("missing")),
    )

    with pytest.raises(RuntimeError):
        config.get_secret_value("MISTRAL_API_KEY", required=True)
