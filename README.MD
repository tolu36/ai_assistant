# Personal AI Assistant MVP

A free/open-source personal AI assistant for task scheduling and daily briefing.
The project is designed to minimize cost by favoring RSS sources, local fallback
logic, optional free/low-cost LLM providers, and AWS serverless services that
fit a small single-user app.

## Current Deployment Status

The current hosted MVP runs on AWS:

- **Lambda Function URL** hosts the FastAPI API and browser UI.
- **DynamoDB** stores preferences, brief history, scheduler proposals, and feedback constraints.
- **EventBridge Scheduler** invokes the morning email job at 9 AM America/Toronto.
- **SSM Parameter Store SecureString** stores hosted secrets such as the app token, SMTP password, and Mistral key.
- **Gmail SMTP** sends the morning brief email.
- **Mistral** is enabled for hosted LLM-backed behavior.
- **Google Calendar is mocked in hosted mode** for now; local Google Calendar support still exists.

Local development still uses SQLite by default, so the app can run without AWS.

## What This Project Solves

- Accepts natural-language tasks such as "study for 2 hours tonight"
- Finds available calendar time and avoids conflicts
- Creates calendar events after a task is scheduled or a proposal is confirmed
- Generates a morning brief with daily note, news, sports, and finance sections
- Stores single-user preferences locally in SQLite or hosted in DynamoDB
- Sends the morning brief by email from the hosted scheduler

## Key Principles

- Low/no ongoing cost for single-user MVP usage
- Open-source and free services first
- Google Calendar only for calendar reads/writes; hosted mode currently uses mock calendar
- RSS-based briefing content
- Optional LLM support with deterministic fallback behavior

## MVP Features

| Feature | Description |
| --- | --- |
| Task scheduling | Parses natural-language tasks and schedules calendar events |
| Schedule proposals | Suggests time slots before booking and accepts feedback |
| Slot confirmation | Lets you confirm all proposed times or a single proposed time |
| Calendar conflict checks | Reads busy calendar slots before selecting a time |
| Morning brief | Shows a daily note, news, sports, and finance updates |
| Brief history | Lets saved briefs be reopened from the UI |
| Preferences | Stores sports interests, teams, and finance watchlists in SQLite locally or DynamoDB on AWS |
| Hosted UI | Provides a browser UI through AWS Lambda Function URL |
| Morning email | Sends the daily brief from EventBridge Scheduler through Gmail SMTP |
| Status endpoint | Reports non-secret runtime configuration and provider health |
| Source notices | Shows RSS/article/LLM fallback notices when sources are unavailable |
| Daily note | Uses the configured LLM when available to add a short daily quote and reflection |

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
- `app/routes/status.py` - non-secret operational status API
- `app/aws_lambda.py` - Lambda handler for HTTP requests and scheduled events
- `app/services/llm_parser.py` - task parsing and fallback logic
- `app/services/scheduler.py` - time slot selection
- `app/services/calendar.py` - Google Calendar integration
- `app/services/brief_generator.py` - RSS news, sports, and finance briefing
- `app/services/brief_history.py` - local/AWS morning brief history
- `app/services/email_delivery.py` - SMTP email rendering and delivery
- `app/services/preferences.py` - local/AWS preference storage
- `app/services/dynamodb_store.py` - hosted DynamoDB persistence
- `app/services/schedule_feedback.py` - scheduler feedback constraints
- `app/services/schedule_store.py` - scheduler proposal persistence
- `deploy/aws/template.yaml` - AWS SAM deployment template

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

Check system status:

```powershell
curl.exe "http://127.0.0.1:8000/status"
```

## Configuration

Key environment variables:

Local `.env` files are loaded automatically. Values already set in your shell
or hosting environment take precedence over `.env`.

- `MODEL_PROVIDER` - `fallback`, `transformers`, `mistral`, or `llama_cpp`
- `MODEL_FALLBACK_PROVIDER` - fallback after the primary model, usually `transformers`
- `MISTRAL_API_KEY` - API key for Mistral when `MODEL_PROVIDER=mistral`
- `MISTRAL_MODEL` - defaults to `mistral-small-latest`
- `OPEN_SOURCE_MODEL` - Transformers model name
- `SECRETS_PROVIDER` - `env` locally, `ssm` for AWS hosted secrets
- `SSM_PARAMETER_PREFIX` - SSM prefix, defaults to `/personal-ai-assistant/prod`
- `CALENDAR_PROVIDER` - `mock` or `google`
- `GOOGLE_CREDENTIALS_PATH` - Google OAuth credentials file
- `GOOGLE_TOKEN_PATH` - Google OAuth token file
- `GOOGLE_CALENDAR_ID` - calendar id, defaults to `primary`
- `NEWS_SUMMARY_PROVIDER` - `off`, `llm`, or `auto`
- `NEWS_RSS_FEEDS` - comma-separated news feeds
- `FINANCE_RSS_FEEDS` - comma-separated finance and macro feeds
- `FINANCE_TOPICS` - comma-separated financial news topics such as rates, inflation, housing, Bank of Canada, employment, or global economy
- `FINANCE_INTELLIGENCE_PROVIDER` - `off`, `auto`, or `llm` for finance synthesis
- `DAILY_NOTE_PROVIDER` - `off`, `auto`, or `llm` for the daily quote and reflection
- `DAILY_QUOTE_ENABLED` - `true` or `false`
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

