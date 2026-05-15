from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import html
import json
import logging
import os
import re
from typing import Any, Dict, List
from urllib.parse import quote
from urllib.request import Request, build_opener, ProxyHandler, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import xml.etree.ElementTree as ET

from app.services.preferences import load_preferences
from app.services.llm_parser import generate_llm_text, get_llm_status
from config import (
    ARTICLE_FETCH_TIMEOUT_SECONDS,
    DAILY_NOTE_PROVIDER,
    DAILY_QUOTE_ENABLED,
    FINANCE_INTELLIGENCE_PROVIDER,
    FINANCE_RSS_FEEDS,
    FINANCE_TICKER_FEED_LIMIT,
    FINANCE_TOPICS,
    FINANCE_WATCHLIST,
    OUTBOUND_HTTP_TRUST_ENV,
    NEWS_RSS_FEEDS,
    NEWS_SUMMARY_MAX_ARTICLES,
    NEWS_SUMMARY_PROVIDER,
    NEWS_SUMMARY_SENTENCES,
    RSS_TIMEOUT_SECONDS,
    TIMEZONE,
)

LOGGER = logging.getLogger(__name__)
RSS_USER_AGENT = "PersonalAIAssistant/0.1 (+https://localhost)"
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))
_BRIEF_NOTICES: ContextVar[List[Dict[str, str]] | None] = ContextVar(
    "brief_notices",
    default=None,
)

DEFAULT_NEWS_ITEMS = [
    {
        "source": "News",
        "title": "No RSS headlines available right now",
        "summary": "Check NEWS_RSS_FEEDS if this persists.",
        "link": "",
    },
]


DEFAULT_SPORTS_HEADLINES = [
    "Sports: Tell the assistant which sports or teams to follow",
    "Sports: Example sports include NBA, NHL, NFL, MLB, soccer, and tennis",
]

DEFAULT_FINANCE_HEADLINES = [
    "Finance intelligence is for research and context only, not investment advice.",
    "Macro watch: interest rates, inflation, housing, ETF/index flows, bonds, cash yields, currency moves, and major earnings can affect ETF portfolios and housing decisions.",
]

FINANCE_SECTION_FINANCIAL_NEWS = "financial_news"
FINANCE_SECTION_MARKET_WATCH = "market_watch"

DAILY_QUOTES = [
    "Small steady actions compound into meaningful progress.",
    "Start where you are, use what you have, and do the next useful thing.",
    "A clear mind and a grateful heart make the day easier to lead.",
    "Progress is built by showing up before everything feels perfect.",
    "Protect your attention; it is one of your most valuable assets.",
    "Every useful step today makes tomorrow a little less crowded.",
    "Calm consistency beats rushed intensity over the long run.",
    "You do not need the whole path to move one step forward.",
]

GRATITUDE_PROMPTS = [
    "Name one person, opportunity, or lesson you are grateful for today.",
    "Notice one ordinary thing that is making your life easier right now.",
    "Pick one small win from yesterday and carry that momentum forward.",
    "Choose one thing you can do today that your future self will appreciate.",
]

DEFAULT_FINANCE_MONITOR_IDEAS = [
    {
        "source": "Finance Monitor",
        "category": "All-in-one ETFs",
        "title": "Global all-equity and balanced ETF portfolios",
        "summary": "Monitor examples such as XEQT.TO, VEQT.TO, XGRO.TO, VGRO.TO, XBAL.TO, and VBAL.TO because they summarize broad equity and bond market direction in one holding.",
        "link": "",
    },
    {
        "source": "Finance Monitor",
        "category": "Canadian ETFs",
        "title": "Canadian market and bond ETF exposure",
        "summary": "Monitor examples such as XIC.TO, VCN.TO, ZCN.TO, ZAG.TO, VAB.TO, and XBB.TO to track Canadian equities, rates, credit conditions, and bond market moves.",
        "link": "",
    },
    {
        "source": "Finance Monitor",
        "category": "US and global ETFs",
        "title": "US, global, and international ETF benchmarks",
        "summary": "Monitor examples such as VFV.TO, VUN.TO, VTI, VOO, VT, VXUS, XEF.TO, and XEC.TO to understand broad US, global, developed, and emerging market trends.",
        "link": "",
    },
    {
        "source": "Finance Monitor",
        "category": "Cash and rate-sensitive ETFs",
        "title": "Cash, money market, and rate-sensitive ETF context",
        "summary": "Monitor examples such as CASH.TO, CBIL.TO, ZMMK.TO, and broad bond ETFs because policy rates, inflation, and yield changes can affect savings, bonds, mortgages, and ETF returns.",
        "link": "",
    },
]

