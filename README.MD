# Personal AI Assistant MVP

A free/open-source personal AI assistant for task scheduling and daily briefing.
The project is designed to minimize cost by favoring RSS sources, SQLite, local
fallback logic, and optional open/free LLM providers.

## What This Project Solves

- Accepts natural-language tasks such as "study for 2 hours tonight"
- Finds available calendar time and avoids conflicts
- Creates calendar events after a task is scheduled or a proposal is confirmed
- Generates a morning brief with news, sports, and finance sections
- Stores single-user preferences in SQLite

## Key Principles

- No ongoing cost by default
- Open-source and free services first
- Google Calendar only for calendar reads/writes
- RSS-based briefing content
- Optional LLM support with deterministic fallback behavior

## MVP Features

| Feature | Description |
| --- | --- |
| Task scheduling | Parses natural-language tasks and schedules calendar events |
| Schedule proposals | Suggests time slots before booking and accepts feedback |
| Calendar conflict checks | Reads busy calendar slots before selecting a time |
| Morning brief | Shows news, sports, and finance updates |
| Preferences | Stores sports interests, teams, and finance watchlists in SQLite |
| Local UI | Provides a simple browser UI for trying the app |

## Out of Scope for the MVP

- Voice input
- Multi-user accounts
- Multi-calendar support
- Full conversational memory
- Task-manager integrations such as Notion or Todoist
- Personalized financial advice or buy/sell recommendations

## Architecture Overview

- `app/main.py` - FastAPI entrypoint
- `app/routes/schedule.py` - scheduling APIs
- `app/routes/brief.py` - morning brief API
- `app/routes/preferences.py` - preference APIs
- `app/routes/llm.py` - LLM status API
- `app/services/llm_parser.py` - task parsing and fallback logic
- `app/services/scheduler.py` - time slot selection
- `app/services/calendar.py` - Google Calendar integration
- `app/services/brief_generator.py` - RSS news, sports, and finance briefing
- `app/services/brief_history.py` - SQLite morning brief history
- `app/services/email_delivery.py` - SMTP email rendering and delivery
- `app/services/preferences.py` - SQLite preference storage
- `app/services/schedule_feedback.py` - scheduler feedback constraints
- `app/services/schedule_store.py` - scheduler proposal persistence

## Setup and Run

Create and activate your Conda environment:

```powershell
conda activate ai_ast
pip install -r requirements.txt
```

For local testing without real Google Calendar writes:

```powershell
$env:MODEL_PROVIDER="fallback"
$env:CALENDAR_PROVIDER="mock"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the UI:

```text
http://127.0.0.1:8000/
```

Open the API docs:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```powershell
conda run -n ai_ast python -m pytest -q
```

## API Examples

Schedule a task:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/schedule/task" -H "Content-Type: application/json" -d "{\"task\":\"Study for 2 hours tonight\"}"
```

