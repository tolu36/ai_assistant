from datetime import date
import html
import logging
import os
import re
from typing import Any, Dict, List
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from app.services.preferences import load_preferences
from app.services.llm_parser import generate_llm_text, get_llm_status
from config import (
    ARTICLE_FETCH_TIMEOUT_SECONDS,
    FINANCE_RSS_FEEDS,
    FINANCE_WATCHLIST,
    NEWS_RSS_FEEDS,
    NEWS_SUMMARY_MAX_ARTICLES,
    NEWS_SUMMARY_PROVIDER,
    NEWS_SUMMARY_SENTENCES,
    RSS_TIMEOUT_SECONDS,
)

LOGGER = logging.getLogger(__name__)
RSS_USER_AGENT = "PersonalAIAssistant/0.1 (+https://localhost)"

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
    "Finance: Configure FINANCE_WATCHLIST to track tickers",
    "Markets: Review major index movement before the open",
]

SPORTS_RSS_FEEDS = {
    "sports": "https://www.espn.com/espn/rss/news",
    "nba": "https://www.espn.com/espn/rss/nba/news",
    "nhl": "https://www.espn.com/espn/rss/nhl/news",
    "nfl": "https://www.espn.com/espn/rss/nfl/news",
    "mlb": "https://www.espn.com/espn/rss/mlb/news",
    "soccer": "https://www.espn.com/espn/rss/soccer/news",
    "tennis": "https://www.espn.com/espn/rss/tennis/news",
    "cfl": "https://www.cbc.ca/webfeed/rss/rss-sports-cfl",
    "curling": "https://www.cbc.ca/webfeed/rss/rss-sports-curling",
    "golf": "https://www.espn.com/espn/rss/golf/news",
    "olympics": "https://www.espn.com/espn/rss/oly/news",
}

SPORTS_FALLBACK_RSS_FEEDS = {
    "sports": "https://www.cbc.ca/webfeed/rss/rss-sports",
    "nba": "https://www.cbc.ca/webfeed/rss/rss-sports-nba",
    "nhl": "https://www.cbc.ca/webfeed/rss/rss-sports-nhl",
    "nfl": "https://www.cbc.ca/webfeed/rss/rss-sports-nfl",
    "mlb": "https://www.cbc.ca/webfeed/rss/rss-sports-mlb",
    "soccer": "https://www.cbc.ca/webfeed/rss/rss-sports-soccer",
    "tennis": "https://www.cbc.ca/webfeed/rss/rss-sports-tennis",
}


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_env_csv(name: str, default: str) -> List[str]:
    return _split_csv(os.getenv(name, default))


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


def _feed_title(root: ET.Element) -> str:
    channel = root.find("channel")
    if channel is None:
        return ""
    return _first_text(channel, "title")


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

    return items


def fetch_rss_headlines(
    feed_urls: List[str],
    limit: int = 6,
    per_feed_limit: int = 2,
) -> List[Dict[str, str]]:
    headlines = []

    for feed_url in feed_urls:
        try:
            request = Request(feed_url, headers={"User-Agent": RSS_USER_AGENT})
            with urlopen(request, timeout=RSS_TIMEOUT_SECONDS) as response:
                xml_text = response.read().decode("utf-8", errors="replace")
            for item in parse_rss_items(xml_text, limit=per_feed_limit):
                headlines.append(item)
                if len(headlines) >= limit:
                    return headlines
        except Exception as exc:
            LOGGER.warning("Could not fetch RSS feed %s: %s", feed_url, exc)

    return headlines


def fetch_rss_items(
    feed_urls: List[str], per_feed_limit: int = 8
) -> List[Dict[str, str]]:
    items = []

    for feed_url in feed_urls:
        try:
            request = Request(feed_url, headers={"User-Agent": RSS_USER_AGENT})
            with urlopen(request, timeout=RSS_TIMEOUT_SECONDS) as response:
                xml_text = response.read().decode("utf-8", errors="replace")
            items.extend(parse_rss_items(xml_text, limit=per_feed_limit))
        except Exception as exc:
            LOGGER.warning("Could not fetch RSS feed %s: %s", feed_url, exc)

    return items