FINANCE_MACRO_TOPICS = {
    "interest rates": [
        "interest rate",
        "interest rates",
        "policy rate",
        "central bank",
        "bank of canada",
        "federal reserve",
        "fed",
        "fomc",
        "yield",
        "bond",
        "mortgage rate",
    ],
    "inflation": [
        "inflation",
        "cpi",
        "consumer price",
        "prices and price indexes",
        "cost of living",
    ],
    "housing": [
        "housing",
        "home sales",
        "real estate",
        "mortgage",
        "rent",
        "household debt",
    ],
    "etfs and markets": [
        "etf",
        "index",
        "s&p",
        "nasdaq",
        "tsx",
        "dow",
        "markets",
        "stocks",
        "equities",
    ],
    "earnings": [
        "earnings",
        "revenue",
        "profit",
        "guidance",
        "quarterly results",
        "forecast",
    ],
    "employment": [
        "employment",
        "jobs",
        "labour market",
        "labor market",
        "unemployment",
        "wages",
        "payroll",
    ],
    "global economy": [
        "global economy",
        "gdp",
        "recession",
        "growth",
        "trade",
        "tariff",
        "supply chain",
        "china",
        "europe",
    ],
    "currency": [
        "currency",
        "canadian dollar",
        "loonie",
        "usd",
        "foreign exchange",
        "fx",
    ],
}

FINANCE_TOPIC_IMPACT = {
    "interest rates": {
        "why": "Rate changes can affect bond ETF prices, cash ETF yields, mortgage costs, bank earnings, and equity valuations.",
        "watch": "central bank language, yield moves, mortgage-rate changes, and bond ETF reactions",
    },
    "inflation": {
        "why": "Inflation data can influence rate expectations, real wages, consumer spending, and the balance between stocks, bonds, and cash.",
        "watch": "CPI trend, food and shelter costs, wage pressure, and market expectations for future cuts or hikes",
    },
    "housing": {
        "why": "Housing news matters for mortgage affordability, household debt, banks, REITs, construction, and your own real estate decisions.",
        "watch": "sales volume, prices, inventory, rents, mortgage delinquencies, and regional differences",
    },
    "etfs and markets": {
        "why": "Broad market moves can affect diversified ETFs more than single-company headlines.",
        "watch": "index direction, sector leadership, ETF flows, currency moves, and whether gains are broad or concentrated",
    },
    "earnings": {
        "why": "Earnings and guidance can shift sector sentiment and influence indexes held inside broad ETFs.",
        "watch": "revenue growth, margins, forward guidance, layoffs, and whether results change the wider market narrative",
    },
    "employment": {
        "why": "Employment and wage data can affect rate expectations, consumer spending, inflation pressure, and recession risk.",
        "watch": "job growth, unemployment, wages, hours worked, and whether labour data changes central-bank expectations",
    },
    "global economy": {
        "why": "Global growth, trade, and geopolitical economic events can affect broad equity ETFs, commodity prices, currencies, and investor risk appetite.",
        "watch": "GDP trends, trade policy, commodity moves, China and Europe headlines, supply chains, and recession signals",
    },
    "currency": {
        "why": "Currency moves can affect Canadian investors holding US or global ETFs and can influence import prices and inflation.",
        "watch": "CAD/USD moves, central-bank divergence, commodity sensitivity, and hedged versus unhedged ETF effects",
    },
}

SPORTS_RSS_FEEDS = {
    "sports": "https://www.espn.com/espn/rss/news",
    "nba": "https://www.espn.com/espn/rss/nba/news",
    "nhl": "https://www.espn.com/espn/rss/nhl/news",
    "nfl": "https://www.espn.com/espn/rss/nfl/news",
    "mlb": "https://www.espn.com/espn/rss/mlb/news",
    "soccer": "https://www.espn.com/espn/rss/soccer/news",
    "tennis": "https://www.espn.com/espn/rss/tennis/news",
    "golf": "https://www.espn.com/espn/rss/golf/news",
    "olympics": "https://www.espn.com/espn/rss/oly/news",
}

SPORTS_FALLBACK_RSS_FEEDS: Dict[str, str] = {}

TEAM_TOKEN_STOPWORDS = {
    "and",
    "city",
    "club",
    "fc",
    "new",
    "of",
    "sc",
    "the",
    "team",
    "united",
}


def _brief_notices() -> List[Dict[str, str]]:
    notices = _BRIEF_NOTICES.get()
    if notices is None:
        return []
    return notices