Request a proposed schedule before booking:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/schedule/propose" -H "Content-Type: application/json" -d "{\"task\":\"Study for 2 hours 5 days a week\"}"
```

Fetch the morning brief:

```powershell
curl.exe http://127.0.0.1:8000/brief/morning
```

Send the morning brief email manually:

```powershell
conda run -n ai_ast python scripts/send_morning_brief.py
```

Preview the email without sending:

```powershell
conda run -n ai_ast python scripts/send_morning_brief.py --dry-run
```

Check LLM status:

```powershell
curl.exe "http://127.0.0.1:8000/llm/status?check=true"
```

## Configuration

Key environment variables:

Local `.env` files are loaded automatically. Values already set in your shell
or GitHub Actions environment take precedence over `.env`.

- `MODEL_PROVIDER` - `fallback`, `transformers`, `mistral`, or `llama_cpp`
- `MODEL_FALLBACK_PROVIDER` - fallback after the primary model, usually `transformers`
- `MISTRAL_API_KEY` - API key for Mistral when `MODEL_PROVIDER=mistral`
- `MISTRAL_MODEL` - defaults to `mistral-small-latest`
- `OPEN_SOURCE_MODEL` - Transformers model name
- `CALENDAR_PROVIDER` - `mock` or `google`
- `GOOGLE_CREDENTIALS_PATH` - Google OAuth credentials file
- `GOOGLE_TOKEN_PATH` - Google OAuth token file
- `GOOGLE_CALENDAR_ID` - calendar id, defaults to `primary`
- `NEWS_SUMMARY_PROVIDER` - `off`, `llm`, or `auto`
- `NEWS_RSS_FEEDS` - comma-separated news feeds
- `FINANCE_RSS_FEEDS` - comma-separated finance and macro feeds
- `FINANCE_WATCHLIST` - comma-separated tickers or company names to track
- `SPORTS_INTERESTS` - comma-separated sports categories
- `SPORTS_TEAMS` - comma-separated team names
- `PREFERENCES_DB_PATH` - preferences SQLite path
- `SCHEDULER_DB_PATH` - scheduler proposal SQLite path
- `BRIEF_HISTORY_DB_PATH` - morning brief history SQLite path
- `SMTP_HOST` - SMTP server host
- `SMTP_PORT` - SMTP server port, usually `587`
- `SMTP_USERNAME` - SMTP username
- `SMTP_PASSWORD` - SMTP password or app password
- `SMTP_USE_TLS` - `true` for STARTTLS
- `SMTP_USE_SSL` - `true` for SMTP over SSL
- `MORNING_BRIEF_FROM_EMAIL` - sender address
- `MORNING_BRIEF_TO_EMAIL` - recipient address
- `MORNING_BRIEF_SUBJECT_PREFIX` - subject prefix

## Morning Email

The daily email path is implemented in `scripts/send_morning_brief.py`.
It generates the morning brief, saves it to SQLite history, renders text and
HTML versions, and sends it through SMTP.

Use `--dry-run` first. That command does not send email:

```powershell
conda run -n ai_ast python scripts/send_morning_brief.py --dry-run
```

The real send requires SMTP settings. At minimum set:

- `SMTP_HOST`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `MORNING_BRIEF_TO_EMAIL`
- `MORNING_BRIEF_FROM_EMAIL`, unless it should use `SMTP_USERNAME`

Then run:

```powershell
conda run -n ai_ast python scripts/send_morning_brief.py
```

For local Windows scheduling, run:

```powershell
.\scripts\register_windows_morning_brief_task.ps1
```

For free hosted scheduling, use the included GitHub Actions workflow:

```text
.github/workflows/morning-brief-email.yml
```

It runs every day at 9:00 AM in `America/Toronto` and can also be started
manually from the GitHub Actions tab.

Add these repository secrets before enabling the workflow:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `MORNING_BRIEF_TO_EMAIL`

Optional secrets:

- `MORNING_BRIEF_FROM_EMAIL`
- `MORNING_BRIEF_SUBJECT_PREFIX`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`

Optional feed and preference values can be added as GitHub repository variables:

- `NEWS_RSS_FEEDS`
- `SPORTS_INTERESTS`
- `SPORTS_TEAMS`
- `FINANCE_WATCHLIST`
- `FINANCE_RSS_FEEDS`

## Finance Brief Behavior

The finance section is a monitoring brief, not financial advice. It is built to:

- Show your configured finance watchlist from the UI or `FINANCE_WATCHLIST`
- Add free Yahoo Finance ticker-specific RSS feeds for watchlist symbols
- Surface macro stories about rates, inflation, housing, ETFs, indexes, and earnings
- Include starter monitoring ideas when no watchlist is configured
- Return structured items with `source`, `title`, `summary`, `link`, and optional tags

Starter monitor ideas include Canadian banks, Canadian sectors, large global
market movers, and broad ETFs/indexes. They are meant to help you decide what
to follow, not what to buy or sell.

## Current Brief Sources

Default news and finance feeds are configured in `config.py`. The finance feeds
include general market RSS sources plus official macro feeds from the Bank of
Canada, Federal Reserve, and Statistics Canada.

## Brief History

The morning brief route saves generated briefs by default and returns a
`history_id`. You can fetch saved summaries with:

```powershell
curl.exe http://127.0.0.1:8000/brief/history
curl.exe http://127.0.0.1:8000/brief/history/1
```

Use `GET /brief/morning?save=false` when you want a one-off brief without
storing it.

## Free Hosting Recommendation

Use Oracle Cloud Always Free when you want dynamic preferences from the UI.
The VPS keeps SQLite state and runs the 9 AM email job from the same app data.
Setup details are in `docs/oracle-vps-setup.md`.

Use GitHub Actions only for a simpler scheduled email where preferences are
edited as GitHub variables. Details are in `docs/free-hosting.md`.

## Next Steps and Future Releases

- Add follow-up Q&A for brief items: `POST /brief/story/{story_id}/ask`
- Improve sports source reliability beyond RSS where free APIs are available
- Add multi-calendar support and combined availability checks
- Add user profiles if this moves beyond a single-user app

## Project Structure

```text
ai_assistant/
+-- app/
|   +-- main.py
|   +-- routes/
|   +-- services/
|   +-- static/
+-- .github/
+-- deploy/
+-- docs/
+-- scripts/
+-- data/
+-- credentials/
+-- tests/
+-- requirements.txt
+-- requirements-brief.txt
+-- config.py
+-- README.MD
```
