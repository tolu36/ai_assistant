from datetime import date

from app.services import brief_generator
from app.services.brief_generator import generate_morning_brief, parse_rss_items


def test_generate_morning_brief_has_required_sections(monkeypatch):
    monkeypatch.setenv("NEWS_SUMMARY_PROVIDER", "off")
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_headlines",
        lambda feed_urls, limit=6, per_feed_limit=2: [
            {
                "source": "Mock News",
                "title": "Mock RSS headline",
                "summary": "This is a short test summary.",
                "link": "https://example.com/mock",
            }
        ],
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [],
    )

    result = generate_morning_brief(today=date(2026, 5, 7))

    assert result["date"] == "2026-05-07"
    assert result["daily_quote"][0]["source"] == "Daily Note"
    assert result["daily_quote"][0]["title"] == "Daily Quote"
    assert result["daily_quote"][0]["reflection"]
    assert result["news"][0]["title"] == "Mock RSS headline"
    assert result["news"][0]["summary"] == "This is a short test summary."
    assert len(result["sports"]) >= 2
    assert len(result["finance"]) >= 2


def test_parse_rss_items_extracts_titles_and_links():
    xml_text = """
    <rss>
      <channel>
        <title>Example News</title>
        <item>
          <title>First headline</title>
          <description>First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence. Sixth sentence.</description>
          <link>https://example.com/first</link>
        </item>
        <item>
          <title>Second headline</title>
          <description>Second description with &lt;strong&gt;HTML&lt;/strong&gt;. Continue reading...</description>
          <link>https://example.com/second</link>
        </item>
      </channel>
    </rss>
    """

    items = parse_rss_items(xml_text)

    assert items == [
        {
            "source": "Example News",
            "title": "First headline",
            "summary": "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence.",
            "link": "https://example.com/first",
        },
        {
            "source": "Example News",
            "title": "Second headline",
            "summary": "Second description with HTML.",
            "link": "https://example.com/second",
        },
    ]


