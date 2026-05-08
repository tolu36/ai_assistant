# 🧠 Personal AI Assistant – MVP

A free/open-source personal AI assistant for personal task scheduling and daily briefing.
This project is intentionally designed to minimize cost by favoring local models,
RSS news sources, and open-source tooling over paid API usage.

---

## 🔍 What this project solves
- Accepts natural-language tasks such as "study for 2 hours tonight"
- Finds available calendar time and books tasks
- Generates a morning brief with sports and finance headlines
- Keeps core behavior free and open-source whenever possible

---

## 📌 Key principles
- **No ongoing cost by default**
- **Open-source models and tools** wherever possible
- **Local-first** inference when affordable
- **Google Calendar only for event creation** via OAuth
- **RSS-based briefs** for finance and sports coverage

---

## 🚀 MVP Features
| Feature                    | Description                                                |
| -------------------------- | ---------------------------------------------------------- |
| Task Scheduling            | Accepts natural language tasks and creates calendar events |
| Smart Time Slot Allocation | Finds available time and avoids conflicts                  |
| Morning Brief              | Sends sports and finance summaries                         |
| Natural Language Input     | Understands commands like "study for 2 hours tonight"      |

---

## 🚫 Out of scope for the MVP
- Voice input
- Personalized task prioritization
- Multi-calendar support
- Conversational memory/history
- Integration with task managers (Notion, Todoist)

---

## 🧱 Architecture Overview
- `app/main.py` — FastAPI entrypoint
- `app/routes/schedule.py` — scheduling APIs
- `app/routes/brief.py` — morning brief API
- `app/services/llm_parser.py` — task parsing and fallback logic
- `app/services/scheduler.py` — time slot selection
- `app/services/calendar.py` — Google Calendar integration
- `app/services/brief_generator.py` — RSS news and finance/sports briefing
- `app/services/preferences.py` — user preference storage

---

## 💰 No-cost strategy
This project is built to stay free by default:
- Use free RSS feeds for briefing content
- Use local/open-source models for parsing and summarization when possible
- Use Google Calendar only for event creation with explicit consent
- Avoid paid OpenAI usage unless explicitly enabled

---

## 📦 Setup and run
1. Create and activate a Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Add Google credentials at `credentials/credentials.json`
3. Start the app

```powershell
uvicorn app.main:app --reload
```

4. Open the API docs

```text
http://127.0.0.1:8000/docs
```

---

## 🧪 Local testing
For local testing without real Google Calendar writes:

```powershell
$env:MODEL_PROVIDER="fallback"
$env:CALENDAR_PROVIDER="mock"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Schedule a task:

```powershell
curl.exe --% -X POST http://127.0.0.1:8000/schedule/task -H "Content-Type: application/json" -d "{"task":"Study for 2 hours tonight"}"
```

Fetch the morning brief:

```powershell
curl.exe http://127.0.0.1:8000/brief/morning
```

Run tests:

```powershell
python -m pytest -q
```

---

## ⚙️ Configuration
Key environment variables:
- `MODEL_PROVIDER` — `fallback`, `transformers`, `mistral`
- `OPEN_SOURCE_MODEL` — model name for Transformers
- `CALENDAR_PROVIDER` — `mock` or `google`
- `NEWS_SUMMARY_PROVIDER` — `off`, `llm`, or `auto`
- `NEWS_RSS_FEEDS` — comma-separated news feeds
- `FINANCE_RSS_FEEDS` — comma-separated finance feeds
- `FINANCE_WATCHLIST` — comma-separated tickers to track
- `SPORTS_INTERESTS` — sports categories to follow
- `SPORTS_TEAMS` — team names to follow
- `PREFERENCES_DB_PATH` — preferences SQLite path

---

## 💡 Finance brief behavior
The morning brief includes finance coverage focused on:
- Watchlist companies and tickers to monitor
- Macro market news such as interest rates, inflation, and housing
- ETF and stock stories that may impact investments

It is built to use free RSS sources and summary logic instead of paid news APIs.

---

## 🧭 Next steps and future releases
### Next improvements
- Add follow-up Q&A for brief items: `POST /brief/story/{story_id}/ask`
- Add recurring schedule proposals with confirm/revise workflow
- Add a lightweight frontend for briefs and scheduling
- Add multi-calendar support and combined availability checks
- Add user profiles and persisted personal preferences
- Expand finance signals with inflation, rates, housing, and earnings coverage

### Longer-term goals
- Improve the local open-source LLM stack
- Add offline caching and persistence
- Add push notification / webhook delivery for morning briefs
- Support additional briefing categories like local news and crypto

---

## 📁 Project structure
```text
ai_assistant/
├── app/
│   ├── main.py
│   ├── routes/
│   │   ├── schedule.py
│   │   └── brief.py
│   ├── services/
│   │   ├── llm_parser.py
│   │   ├── scheduler.py
│   │   ├── calendar.py
│   │   ├── brief_generator.py
│   │   └── preferences.py
├── data/
├── credentials/
├── tests/
├── requirements.txt
├── config.py
└── readme
```

---

## ✅ Summary
A zero-cost personal productivity assistant prototype that combines
open-source parsing, RSS-based briefing, and optional Google Calendar
integration for scheduling.