def fetch_article_text(link: str, max_chars: int = 6000) -> str:
    if not link:
        return ""
    try:
        request = Request(link, headers={"User-Agent": RSS_USER_AGENT})
        with urlopen(request, timeout=ARTICLE_FETCH_TIMEOUT_SECONDS) as response:
            html_text = response.read().decode("utf-8", errors="replace")
        return _clean_article_html(html_text)[:max_chars]
    except Exception as exc:
        LOGGER.warning("Could not fetch article %s: %s", link, exc)
        return ""


def _llm_summary_enabled() -> bool:
    provider = os.getenv("NEWS_SUMMARY_PROVIDER", NEWS_SUMMARY_PROVIDER).lower()
    if provider == "off":
        return False
    if provider == "llm":
        return True
    return get_llm_status()["enabled"]


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
        return item.get("summary", "")


def summarize_sports_item(item: Dict[str, str]) -> str:
    summary = item.get("summary", "")
    if not summary or summary.lower() == "null":
        summary = item.get("title", "")
    return _sentence_summary(summary, max_sentences=2)


def _normalize(value: str) -> str:
    return value.lower().strip()


def _finance_feed_urls() -> List[str]:
    return _get_env_csv("FINANCE_RSS_FEEDS", FINANCE_RSS_FEEDS) or []


def _match_watchlist(item: Dict[str, str], watchlist: List[str]) -> str:
    text = f"{item.get('source', '')} {item.get('title', '')} {item.get('summary', '')}".lower()
    for ticker in watchlist:
        normalized = ticker.lower().strip()
        if normalized and normalized in text:
            return ticker
    return ""


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
    text = f"{item.get('source', '')} {item.get('title', '')}".lower()

    for team in teams:
        if team.lower() in text:
            return team
    for interest in interests:
        if interest.lower() in text:
            return interest

    return ""


def _match_team(item: Dict[str, str], teams: List[str]) -> str:
    text = f"{item.get('source', '')} {item.get('title', '')}".lower()
    for team in teams:
        if team.lower() in text:
            return team
    return ""


def build_news_section() -> List[Dict[str, str]]:
    feeds = _get_env_csv("NEWS_RSS_FEEDS", NEWS_RSS_FEEDS)
    if not feeds:
        return DEFAULT_NEWS_ITEMS

    headlines = fetch_rss_headlines(feeds)
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
    items = fetch_rss_items(feed_urls)
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


def _finance_card(item: Dict[str, str], matched_ticker: str = "") -> str:
    summary = item.get("summary", "") or item.get("title", "")
    headline = _sentence_summary(summary, max_sentences=2)
    card = f"{item.get('source', 'Finance')}: {item.get('title', '')} — {headline}"
    if matched_ticker:
        card = f"Watchlist {matched_ticker}: {card}"
    return card


def build_finance_section() -> List[str]:
    preferences = load_preferences()
    watchlist = preferences["finance_watchlist"] or _get_env_csv(
        "FINANCE_WATCHLIST", FINANCE_WATCHLIST
    )
    if not watchlist:
        return DEFAULT_FINANCE_HEADLINES

    headlines = fetch_rss_items(_finance_feed_urls(), per_feed_limit=2)
    watchlist_lines = []
    general_lines = []

    for item in headlines:
        matched = _match_watchlist(item, watchlist)
        card = _finance_card(item, matched)
        if matched:
            watchlist_lines.append(card)
        else:
            general_lines.append(card)
        if len(watchlist_lines) >= 2 and len(general_lines) >= 2:
            break

    lines = [f"Finance watchlist: {', '.join(watchlist)}"]
    lines.append(
        "Macro watch: interest rates, inflation, housing market, and ETF flows remain important for your portfolio."
    )
    if watchlist_lines:
        lines.extend(watchlist_lines[:2])
    if general_lines:
        lines.extend(general_lines[:2])

    if len(lines) <= 2:
        broader = fetch_rss_headlines(_finance_feed_urls(), limit=3, per_feed_limit=1)
        if broader:
            lines.extend(_finance_card(item) for item in broader[:2])
        else:
            lines.append(
                "Finance: No finance headlines were available; check your FINANCE_RSS_FEEDS or network connectivity."
            )

    return lines


def generate_morning_brief(today: date | None = None) -> Dict[str, Any]:
    brief_date = today or date.today()
    return {
        "date": brief_date.isoformat(),
        "news": build_news_section(),
        "sports": build_sports_section(),
        "finance": build_finance_section(),
    }
