import os

TIMEZONE = os.getenv("TIMEZONE", "UTC")
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
        "https://www.cbc.ca/webfeed/rss/rss-canada",
        "https://www.cbc.ca/webfeed/rss/rss-world",
    ]
)
DEFAULT_FINANCE_RSS_FEEDS = ",".join(
    [
        "https://finance.yahoo.com/news/rss",
        "https://www.reuters.com/markets/us/rss.xml",
        "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        "https://www.marketwatch.com/rss/topstories",
        "https://www.bloomberg.com/feed/podcast/etf-report.xml",
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
FINANCE_WATCHLIST = os.getenv("FINANCE_WATCHLIST", "")
PREFERENCES_DB_PATH = os.getenv("PREFERENCES_DB_PATH", "data/preferences.db")
SCHEDULER_DB_PATH = os.getenv("SCHEDULER_DB_PATH", "data/scheduler.db")
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

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
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
MISTRAL_MIN_SECONDS_BETWEEN_REQUESTS = float(
    os.getenv("MISTRAL_MIN_SECONDS_BETWEEN_REQUESTS", "1.1")
)