def test_parse_atom_items_extracts_titles_links_and_summaries():
    xml_text = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Statistics Canada</title>
      <entry>
        <title>Consumer prices rise</title>
        <summary>Inflation rose in the latest monthly release. Food prices were a contributor. Extra sentence.</summary>
        <link href="https://example.com/cpi" />
      </entry>
    </feed>
    """

    items = parse_rss_items(xml_text)

    assert items == [
        {
            "source": "Statistics Canada",
            "title": "Consumer prices rise",
            "summary": "Inflation rose in the latest monthly release. Food prices were a contributor. Extra sentence.",
            "link": "https://example.com/cpi",
        }
    ]


def test_generate_morning_brief_uses_configured_rss(monkeypatch):
    monkeypatch.setenv("NEWS_SUMMARY_PROVIDER", "off")
    monkeypatch.setenv("NEWS_RSS_FEEDS", "https://example.com/rss")
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_headlines",
        lambda feed_urls, limit=6, per_feed_limit=2: [
            {
                "source": "Configured News",
                "title": "Configured RSS headline",
                "summary": "Configured summary.",
                "link": "https://example.com/configured",
            }
        ],
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [],
    )

    result = generate_morning_brief(today=date(2026, 5, 7))

    assert result["news"][0]["title"] == "Configured RSS headline"
    assert result["news"][0]["link"] == "https://example.com/configured"


def test_default_news_feeds_include_domestic_and_global_sources(monkeypatch):
    monkeypatch.delenv("NEWS_RSS_FEEDS", raising=False)

    feeds = brief_generator._get_env_csv(
        "NEWS_RSS_FEEDS",
        brief_generator.NEWS_RSS_FEEDS,
    )

    assert "https://www.cbc.ca/webfeed/rss/rss-canada" not in feeds
    assert "https://www.cbc.ca/webfeed/rss/rss-world" not in feeds
    assert "https://feeds.bbci.co.uk/news/world/rss.xml" in feeds
    assert "https://www.cbsnews.com/latest/rss/world" in feeds
    assert "https://www.theguardian.com/world/rss" in feeds
    assert "https://nationalpost.com/feed/" in feeds
    assert "https://globalnews.ca/feed/" in feeds
    assert "https://globalnews.ca/canada/feed/" in feeds
    assert "https://globalnews.ca/world/feed/" in feeds


def test_default_feeds_exclude_known_failing_sources(monkeypatch):
    monkeypatch.delenv("FINANCE_RSS_FEEDS", raising=False)

    finance_feeds = brief_generator._get_env_csv(
        "FINANCE_RSS_FEEDS",
        brief_generator.FINANCE_RSS_FEEDS,
    )
    sports_feeds = brief_generator._sports_feed_urls(["NBA", "NFL"])

    assert "https://www.reuters.com/markets/us/rss.xml" not in finance_feeds
    assert all("cbc.ca" not in feed for feed in sports_feeds)


def test_fetch_rss_headlines_limits_each_feed(monkeypatch):
    first_feed = """
    <rss><channel><title>First Source</title>
      <item><title>First A</title><description>First A summary.</description><link>https://example.com/a</link></item>
      <item><title>First B</title><description>First B summary.</description><link>https://example.com/b</link></item>
      <item><title>First C</title><description>First C summary.</description><link>https://example.com/c</link></item>
    </channel></rss>
    """
    second_feed = """
    <rss><channel><title>Second Source</title>
      <item><title>Second A</title><description>Second A summary.</description><link>https://example.com/d</link></item>
      <item><title>Second B</title><description>Second B summary.</description><link>https://example.com/e</link></item>
    </channel></rss>
    """

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return self.text.encode("utf-8")

    responses = {
        "https://example.com/first": first_feed,
        "https://example.com/second": second_feed,
    }

    monkeypatch.setattr(
        brief_generator,
        "urlopen",
        lambda request, timeout=3: FakeResponse(responses[request.full_url]),
    )

    headlines = brief_generator.fetch_rss_headlines(
        ["https://example.com/first", "https://example.com/second"],
        limit=4,
        per_feed_limit=1,
    )

    assert headlines == [
        {
            "source": "First Source",
            "title": "First A",
            "summary": "First A summary.",
            "link": "https://example.com/a",
        },
        {
            "source": "Second Source",
            "title": "Second A",
            "summary": "Second A summary.",
            "link": "https://example.com/d",
        },
    ]


def test_summarize_article_uses_llm_when_enabled(monkeypatch):
    monkeypatch.setenv("NEWS_SUMMARY_PROVIDER", "llm")
    monkeypatch.setattr(
        brief_generator,
        "generate_llm_text",
        lambda prompt: "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five. Sentence six.",
    )

    summary = brief_generator.summarize_article(
        {"source": "Example", "title": "Headline", "summary": "RSS fallback."},
        "Full article text.",
    )

    assert (
        summary
        == "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
    )


def test_daily_note_uses_llm_when_enabled(monkeypatch):
    monkeypatch.setenv("DAILY_NOTE_PROVIDER", "llm")
    monkeypatch.setattr(
        brief_generator,
        "generate_llm_text",
        lambda prompt: '{"quote":"Begin with one clear step and let the day gather momentum.","reflection":"What deserves your attention before the day gets noisy?"}',
    )

    result = brief_generator.build_daily_quote_section(date(2026, 5, 9))

    assert result[0]["generated_by"] == "llm"
    assert result[0]["title"] == "Daily Quote"
    assert result[0]["summary"] == "Begin with one clear step and let the day gather momentum."
    assert result[0]["reflection"] == "What deserves your attention before the day gets noisy?"


def test_daily_note_falls_back_when_llm_output_is_invalid(monkeypatch):
    monkeypatch.setenv("DAILY_NOTE_PROVIDER", "llm")
    monkeypatch.setattr(brief_generator, "generate_llm_text", lambda prompt: "not json")

    result = brief_generator.build_daily_quote_section(date(2026, 5, 9))

    assert result[0]["generated_by"] == "fallback"
    assert result[0]["summary"]
    assert result[0]["reflection"]


def test_generate_morning_brief_uses_sports_interests_and_teams(monkeypatch):
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": ["NBA", "Tennis"],
            "sports_teams": ["Toronto Raptors", "Serena Williams"],
            "finance_watchlist": [],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [
            {
                "source": "ESPN NBA",
                "title": "Toronto Raptors win late",
                "summary": "The Raptors rallied late. The bench scored 30 points. Extra sentence.",
                "link": "https://example.com/raptors",
            },
            {
                "source": "ESPN Tennis",
                "title": "Serena Williams announces exhibition match",
                "summary": "Williams announced a new exhibition match.",
                "link": "https://example.com/serena",
            },
        ],
    )

    result = generate_morning_brief(today=date(2026, 5, 7))

    assert len(result["sports"]) == 2
    assert result["sports"][0]["matched_interest"] == "Toronto Raptors"
    assert (
        result["sports"][0]["summary"]
        == "The Raptors rallied late. The bench scored 30 points."
    )
    assert result["sports"][0]["link"] == "https://example.com/raptors"
    assert result["sports"][1]["matched_interest"] == "Serena Williams"


def test_sports_section_shows_league_headlines_when_teams_do_not_match(monkeypatch):
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": ["NBA"],
            "sports_teams": ["Toronto Raptors"],
            "finance_watchlist": [],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [
            {
                "source": "ESPN NBA",
                "title": "Knicks injury update",
                "summary": "League news.",
                "link": "https://example.com/knicks",
            }
        ],
    )

    result = brief_generator.build_sports_section()

    assert (
        result[0]
        == "Sports: No team-specific headlines found right now; showing league headlines instead."
    )
    assert result[1]["title"] == "Knicks injury update"
    assert result[1]["summary"] == "League news."
    assert result[1]["link"] == "https://example.com/knicks"


def test_sports_section_matches_team_alias_tokens(monkeypatch):
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": ["NBA"],
            "sports_teams": ["OKC Thunder"],
            "finance_watchlist": [],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [
            {
                "source": "ESPN NBA",
                "title": "OKC up 2-0 on Lakers as Holmgren, SGA score 22",
                "summary": "The Thunder took command of Game 2.",
                "link": "https://example.com/okc",
            }
        ],
    )

    result = brief_generator.build_sports_section()

    assert len(result) == 1
    assert result[0]["matched_interest"] == "OKC Thunder"
    assert result[0]["title"] == "OKC up 2-0 on Lakers as Holmgren, SGA score 22"


def test_sports_summary_falls_back_to_title_for_empty_summary():
    summary = brief_generator.summarize_sports_item(
        {
            "source": "ESPN NBA",
            "title": "Follow live: Pistons build early lead",
            "summary": "null",
            "link": "https://example.com/live",
        }
    )

    assert summary == "Follow live: Pistons build early lead"


def test_generate_morning_brief_uses_finance_watchlist(monkeypatch):
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": [],
            "sports_teams": [],
            "finance_watchlist": ["AAPL", "NVDA", "SPY"],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [],
    )

    result = generate_morning_brief(today=date(2026, 5, 7))

    assert result["finance"][0]["source"] == "Finance Intelligence"
    assert any(
        isinstance(item, dict) and "AAPL, NVDA, SPY" in item.get("summary", "")
        for item in result["finance"]
    )


def test_finance_feed_urls_include_watchlist_feeds(monkeypatch):
    monkeypatch.setenv("FINANCE_RSS_FEEDS", "https://example.com/base")

    feeds = brief_generator._finance_feed_urls(["AAPL", "RY.TO"])

    assert feeds == [
        "https://finance.yahoo.com/rss/headline?s=AAPL",
        "https://finance.yahoo.com/rss/headline?s=RY.TO",
        "https://example.com/base",
    ]


def test_build_finance_section_returns_watchlist_and_headlines(monkeypatch):
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": [],
            "sports_teams": [],
            "finance_topics": ["Inflation"],
            "finance_watchlist": ["AAPL", "NVDA"],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [
            {
                "source": "Mock Finance",
                "title": "AAPL earnings beat expectations",
                "summary": "Apple reported stronger than expected quarterly results.",
                "link": "https://example.com/aapl",
            },
            {
                "source": "Mock Finance",
                "title": "Global inflation data surprises markets",
                "summary": "Inflation remains elevated in key economies.",
                "link": "https://example.com/inflation",
            },
        ],
    )

    result = generate_morning_brief(today=date(2026, 5, 7))

    assert result["finance"][0]["title"] == "Financial news snapshot"
    assert any(
        isinstance(item, dict) and "AAPL, NVDA" in item.get("summary", "")
        for item in result["finance"]
    )
    assert any(
        isinstance(item, dict) and "Macro watch" in item.get("category", "")
        for item in result["finance"]
    )
    assert any(
        isinstance(item, dict) and item.get("matched_ticker") == "AAPL"
        for item in result["finance"]
    )
    assert any(
        isinstance(item, dict) and item.get("impact_area", "").lower() == "inflation"
        for item in result["finance"]
    )
    assert any(
        isinstance(item, dict) and item.get("source") == "Mock Finance"
        for item in result["finance"]
    )


def test_build_finance_section_without_watchlist_returns_monitor_ideas(monkeypatch):
    monkeypatch.setattr(brief_generator, "FINANCE_WATCHLIST", "")
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": [],
            "sports_teams": [],
            "finance_watchlist": [],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [],
    )

    result = brief_generator.build_finance_section()

    assert result[0]["source"] == "Finance Intelligence"
    assert any(
        isinstance(item, dict) and item.get("category") == "All-in-one ETFs"
        for item in result
    )
    assert any(
        isinstance(item, dict) and item.get("category") == "Macro watch"
        for item in result
    )


def test_finance_intelligence_adds_why_it_matters_and_watch_for(monkeypatch):
    monkeypatch.setenv("FINANCE_INTELLIGENCE_PROVIDER", "off")
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": [],
            "sports_teams": [],
            "finance_watchlist": ["VFV.TO"],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [
            {
                "source": "Mock Macro",
                "title": "Bank of Canada signals interest rate caution",
                "summary": "Bond yields moved as investors assessed the path for policy rates.",
                "link": "https://example.com/rates",
            }
        ],
    )

    result = brief_generator.build_finance_section()

    assert result[0]["category"] == "Market context"
    assert "rate decisions" in result[0]["watch_for"]
    assert any(
        isinstance(item, dict)
        and item.get("impact_area") == "interest rates"
        and "bond ETF prices" in item.get("why_it_matters", "")
        for item in result
    )


def test_finance_intelligence_uses_llm_when_enabled(monkeypatch):
    monkeypatch.setenv("FINANCE_INTELLIGENCE_PROVIDER", "llm")
    monkeypatch.setattr(
        brief_generator,
        "generate_llm_text",
        lambda prompt: "Markets are focused on inflation and rate expectations. ETF investors should watch bonds, cash yields, and equity concentration. Next, monitor central-bank language and housing data.",
    )
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": [],
            "sports_teams": [],
            "finance_watchlist": ["VFV.TO"],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [
            {
                "source": "Mock Finance",
                "title": "Inflation report moves markets",
                "summary": "Investors reassessed rate expectations.",
                "link": "https://example.com/inflation",
            }
        ],
    )

    result = brief_generator.build_finance_section()

    assert result[0]["summary"].startswith("Markets are focused on inflation")


def test_finance_topics_prioritize_financial_news_section(monkeypatch):
    monkeypatch.setenv("FINANCE_INTELLIGENCE_PROVIDER", "off")
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": [],
            "sports_teams": [],
            "finance_topics": ["Bank of Canada", "Housing"],
            "finance_watchlist": ["VFV.TO"],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "fetch_rss_items",
        lambda feed_urls, per_feed_limit=8, limit=None: [
            {
                "source": "Mock Macro",
                "title": "Bank of Canada holds rates as housing market cools",
                "summary": "The central bank said housing activity remains sensitive to borrowing costs.",
                "link": "https://example.com/boc",
            },
            {
                "source": "Mock Markets",
                "title": "VFV.TO sees heavy ETF trading as US markets rally",
                "summary": "Broad US index ETFs moved higher.",
                "link": "https://example.com/vfv",
            },
        ],
    )

    result = brief_generator.build_finance_section()

    assert any(
        isinstance(item, dict)
        and item.get("section") == "financial_news"
        and item.get("impact_area") == "Bank of Canada"
        for item in result
    )
    assert any(
        isinstance(item, dict)
        and item.get("section") == "market_watch"
        and item.get("matched_ticker") == "VFV.TO"
        for item in result
    )


def test_generate_morning_brief_includes_source_health_notices(monkeypatch):
    monkeypatch.setenv("NEWS_RSS_FEEDS", "https://example.com/bad")
    monkeypatch.setenv("FINANCE_RSS_FEEDS", "")
    monkeypatch.setattr(
        brief_generator,
        "load_preferences",
        lambda: {
            "sports_interests": [],
            "sports_teams": [],
            "finance_topics": [],
            "finance_watchlist": [],
        },
    )
    monkeypatch.setattr(
        brief_generator,
        "urlopen",
        lambda request, timeout=3: (_ for _ in ()).throw(TimeoutError("slow feed")),
    )

    result = generate_morning_brief(today=date(2026, 5, 7))

    assert any(
        notice["title"] == "RSS feed unavailable"
        for notice in result["notices"]
    )
