# Next Chat Handoff

Use this file to catch up a new Codex chat on the current state of the
Personal AI Assistant project. Do not paste `.env` values, SMTP passwords, or
API keys into the next chat.

## Current Project State

- The app is a single-user Personal AI Assistant MVP.
- Local development runs with FastAPI and SQLite.
- Hosted production runs on AWS serverless:
  - Lambda Function URL hosts the FastAPI API and browser UI.
  - DynamoDB stores preferences, brief history, scheduler proposals, and scheduler feedback.
  - EventBridge Scheduler sends the morning brief at 9 AM America/Toronto.
  - SSM Parameter Store SecureString stores hosted secrets.
  - Gmail SMTP sends the morning email.
  - Mistral is used for hosted LLM-backed behavior.
  - Google Calendar is mocked in hosted mode for now.
- The app is currently unauthenticated for this single-user MVP; keep the
  hosted URL private until proper authentication is added.

## Important Files

- `README.MD` - main setup, run, feature, and hosting overview.
- `docs/aws-always-free-serverless.md` - AWS deployment and operations guide.
- `docs/roadmap.md` - wishlist and next development priorities.
- `deploy/aws/template.yaml` - AWS SAM template.
- `app/aws_lambda.py` - Lambda handler for HTTP and scheduled events.
- `app/services/brief_generator.py` - daily note, news, sports, and finance brief logic.
- `app/services/email_delivery.py` - email rendering and SMTP delivery.
- `app/services/preferences.py` - local/AWS preference storage.
- `app/services/schedule_store.py` - scheduler proposal persistence.
- `app/static/index.html`, `app/static/app.js`, `app/static/styles.css` - single-page UI.

## Recent Changes Completed

- Added LLM-backed daily note with quote and reflection.
- Split finance brief into:
  - financial news and macro trends
  - companies, stocks, and ETFs to watch
- Added finance topic preferences, such as interest rates, Bank of Canada,
  inflation, housing, bond yields, global economy, employment, and currency.
- Shifted default finance examples toward ETFs:
  - `XEQT.TO`, `VEQT.TO`, `VFV.TO`, `XIC.TO`, `ZAG.TO`, `CASH.TO`, `VTI`, `VOO`, `VT`
- Added source-health notices for RSS/article/LLM fallback issues.
- Added brief history UI.
- Improved scheduler proposal UI.
- Added per-slot scheduler confirmation, so a user can confirm one suggested time
  instead of all proposed times.
- Added finance LLM cleanup so markdown output like `**Morning Brief** 1. **What is happening:**`
  is stripped before being shown in the UI.
- Removed the GitHub Actions morning email path from the active production plan.
  AWS EventBridge Scheduler is the production scheduler.
- Removed the temporary shared app access token gate.

## Verification Status

Latest local checks completed successfully:

```powershell
node --check app/static/app.js
conda run -n ai_ast python -m pytest -q
```

The full test suite passed with:

```text
74 passed
```

The most recent finance markdown cleanup was tested locally, but the hosted AWS
app still needs to be redeployed after that change.

## AWS Login

From WSL:

```bash
aws sso login --profile ai-assistant
```

If browser login does not work from WSL:

```bash
aws sso login --profile ai-assistant --use-device-code
```

Verify:

```bash
aws sts get-caller-identity --profile ai-assistant
```

## Redeploy Commands

Run from WSL in the repo root:

```bash
cd /mnt/c/Users/Tolu/Documents/vs_code/ai_assistant
sam build --template-file deploy/aws/template.yaml
sam deploy --resolve-s3 --no-confirm-changeset --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --profile ai-assistant --region us-east-2 --stack-name personal-ai-assistant --template-file .aws-sam/build/template.yaml
```

To keep hosted LLM features enabled:

```bash
sam deploy --resolve-s3 --no-confirm-changeset --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --profile ai-assistant --region us-east-2 --stack-name personal-ai-assistant --template-file .aws-sam/build/template.yaml --parameter-overrides ModelProvider=mistral NewsSummaryProvider=llm FinanceIntelligenceProvider=llm DailyNoteProvider=llm DailyQuoteEnabled=true
```

Secrets should stay in SSM Parameter Store and should not be passed in deploy
commands.

## Hosted Smoke Test Checklist

After redeploying:

- Open the hosted Lambda Function URL and refresh the UI.
- Check `/status`.
- Check `/llm/status?check=true`.
- Check `/brief/morning?save=false`.
- Confirm the finance summary no longer shows raw markdown or numbered headings.
- Save preferences in the hosted UI and refresh to confirm DynamoDB persistence.
- Test scheduler proposal, revise, and confirm.
- Optionally invoke the scheduled email manually and confirm inbox delivery.

## Known Design Decisions

- Keep the app single-user for now.
- Keep the hosted URL private until proper auth is implemented.
- Keep hosted calendar mode as `mock` until Google Calendar OAuth is redesigned
  for hosted serverless use.
- Keep finance content as education and monitoring context, not financial advice.
- Use free or low-cost services first.
- Avoid adding a second production scheduler, because duplicate schedulers caused
  duplicate morning emails before.

## Next Major Focus

The next phase should focus on Android and read-aloud support:

1. Make the current hosted UI a better mobile/PWA experience.
2. Add a web app manifest, icons, theme color, and installable Android home-screen support.
3. Add read-aloud controls for the morning brief using browser/device text-to-speech first.
4. Create a spoken-friendly version of the brief so links, headings, and repeated labels
   do not sound awkward.
5. Later, package the PWA as an Android app using a free/open-source path such as
   Trusted Web Activity or Capacitor.

Suggested opening prompt for the next chat:

```text
Read README.MD, docs/aws-always-free-serverless.md, docs/roadmap.md, and
docs/next-chat-handoff.md. Inspect the repo before changing code. I want to
start the next phase: Android/PWA support and read-aloud morning briefs.
```
