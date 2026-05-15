import argparse
import pathlib
import shlex
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit


DEFAULT_PROFILE = "ai-assistant"
DEFAULT_REGION = "us-east-2"
DEFAULT_STACK_NAME = "personal-ai-assistant"
DEFAULT_TEMPLATE = ".aws-sam/build/template.yaml"


def read_env(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in (chr(34), chr(39)):
            value = value[1:-1]
        values[key.strip()] = value

    return values


def endpoint_origin(raw: str) -> str:
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return raw


def require_values(env: dict[str, str], names: list[str]) -> None:
    missing = [name for name in names if not env.get(name)]
    if missing:
        raise SystemExit("Missing required .env keys: " + ", ".join(missing))


def deploy(args: argparse.Namespace) -> None:
    env = read_env(pathlib.Path(args.env_file))

    require_values(
        env,
        [
            "SMTP_USERNAME",
            "MORNING_BRIEF_TO_EMAIL",
            "BRIEF_AUDIO_OBJECT_BUCKET",
            "BRIEF_AUDIO_OBJECT_ENDPOINT_URL",
        ],
    )

    def value(name: str, default: str = "") -> str:
        return env.get(name) or default

    email = value("MORNING_BRIEF_TO_EMAIL") or value("SMTP_USERNAME")
    model_provider = value("MODEL_PROVIDER", "fallback")
    if model_provider not in ("fallback", "mistral"):
        model_provider = "fallback"

    params = {
        "AppName": "personal-ai-assistant",
        "SsmParameterPrefix": "/personal-ai-assistant/prod",
        "SmtpHost": value("SMTP_HOST", "smtp.gmail.com"),
        "SmtpPort": value("SMTP_PORT", "587"),
        "SmtpUsername": value("SMTP_USERNAME"),
        "MorningBriefFromEmail": value(
            "MORNING_BRIEF_FROM_EMAIL",
            value("SMTP_USERNAME"),
        ),
        "MorningBriefToEmail": value("MORNING_BRIEF_TO_EMAIL"),
        "SportsInterests": value("SPORTS_INTERESTS", "NBA,NFL"),
        "SportsTeams": value("SPORTS_TEAMS", ""),
        "FinanceWatchlist": value(
            "FINANCE_WATCHLIST",
            "XEQT.TO,VEQT.TO,VFV.TO,XIC.TO,ZAG.TO,CASH.TO,VTI,VOO,VT",
        ),
        "FinanceTopics": value(
            "FINANCE_TOPICS",
            "interest rates,Bank of Canada,inflation,housing,bond yields,global economy,employment,currency",
        ),
        "NewsSummaryProvider": value("NEWS_SUMMARY_PROVIDER", "off"),
        "FinanceIntelligenceProvider": value("FINANCE_INTELLIGENCE_PROVIDER", "auto"),
        "DailyQuoteEnabled": value("DAILY_QUOTE_ENABLED", "true"),
        "DailyNoteProvider": value("DAILY_NOTE_PROVIDER", "auto"),
        "ModelProvider": model_provider,
        "PipelineScheduleExpression": value(
            "PIPELINE_SCHEDULE_EXPRESSION",
            "cron(45 8 * * ? *)",
        ),
        "ScheduleExpression": value("SCHEDULE_EXPRESSION", "cron(0 9 * * ? *)"),
        "ScheduleTimezone": value("TIMEZONE", "America/Toronto"),
        "BriefAudioRetentionDays": value("BRIEF_AUDIO_RETENTION_DAYS", "7"),
        "CloudflareR2BucketName": value("BRIEF_AUDIO_OBJECT_BUCKET"),
        "CloudflareR2EndpointUrl": endpoint_origin(value("BRIEF_AUDIO_OBJECT_ENDPOINT_URL")),
        "BriefAudioObjectPrefix": value("BRIEF_AUDIO_OBJECT_PREFIX", "brief-audio"),
        "PushVapidSubject": value("PUSH_VAPID_SUBJECT", f"mailto:{email}"),
    }

    overrides = [
        f"{key}={shlex.quote(param)}"
        for key, param in params.items()
        if param != ""
    ]
    command = [
        "sam",
        "deploy",
        "--resolve-s3",
        "--no-confirm-changeset",
        "--no-fail-on-empty-changeset",
        "--capabilities",
        "CAPABILITY_IAM",
        "CAPABILITY_AUTO_EXPAND",
        "--profile",
        args.profile,
        "--region",
        args.region,
        "--stack-name",
        args.stack_name,
        "--template-file",
        args.template_file,
        "--parameter-overrides",
        *overrides,
    ]

    subprocess.run(command, check=True)

    url = subprocess.run(
        [
            "aws",
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            args.stack_name,
            "--profile",
            args.profile,
            "--region",
            args.region,
            "--query",
            "Stacks[0].Outputs[?OutputKey=='AppUrl'].OutputValue|[0]",
            "--output",
            "text",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    print()
    print(f"AppUrl: {url}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy the Personal AI Assistant AWS stack.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--stack-name", default=DEFAULT_STACK_NAME)
    parser.add_argument("--template-file", default=DEFAULT_TEMPLATE)
    parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        deploy(parse_args())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
