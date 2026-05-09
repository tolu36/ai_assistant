import os

from fastapi import APIRouter

from config import (
    CALENDAR_PROVIDER,
    MODEL_PROVIDER,
    NEWS_SUMMARY_PROVIDER,
    SECRETS_PROVIDER,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_USERNAME,
    STORAGE_PROVIDER,
    TIMEZONE,
    MORNING_BRIEF_TO_EMAIL,
    secrets_configured,
)

router = APIRouter()


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value


@router.get("")
async def system_status():
    secret_status = secrets_configured()
    email_configured = all(
        [
            _env("SMTP_HOST", SMTP_HOST),
            _env("SMTP_USERNAME", SMTP_USERNAME),
            _env("SMTP_PASSWORD", SMTP_PASSWORD),
            _env("MORNING_BRIEF_TO_EMAIL", MORNING_BRIEF_TO_EMAIL),
        ]
    )

    return {
        "storage_provider": _env("STORAGE_PROVIDER", STORAGE_PROVIDER),
        "calendar_provider": _env("CALENDAR_PROVIDER", CALENDAR_PROVIDER),
        "model_provider": _env("MODEL_PROVIDER", MODEL_PROVIDER),
        "news_summary_provider": _env(
            "NEWS_SUMMARY_PROVIDER",
            NEWS_SUMMARY_PROVIDER,
        ),
        "timezone": _env("TIMEZONE", TIMEZONE),
        "email_configured": email_configured,
        "secrets_provider": _env("SECRETS_PROVIDER", SECRETS_PROVIDER),
        "ssm_secrets_configured": all(secret_status.values()),
        "secrets_configured": secret_status,
    }