The local email path is implemented in `scripts/send_morning_brief.py`.
It generates the morning brief, saves it to SQLite history, renders text and
HTML versions, and sends it through SMTP. In the hosted AWS deployment, the same
brief generation and email delivery logic is invoked by EventBridge Scheduler
through `app/aws_lambda.py`, with brief history saved to DynamoDB.

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

For local Windows scheduling, run this only if you are not using the hosted AWS
EventBridge schedule:

```powershell
.\scripts\register_windows_morning_brief_task.ps1
```

The current hosted MVP uses AWS EventBridge Scheduler as the only production
morning email scheduler. Avoid adding a second scheduler for the same script,
or you can receive duplicate morning briefs from separate runtimes with
different configuration.

## Daily Note Behavior

The daily note appears at the top of the morning brief. When
`DAILY_NOTE_PROVIDER=auto`, the app uses the configured LLM if one is enabled;
otherwise it falls back to a small built-in set of original quotes and
reflection prompts. Use `DAILY_NOTE_PROVIDER=llm` when you want to force an LLM
attempt, while still keeping the fallback if the API is unavailable.

The quote is generated as an original line, not a famous attributed quote. The
reflection is a short personal cue for gratitude, focus, progress, or intention.

## Finance Brief Behavior

The finance section is a monitoring brief, not financial advice. It is built to:

- Split the finance brief into financial news/macro context and companies, stocks, ETFs to watch
- Lead with broad domestic/global financial context
- Explain why headlines may matter for ETFs, rates, inflation, housing, bonds, cash yields, and broad markets
- Use configured finance topics from the UI or `FINANCE_TOPICS` to prioritize financial news
- Use your configured companies, stocks, and ETF watchlist from the UI or `FINANCE_WATCHLIST` as a market-watch relevance signal
- Add free Yahoo Finance ticker-specific RSS feeds for watchlist symbols
- Surface macro stories about rates, inflation, housing, ETFs, indexes, and earnings
- Include starter monitoring ideas when no watchlist is configured
- Return structured items with `source`, `title`, `summary`, `link`, optional tags, `why_it_matters`, and `watch_for`

Starter monitor ideas focus on broad ETFs and indexes by default, such as
`XEQT.TO`, `VEQT.TO`, `VFV.TO`, `XIC.TO`, `ZAG.TO`, `CASH.TO`, `VTI`, `VOO`,
and `VT`. They are meant to help you decide what to follow, not what to buy or
sell.

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

## Hosting

The active hosted deployment uses AWS serverless. It runs the app with Lambda
Function URLs, DynamoDB, EventBridge Scheduler, SSM Parameter Store, Gmail SMTP,
and Mistral. Setup details are in `docs/aws-always-free-serverless.md`.

After code changes, rebuild and redeploy from WSL in the repository root:

```bash
sam build --template-file deploy/aws/template.yaml
sam deploy --resolve-s3 --no-confirm-changeset --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --profile ai-assistant --region us-east-2 --stack-name personal-ai-assistant --template-file .aws-sam/build/template.yaml
```

To keep the hosted app using Mistral-backed article summaries, finance
intelligence, and daily notes, deploy with these non-secret parameter overrides:

```bash
sam deploy --resolve-s3 --no-confirm-changeset --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --profile ai-assistant --region us-east-2 --stack-name personal-ai-assistant --template-file .aws-sam/build/template.yaml --parameter-overrides ModelProvider=mistral NewsSummaryProvider=llm FinanceIntelligenceProvider=llm DailyNoteProvider=llm DailyQuoteEnabled=true
```

Secrets are not passed in deploy commands. Hosted secrets live in SSM Parameter
Store under the configured `SSM_PARAMETER_PREFIX`.

Use Oracle Cloud Always Free when you want a traditional VPS. The VPS keeps
SQLite state and runs the 9 AM email job from the same app data. Setup details
are in `docs/oracle-vps-setup.md`.

## Roadmap

Future improvements and wishlist items are tracked in `docs/roadmap.md`.

## Project Structure

```text
ai_assistant/
+-- app/
|   +-- main.py
|   +-- routes/
|   +-- services/
|   +-- static/
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
