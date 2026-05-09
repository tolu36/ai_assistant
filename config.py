import os
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value


SECRETS_PROVIDER = _env("SECRETS_PROVIDER", "env").lower()
SSM_PARAMETER_PREFIX = _env("SSM_PARAMETER_PREFIX", "/personal-ai-assistant/prod")
_SSM_SECRET_CACHE: dict[str, str] = {}


def _ssm_parameter_name(name: str) -> str:
    suffix = name.lower()
    prefix = SSM_PARAMETER_PREFIX.rstrip("/")
    return f"{prefix}/{suffix}"


def _get_ssm_secret(name: str) -> str:
    if name in _SSM_SECRET_CACHE:
        return _SSM_SECRET_CACHE[name]

    import boto3

    response = boto3.client("ssm").get_parameter(
        Name=_ssm_parameter_name(name),
        WithDecryption=True,
    )
    value = response["Parameter"]["Value"]
    _SSM_SECRET_CACHE[name] = value
    return value


def get_secret_value(name: str, default: str = "", required: bool = False) -> str:
    value = os.getenv(name)
    if value is not None and value.strip():
        return value

    if SECRETS_PROVIDER == "ssm":
        try:
            secret = _get_ssm_secret(name)
            if secret.strip():
                return secret
        except Exception:
            if required:
                raise

    if required and not default:
        raise RuntimeError(f"{name} is required but was not configured.")
    return default


def secrets_configured() -> dict[str, bool]:
    names = ("APP_ACCESS_TOKEN", "SMTP_PASSWORD", "MISTRAL_API_KEY")
    return {name.lower(): bool(get_secret_value(name)) for name in names}


TIMEZONE = _env("TIMEZONE", "UTC")
GOOGLE_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CREDENTIALS_PATH", "credentials/credentials.json"
)
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "credentials/token.json")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
CALENDAR_PROVIDER = os.getenv("CALENDAR_PROVIDER", "google")
SCHEDULER_DAY_START_HOUR = int(os.getenv("SCHEDULER_DAY_START_HOUR", "9"))
SCHEDULER_DAY_END_HOUR = int(os.getenv("SCHEDULER_DAY_END_HOUR", "22"))
SCHEDULER_DEFAULT_HOUR = int(os.getenv("SCHEDULER_DEFAULT_HOUR", "18"))
DEFAULT_NEWS_RSS_FEEDS = ",".join(
    [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.cbsnews.com/latest/rss/world",
        "https://www.theguardian.com/world/rss",
        "https://nationalpost.com/feed/",
        "https://globalnews.ca/feed/",
        "https://globalnews.ca/canada/feed/",
        "https://globalnews.ca/world/feed/",
    ]
)
DEFAULT_FINANCE_RSS_FEEDS = ",".join(
    [
        "https://finance.yahoo.com/news/rss",
        "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        "https://www.marketwatch.com/rss/topstories",
        "https://www.bloomberg.com/feed/podcast/etf-report.xml",
        "https://www.bankofcanada.ca/content_type/press-releases/feed/",
        "https://www.federalreserve.gov/feeds/press_monetary.xml",
        "https://www150.statcan.gc.ca/n1/rss/dai-quo/18-eng.atom",
        "https://www150.statcan.gc.ca/n1/rss/dai-quo/46-eng.atom",
    ]
)
NEWS_RSS_FEEDS = os.getenv("NEWS_RSS_FEEDS", DEFAULT_NEWS_RSS_FEEDS)
FINANCE_RSS_FEEDS = os.getenv("FINANCE_RSS_FEEDS", DEFAULT_FINANCE_RSS_FEEDS)
RSS_TIMEOUT_SECONDS = float(os.getenv("RSS_TIMEOUT_SECONDS", "3"))
ARTICLE_FETCH_TIMEOUT_SECONDS = float(os.getenv("ARTICLE_FETCH_TIMEOUT_SECONDS", "5"))
NEWS_SUMMARY_PROVIDER = os.getenv("NEWS_SUMMARY_PROVIDER", "auto")
NEWS_SUMMARY_SENTENCES = int(os.getenv("NEWS_SUMMARY_SENTENCES", "5"))
NEWS_SUMMARY_MAX_ARTICLES = int(os.getenv("NEWS_SUMMARY_MAX_ARTICLES", "6"))
SPORTS_INTERESTS = os.getenv("SPORTS_INTERESTS", "NBA,NHL")
SPORTS_TEAMS = os.getenv("SPORTS_TEAMS", "")
FINANCE_WATCHLIST = os.getenv(
    "FINANCE_WATCHLIST",
    "XEQT.TO,VEQT.TO,VFV.TO,XIC.TO,ZAG.TO,CASH.TO,VTI,VOO,VT",
)
PREFERENCES_DB_PATH = os.getenv("PREFERENCES_DB_PATH", "data/preferences.db")
SCHEDULER_DB_PATH = os.getenv("SCHEDULER_DB_PATH", "data/scheduler.db")
BRIEF_HISTORY_DB_PATH = os.getenv("BRIEF_HISTORY_DB_PATH", "data/brief_history.db")
STORAGE_PROVIDER = _env("STORAGE_PROVIDER", "sqlite")
DYNAMODB_TABLE_NAME = _env("DYNAMODB_TABLE_NAME", "personal-ai-assistant")
DYNAMODB_USER_ID = _env("DYNAMODB_USER_ID", "default")
APP_ACCESS_TOKEN = get_secret_value(
    "APP_ACCESS_TOKEN",
    "",
    required=SECRETS_PROVIDER == "ssm",
)
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

SMTP_HOST = _env("SMTP_HOST", "")
SMTP_PORT = int(_env("SMTP_PORT", "587"))
SMTP_USERNAME = _env("SMTP_USERNAME", "")
SMTP_PASSWORD = get_secret_value("SMTP_PASSWORD", "")
SMTP_USE_TLS = _env("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
SMTP_USE_SSL = _env("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
MORNING_BRIEF_FROM_EMAIL = _env("MORNING_BRIEF_FROM_EMAIL", SMTP_USERNAME)
MORNING_BRIEF_TO_EMAIL = _env("MORNING_BRIEF_TO_EMAIL", "")
MORNING_BRIEF_SUBJECT_PREFIX = _env(
    "MORNING_BRIEF_SUBJECT_PREFIX", "Personal AI Assistant"
)

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "fallback")
MODEL_FALLBACK_PROVIDER = os.getenv("MODEL_FALLBACK_PROVIDER", "transformers")
MODEL_NAME = os.getenv("OPEN_SOURCE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "256"))
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.1"))
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "auto")
LLAMA_CPP_MODEL_PATH = os.getenv("LLAMA_CPP_MODEL_PATH", "")
MISTRAL_API_URL = os.getenv(
    "MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions"
)
MISTRAL_API_KEY = get_secret_value("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
MISTRAL_MIN_SECONDS_BETWEEN_REQUESTS = float(
    os.getenv("MISTRAL_MIN_SECONDS_BETWEEN_REQUESTS", "1.1")
)