def _add_brief_notice(
    title: str,
    detail: str = "",
    severity: str = "warn",
) -> None:
    notices = _BRIEF_NOTICES.get()
    if notices is None or len(notices) >= 8:
        return
    notice = {
        "title": title,
        "severity": severity,
    }
    if detail:
        notice["detail"] = detail
    notices.append(notice)


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_env_csv(name: str, default: str) -> List[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        value = default
    return _split_csv(value)


def _first_text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _first_text_by_local_name(element: ET.Element, local_name: str) -> str:
    for child in element:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == local_name and child.text:
            return child.text.strip()
    return ""


def _elements_by_local_name(element: ET.Element, local_name: str) -> List[ET.Element]:
    return [
        child
        for child in element.iter()
        if child.tag.rsplit("}", 1)[-1] == local_name
    ]


def _atom_link(element: ET.Element) -> str:
    for child in element:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "link":
            return child.attrib.get("href", "") or (child.text or "").strip()
    return ""


def _clean_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\bContinue reading\.\.\.", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return text.strip()


def _clean_article_html(value: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", value)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<nav[^>]*>.*?</nav>", " ", text)
    text = re.sub(r"(?is)<footer[^>]*>.*?</footer>", " ", text)
    return _clean_text(text)


def _sentence_summary(text: str, max_sentences: int = 5) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
    if not sentences:
        return cleaned
    return " ".join(sentences[:max_sentences])


def _clean_llm_plain_summary(text: str, max_sentences: int = 3) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[*_`#>]+", "", cleaned)
    cleaned = re.sub(
        r"^\s*(?:Morning Brief|Finance Brief)\s*:\s*.*?(?=\s+\d+[\).]\s+)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"(^|\s)(?:\d+[\).]|[-•])\s+", " ", cleaned)
    cleaned = re.sub(
        r"\b(?:what[’']?s happening|why it matters|what to watch next|watch next|watch for)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return _sentence_summary(cleaned, max_sentences=max_sentences)


def _feed_title(root: ET.Element) -> str:
    channel = root.find("channel")
    if channel is not None:
        return _first_text(channel, "title")
    return _first_text_by_local_name(root, "title")


def parse_rss_items(xml_text: str, limit: int = 5) -> List[Dict[str, str]]:
    root = ET.fromstring(xml_text)
    source = _feed_title(root)
    items = []

    for item in root.findall(".//item"):
        title = _first_text(item, "title")
        link = _first_text(item, "link")
        description = _first_text(item, "description")
        if not description:
            description = _first_text_by_local_name(item, "encoded")
        if title:
            items.append(
                {
                    "source": _clean_text(source),
                    "title": _clean_text(title),
                    "summary": _sentence_summary(description or title),
                    "link": _clean_text(link),
                }
            )
        if len(items) >= limit:
            break

    if items:
        return items

    for entry in _elements_by_local_name(root, "entry"):
        title = _first_text_by_local_name(entry, "title")
        link = _atom_link(entry)
        description = _first_text_by_local_name(entry, "summary")
        if not description:
            description = _first_text_by_local_name(entry, "content")
        if title:
            items.append(
                {
                    "source": _clean_text(source),
                    "title": _clean_text(title),
                    "summary": _sentence_summary(description or title),
                    "link": _clean_text(link),
                }
            )
        if len(items) >= limit:
            break

    return items


def _add_rss_failure_notice(failures: List[str], got_items: bool) -> None:
    if not failures:
        return

    title = "Some RSS feeds unavailable" if got_items else "RSS sources unavailable"
    detail = (
        f"{len(failures)} feed(s) failed. First error: {failures[0]}"
        if got_items
        else f"Tried {len(failures)} feed(s). First error: {failures[0]}"
    )
    _add_brief_notice(title, detail)


def _open_url(request: Request, timeout: float):
    if OUTBOUND_HTTP_TRUST_ENV:
        return urlopen(request, timeout=timeout)
    return _NO_PROXY_OPENER.open(request, timeout=timeout)


def _fetch_single_rss_feed(
    feed_url: str,
    per_feed_limit: int,
) -> tuple[List[Dict[str, str]], str]:
    try:
        request = Request(feed_url, headers={"User-Agent": RSS_USER_AGENT})
        with _open_url(request, timeout=RSS_TIMEOUT_SECONDS) as response:
            xml_text = response.read().decode("utf-8", errors="replace")
        return parse_rss_items(xml_text, limit=per_feed_limit), ""
    except Exception as exc:
        LOGGER.warning("Could not fetch RSS feed %s: %s", feed_url, exc)
        return [], f"{feed_url}: {exc}"


def fetch_rss_headlines(
    feed_urls: List[str],
    limit: int = 6,
    per_feed_limit: int = 2,
) -> List[Dict[str, str]]:
    headlines = []
    failures = []
    if not feed_urls:
        return headlines

    max_workers = min(8, len(feed_urls))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(
            lambda url: _fetch_single_rss_feed(url, per_feed_limit),
            feed_urls,
        )
        for items, error in results:
            if error:
                failures.append(error)
                continue
            for item in items:
                headlines.append(item)
                if len(headlines) >= limit:
                    _add_rss_failure_notice(failures, got_items=True)
                    return headlines

    _add_rss_failure_notice(failures, got_items=bool(headlines))
    return headlines


def fetch_rss_items(
    feed_urls: List[str],
    per_feed_limit: int = 8,
    limit: int | None = None,
) -> List[Dict[str, str]]:
    items = []
    failures = []
    if not feed_urls:
        return items

    max_workers = min(8, len(feed_urls))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(
            lambda url: _fetch_single_rss_feed(url, per_feed_limit),
            feed_urls,
        )
        for feed_items, error in results:
            if error:
                failures.append(error)
                continue
            items.extend(feed_items)
            if limit is not None and len(items) >= limit:
                _add_rss_failure_notice(failures, got_items=True)
                return items[:limit]

    _add_rss_failure_notice(failures, got_items=bool(items))
    return items


def fetch_article_text(link: str, max_chars: int = 6000) -> str:
    if not link:
        return ""
    try:
        request = Request(link, headers={"User-Agent": RSS_USER_AGENT})
        with _open_url(request, timeout=ARTICLE_FETCH_TIMEOUT_SECONDS) as response:
            html_text = response.read().decode("utf-8", errors="replace")
        return _clean_article_html(html_text)[:max_chars]
    except Exception as exc:
        LOGGER.warning("Could not fetch article %s: %s", link, exc)
        _add_brief_notice(
            "Article text unavailable",
            f"{link}: {exc}",
        )
        return ""


def _llm_summary_enabled() -> bool:
    provider = os.getenv("NEWS_SUMMARY_PROVIDER", NEWS_SUMMARY_PROVIDER).lower()
    if provider == "off":
        return False
    if provider == "llm":
        return True
    return get_llm_status()["enabled"]


def _finance_intelligence_enabled() -> bool:
    provider = os.getenv(
        "FINANCE_INTELLIGENCE_PROVIDER",
        FINANCE_INTELLIGENCE_PROVIDER,
    ).lower()
    if provider == "off":
        return False
    if provider == "llm":
        return True
    return get_llm_status()["enabled"]


def _daily_quote_enabled() -> bool:
    value = os.getenv("DAILY_QUOTE_ENABLED")
    if value is None or not value.strip():
        return DAILY_QUOTE_ENABLED
    return value.lower() in ("1", "true", "yes")


def _daily_note_provider() -> str:
    return os.getenv("DAILY_NOTE_PROVIDER", DAILY_NOTE_PROVIDER).lower()


def _daily_note_llm_enabled() -> bool:
    provider = _daily_note_provider()
    if provider == "off":
        return False
    if provider == "llm":
        return True
    return get_llm_status()["enabled"]


def _extract_json_object(text: str) -> Dict[str, Any]:
    decoder = json.JSONDecoder()
    for matcher in re.finditer(r"\{", text or ""):
        candidate = text[matcher.start() :]
        try:
            parsed, _ = decoder.raw_decode(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return {}


def summarize_article(item: Dict[str, str], article_text: str) -> str:
    if not article_text or not _llm_summary_enabled():
        return item.get("summary", "")

    prompt = f"""
Summarize this news article for a personal morning brief.
Use exactly {NEWS_SUMMARY_SENTENCES} concise sentences when the article text supports it.
Do not add facts that are not in the article text.
Do not mention that you are an AI.

Source: {item.get("source", "")}
Title: {item.get("title", "")}
RSS summary: {item.get("summary", "")}
Article text:
{article_text}
"""
    try:
        summary = generate_llm_text(prompt)
        return _sentence_summary(
            summary, max_sentences=NEWS_SUMMARY_SENTENCES
        ) or item.get("summary", "")
    except Exception as exc:
        LOGGER.warning("Could not summarize article with LLM: %s", exc)
        _add_brief_notice(
            "News summary fallback",
            "The LLM summary failed for one or more stories, so RSS summaries were used.",
        )
        return item.get("summary", "")


def summarize_sports_item(item: Dict[str, str]) -> str:
    summary = item.get("summary", "")
    if not summary or summary.lower() == "null":
        summary = item.get("title", "")
    return _sentence_summary(summary, max_sentences=2)


def _normalize(value: str) -> str:
    return value.lower().strip()


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    unique = []
    for value in values:
        if value and value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def _fallback_daily_note(brief_date: date) -> Dict[str, str]:
    quote = DAILY_QUOTES[brief_date.toordinal() % len(DAILY_QUOTES)]
    reflection = GRATITUDE_PROMPTS[brief_date.toordinal() % len(GRATITUDE_PROMPTS)]
    return {
        "source": "Daily Note",
        "category": "Mindset",
        "title": "Daily Quote",
        "summary": quote,
        "reflection": reflection,
        "prompt": reflection,
        "generated_by": "fallback",
        "link": "",
    }


def _llm_daily_note(brief_date: date) -> Dict[str, str]:
    if not _daily_note_llm_enabled():
        return {}

    prompt = f"""
Create a personal morning daily note for {brief_date.isoformat()}.
Return only valid JSON with exactly these keys:
{{
  "quote": "one original positive or gratitude-focused quote, 8 to 22 words",
  "reflection": "one short reflection prompt for the user, 8 to 22 words"
}}

Rules:
- Make the quote original. Do not quote or attribute a famous person.
- Keep it grounded, warm, and useful for starting the day.
- Avoid cliches and avoid religious language.
- The reflection should ask the user to notice gratitude, progress, focus, or intention.
- Do not mention that you are an AI.
"""
    try:
        raw = generate_llm_text(prompt)
        parsed = _extract_json_object(raw)
        quote = _sentence_summary(str(parsed.get("quote", "")), max_sentences=1)
        reflection = _sentence_summary(
            str(parsed.get("reflection", "")),
            max_sentences=1,
        )
        if not quote or not reflection:
            _add_brief_notice(
                "Daily note fallback",
                "The LLM daily note response was not usable, so the built-in fallback was used.",
            )
            return {}
        return {
            "source": "Daily Note",
            "category": "Mindset",
            "title": "Daily Quote",
            "summary": quote,
            "reflection": reflection,
            "prompt": reflection,
            "generated_by": "llm",
            "link": "",
        }
    except Exception as exc:
        LOGGER.warning("Could not generate daily note with LLM: %s", exc)
        _add_brief_notice(
            "Daily note fallback",
            "The LLM daily note failed, so the built-in fallback was used.",
        )
        return {}


def build_daily_quote_section(brief_date: date) -> List[Dict[str, str]]:
    if not _daily_quote_enabled():
        return []

    daily_note = _llm_daily_note(brief_date) or _fallback_daily_note(brief_date)
    return [
        daily_note
    ]


def _normalize_ticker(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.\-]", "", value.strip().upper())


def _finance_feed_urls(watchlist: List[str] | None = None) -> List[str]:
    feeds = _get_env_csv("FINANCE_RSS_FEEDS", FINANCE_RSS_FEEDS) or []
    ticker_limit = int(os.getenv("FINANCE_TICKER_FEED_LIMIT", str(FINANCE_TICKER_FEED_LIMIT)))
    for ticker in (watchlist or [])[: max(0, ticker_limit)]:
        normalized = _normalize_ticker(ticker)
        if normalized:
            feeds.append(
                f"https://finance.yahoo.com/rss/headline?s={quote(normalized)}"
            )
    return _dedupe(feeds)


def _finance_search_text(item: Dict[str, str]) -> str:
    return (
        f"{item.get('source', '')} {item.get('title', '')} "
        f"{item.get('summary', '')}"
    ).lower()


def _match_watchlist(item: Dict[str, str], watchlist: List[str]) -> str:
    text = _finance_search_text(item)
    for ticker in watchlist:
        normalized = ticker.lower().strip()
        if not normalized:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])"
        if re.search(pattern, text) or (len(normalized) >= 4 and normalized in text):
            return ticker
    return ""


def _match_macro_topic(item: Dict[str, str]) -> str:
    text = _finance_search_text(item)
    for topic, keywords in FINANCE_MACRO_TOPICS.items():
        if any(keyword in text for keyword in keywords):
            return topic
    return ""


def _topic_match_tokens(topic: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", topic.lower())
    return [token for token in tokens if len(token) >= 3]


def _matches_finance_topic_text(text: str, topic: str) -> bool:
    normalized_topic = topic.lower().strip()
    if not normalized_topic:
        return False
    if normalized_topic in text:
        return True
    tokens = _topic_match_tokens(topic)
    if not tokens:
        return False
    return all(re.search(rf"\b{re.escape(token)}\b", text) for token in tokens)


def _match_user_finance_topic(item: Dict[str, str], topics: List[str]) -> str:
    text = _finance_search_text(item)
    for topic in topics:
        if _matches_finance_topic_text(text, topic):
            return topic
    return ""


def _finance_topic_impact(topic: str) -> Dict[str, str]:
    normalized = topic.lower().strip()
    if normalized == "bank of canada":
        return FINANCE_TOPIC_IMPACT["interest rates"]
    if normalized == "bond yields":
        return FINANCE_TOPIC_IMPACT["interest rates"]
    return FINANCE_TOPIC_IMPACT.get(normalized, {})


def _sports_feed_urls(interests: List[str]) -> List[str]:
    feed_urls = []
    keys = [_normalize(interest) for interest in interests]
    if not keys:
        keys = ["sports"]

    for key in keys:
        if key in SPORTS_RSS_FEEDS and SPORTS_RSS_FEEDS[key] not in feed_urls:
            feed_urls.append(SPORTS_RSS_FEEDS[key])
        if (
            key in SPORTS_FALLBACK_RSS_FEEDS
            and SPORTS_FALLBACK_RSS_FEEDS[key] not in feed_urls
        ):
            feed_urls.append(SPORTS_FALLBACK_RSS_FEEDS[key])

    if not feed_urls:
        feed_urls.append(SPORTS_RSS_FEEDS["sports"])
    return feed_urls


def _match_sports_item(
    item: Dict[str, str], interests: List[str], teams: List[str]
) -> str:
    text = _sports_search_text(item)

    for team in teams:
        if _matches_team_text(text, team):
            return team
    for interest in interests:
        if interest.lower() in text:
            return interest

    return ""


def _sports_search_text(item: Dict[str, str]) -> str:
    return (
        f"{item.get('source', '')} {item.get('title', '')} "
        f"{item.get('summary', '')}"
    ).lower()


def _team_match_tokens(team: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", team.lower())
    return [
        token
        for token in tokens
        if len(token) >= 3 and token not in TEAM_TOKEN_STOPWORDS
    ]


def _matches_team_text(text: str, team: str) -> bool:
    normalized_team = team.lower().strip()
    if not normalized_team:
        return False
    if normalized_team in text:
        return True
    return any(
        re.search(rf"\b{re.escape(token)}\b", text)
        for token in _team_match_tokens(team)
    )


def _match_team(item: Dict[str, str], teams: List[str]) -> str:
    text = _sports_search_text(item)
    for team in teams:
        if _matches_team_text(text, team):
            return team
    return ""


def build_news_section() -> List[Dict[str, str]]:
    feeds = _get_env_csv("NEWS_RSS_FEEDS", NEWS_RSS_FEEDS)
    if not feeds:
        return DEFAULT_NEWS_ITEMS

    headlines = fetch_rss_headlines(feeds)
    if _llm_summary_enabled():
        for item in headlines[:NEWS_SUMMARY_MAX_ARTICLES]:
            article_text = fetch_article_text(item.get("link", ""))
            item["summary"] = summarize_article(item, article_text)
    return headlines or [
        {
            "source": "News",
            "title": "RSS feeds configured, but no headlines could be fetched",
            "summary": "The configured feeds did not return readable headlines before the timeout.",
            "link": "",
        }
    ]


def _sports_card(item: Dict[str, str], matched_interest: str = "") -> Dict[str, str]:
    card = {
        "source": item.get("source", "Sports"),
        "title": item.get("title", ""),
        "summary": summarize_sports_item(item),
        "link": item.get("link", ""),
    }
    if matched_interest:
        card["matched_interest"] = matched_interest
    return card


def build_sports_section() -> List[Any]:
    preferences = load_preferences()
    interests = preferences["sports_interests"]
    teams = preferences["sports_teams"]
    if not interests and not teams:
        return DEFAULT_SPORTS_HEADLINES

    feed_urls = _sports_feed_urls(interests)
    items = fetch_rss_items(feed_urls, per_feed_limit=3, limit=10)
    lines = []
    league_lines = []

    for item in items:
        matched_interest = (
            _match_team(item, teams)
            if teams
            else _match_sports_item(item, interests, teams)
        )
        card = _sports_card(item, matched_interest)

        if matched_interest:
            lines.append(card)
        else:
            league_lines.append(card)
        if len(lines) >= 5:
            break

    if not lines and league_lines:
        return [
            "Sports: No team-specific headlines found right now; showing league headlines instead."
        ] + league_lines[:5]

    return lines or [
        f"Sports interests: {', '.join(interests) or 'None'}",
        f"Teams to follow: {', '.join(teams) or 'None'}",
        "Sports: No matching RSS headlines were found right now",
    ]


def _finance_card(
    item: Dict[str, str],
    matched_ticker: str = "",
    impact_area: str = "",
    section: str = "",
) -> Dict[str, str]:
    summary = item.get("summary", "") or item.get("title", "")
    category = "Market news"
    if matched_ticker:
        category = "Market mover"
    elif impact_area:
        category = "Financial news"

    card = {
        "source": item.get("source", "Finance"),
        "category": category,
        "section": section
        or (
            FINANCE_SECTION_MARKET_WATCH
            if matched_ticker
            else FINANCE_SECTION_FINANCIAL_NEWS
            if impact_area
            else FINANCE_SECTION_MARKET_WATCH
        ),
        "title": item.get("title", ""),
        "summary": _sentence_summary(summary, max_sentences=2),
        "link": item.get("link", ""),
    }
    if matched_ticker:
        card["matched_ticker"] = matched_ticker
        card["why_it_matters"] = (
            f"This mentions {matched_ticker}, so compare the story with your "
            "broader ETF exposure instead of treating one headline as a buy/sell signal."
        )
    if impact_area:
        card["impact_area"] = impact_area
        impact = _finance_topic_impact(impact_area)
        card["why_it_matters"] = impact.get(
            "why",
            "This may affect broad markets, ETFs, rates, or household financial decisions.",
        )
        card["watch_for"] = impact.get(
            "watch",
            "whether the story changes rates, inflation, earnings, or broad market sentiment",
        )
    if not matched_ticker and not impact_area:
        card["why_it_matters"] = (
            "Use this as market context and check whether it affects broad indexes, "
            "ETF holdings, rates, currency, or sector concentration."
        )
    return card


def _finance_topic_counts(items: List[Dict[str, str]], topics: List[str]) -> Dict[str, int]:
    topic_pool = _dedupe(topics + list(FINANCE_MACRO_TOPICS))
    counts = {topic: 0 for topic in topic_pool}
    for item in items:
        topic = _match_user_finance_topic(item, topics) or _match_macro_topic(item)
        if topic:
            counts[topic] += 1
    return counts


def _top_finance_topics(
    items: List[Dict[str, str]],
    topics: List[str],
    limit: int = 3,
) -> List[str]:
    counts = _finance_topic_counts(items, topics)
    ranked = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    return [topic for topic, count in ranked if count > 0][:limit]


def _finance_headline_digest(items: List[Dict[str, str]], limit: int = 8) -> str:
    lines = []
    for item in items[:limit]:
        source = item.get("source", "Finance")
        title = item.get("title", "")
        summary = item.get("summary", "")
        if title:
            lines.append(f"- {source}: {title}. {summary}")
    return "\n".join(lines)


def _default_finance_snapshot_summary(
    headlines: List[Dict[str, str]],
    watchlist: List[str],
    topics: List[str],
) -> str:
    top_topics = _top_finance_topics(headlines, topics)
    topic_text = ", ".join(top_topics) if top_topics else "financial news and macro conditions"
    watch_text = ", ".join(watchlist) if watchlist else "your ETF portfolio"
    if headlines:
        return (
            f"Today's finance feed is highlighting {topic_text}. Use these stories "
            f"to understand what may affect {watch_text}, especially broad equity ETFs, "
            "bond ETFs, cash-like ETFs, mortgage costs, and household purchasing power."
        )
    return (
        "Finance feeds did not return live headlines, so use the ETF and macro monitor "
        "list as a baseline. Focus on rates, inflation, housing, bond yields, broad "
        "indexes, ETF flows, and major earnings when new stories become available."
    )


def _llm_finance_snapshot_summary(
    headlines: List[Dict[str, str]],
    watchlist: List[str],
    topics: List[str],
) -> str:
    if not headlines or not _finance_intelligence_enabled():
        return ""

    prompt = f"""
Create a grounded personal finance morning brief using only the headlines below.
This is education and monitoring context, not financial advice.
Do not recommend buying, selling, or timing investments.
Write 3 concise sentences:
1. What is happening in global/domestic finance.
2. Why it may matter for ETF-heavy portfolios, housing, rates, or inflation.
3. What to watch next.
Return plain text only. Do not use markdown, bold text, bullets, numbering,
headings, labels, or section titles.

User financial news topics: {', '.join(topics) if topics else 'general financial news'}
User company/stock/ETF watchlist: {', '.join(watchlist) if watchlist else 'not configured'}
Headlines:
{_finance_headline_digest(headlines)}
"""
    try:
        summary = generate_llm_text(prompt)
        return _clean_llm_plain_summary(summary, max_sentences=3)
    except Exception as exc:
        LOGGER.warning("Could not build finance intelligence with LLM: %s", exc)
        _add_brief_notice(
            "Finance intelligence fallback",
            "The LLM finance synthesis failed, so deterministic finance context was used.",
        )
        return ""


def _finance_intelligence_cards(
    headlines: List[Dict[str, str]],
    watchlist: List[str],
    topics: List[str],
) -> List[Dict[str, str]]:
    summary = _llm_finance_snapshot_summary(headlines, watchlist, topics)
    if not summary:
        summary = _default_finance_snapshot_summary(headlines, watchlist, topics)

    watch_text = ", ".join(watchlist) if watchlist else "broad ETF exposure"
    topic_text = ", ".join(topics) if topics else "rates, inflation, housing, central banks, and global trends"
    return [
        {
            "source": "Finance Intelligence",
            "category": "Market context",
            "section": FINANCE_SECTION_FINANCIAL_NEWS,
            "title": "Financial news snapshot",
            "summary": summary,
            "why_it_matters": (
                "This frames the linked headlines around broad ETFs, rates, "
                "inflation, housing, bonds, and cash yields rather than single-stock noise."
            ),
            "watch_for": (
                "rate decisions, inflation releases, housing data, bond yields, "
                "ETF/index flows, earnings guidance, and currency moves"
            ),
            "link": "",
        },
        {
            "source": "Finance Intelligence",
            "category": "ETF lens",
            "section": FINANCE_SECTION_MARKET_WATCH,
            "title": "ETF portfolio lens",
            "summary": (
                f"Use {watch_text} as context for relevance, not as a recommendation list. "
                "For ETF-heavy investing, prioritize asset mix, geography, fees, currency, "
                "bond duration, cash yields, and whether market moves are broad or concentrated."
            ),
            "why_it_matters": (
                "Diversified ETFs can be affected by macro shifts even when the headline "
                "is about one company, sector, or country."
            ),
            "watch_for": (
                "whether a story affects equities, bonds, cash yields, housing affordability, "
                "or Canada/US/global allocation"
            ),
            "link": "",
        },
        {
            "source": "Finance Intelligence",
            "category": "Tracked topics",
            "section": FINANCE_SECTION_FINANCIAL_NEWS,
            "title": "Financial news focus",
            "summary": (
                f"Monitoring {topic_text}. Update Finance Topics in preferences when "
                "you want the brief to prioritize different macro or economic themes."
            ),
            "why_it_matters": (
                "This keeps the financial news section focused on what you explicitly "
                "want to understand, similar to sports and team preferences."
            ),
            "link": "",
        },
    ]


def _dedupe_finance_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    unique = []
    for item in items:
        key = item.get("link") or item.get("title")
        if not key or key in seen:
            continue
        unique.append(item)
        seen.add(key)
    return unique


def build_finance_section() -> List[Any]:
    preferences = load_preferences()
    finance_topics = _dedupe(
        preferences.get("finance_topics")
        or _get_env_csv("FINANCE_TOPICS", FINANCE_TOPICS)
    )
    watchlist = _dedupe(
        preferences.get("finance_watchlist", [])
        or _get_env_csv("FINANCE_WATCHLIST", FINANCE_WATCHLIST)
    )
    headlines = _dedupe_finance_items(
        fetch_rss_items(_finance_feed_urls(watchlist), per_feed_limit=2, limit=10)
    )
    watchlist_cards = []
    macro_cards = []
    market_cards = []

    for item in headlines:
        matched = _match_watchlist(item, watchlist)
        impact_area = _match_user_finance_topic(item, finance_topics) or _match_macro_topic(item)
        section = (
            FINANCE_SECTION_MARKET_WATCH
            if matched
            else FINANCE_SECTION_FINANCIAL_NEWS
            if impact_area
            else FINANCE_SECTION_MARKET_WATCH
        )
        card = _finance_card(item, matched, impact_area, section=section)
        if matched:
            watchlist_cards.append(card)
        elif impact_area:
            macro_cards.append(card)
        else:
            market_cards.append(card)
        if len(watchlist_cards) >= 3 and len(macro_cards) >= 3:
            break

    lines: List[Any] = []
    lines.extend(_finance_intelligence_cards(headlines, watchlist, finance_topics))
    lines.append(
        {
            "source": "Finance Intelligence",
            "category": "Important note",
            "section": FINANCE_SECTION_FINANCIAL_NEWS,
            "title": "Research context only",
            "summary": DEFAULT_FINANCE_HEADLINES[0],
            "link": "",
        }
    )
    lines.append(
        {
            "source": "Finance Intelligence",
            "category": "Macro watch",
            "section": FINANCE_SECTION_FINANCIAL_NEWS,
            "title": "What to stay informed on",
            "summary": DEFAULT_FINANCE_HEADLINES[1],
            "link": "",
        }
    )
    if watchlist:
        lines.append(
            {
                "source": "Finance Intelligence",
                "category": "Watchlist context",
                "section": FINANCE_SECTION_MARKET_WATCH,
                "title": "Companies, stocks, and ETFs to watch",
                "summary": (
                    f"Monitoring {', '.join(watchlist)}. This prioritizes relevance "
                    "in the brief; it is not a buy or sell recommendation."
                ),
                "link": "",
            }
        )
    else:
        lines.extend(
            {
                **item,
                "section": FINANCE_SECTION_MARKET_WATCH,
            }
            for item in DEFAULT_FINANCE_MONITOR_IDEAS
        )

    lines.extend(macro_cards[:3])
    lines.extend(watchlist_cards[:3])
    lines.extend(market_cards[:2])

    has_live_headline = any(
        isinstance(item, dict) and item.get("link") for item in lines
    )
    if not has_live_headline:
        lines.append(
            {
                "source": "Finance",
                "category": "Finance",
                "section": FINANCE_SECTION_FINANCIAL_NEWS,
                "title": "No finance headlines were available",
                "summary": "Check FINANCE_RSS_FEEDS or network connectivity if this persists. The starter monitor list is still shown so you can decide which companies, ETFs, and macro topics to follow.",
                "link": "",
            }
        )

    return lines


def _current_brief_date() -> date:
    try:
        timezone = ZoneInfo(TIMEZONE)
    except ZoneInfoNotFoundError:
        LOGGER.warning("Configured TIMEZONE %s was not found; using local date.", TIMEZONE)
        return date.today()
    return datetime.now(timezone).date()


def generate_morning_brief(today: date | None = None) -> Dict[str, Any]:
    token = _BRIEF_NOTICES.set([])
    brief_date = today or _current_brief_date()
    try:
        brief = {
            "date": brief_date.isoformat(),
            "daily_quote": build_daily_quote_section(brief_date),
            "news": build_news_section(),
            "sports": build_sports_section(),
            "finance": build_finance_section(),
        }
        brief["notices"] = list(_brief_notices())
        return brief
    finally:
        _BRIEF_NOTICES.reset(token)
