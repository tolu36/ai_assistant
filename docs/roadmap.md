# Personal AI Assistant Roadmap

This file tracks improvement ideas beyond the current MVP. The README should
stay focused on setup, running, and deployment.

## MVP Status

- Hosted AWS Lambda app is live.
- DynamoDB persistence works for preferences, brief history, proposals, and scheduler feedback.
- SSM Parameter Store holds hosted secrets.
- Mistral TTS is enabled for prebuilt read-aloud audio.
- Cloudflare R2 stores prebuilt morning brief MP3 chunks for 7 days.
- EventBridge Scheduler prepares the morning brief and Mistral audio at 8:45 AM America/Toronto.
- EventBridge Scheduler sends an Android PWA Web Push notification at 9 AM America/Toronto only after audio is ready.
- Hosted scheduled email is disabled; Gmail SMTP remains available for manual/local sends.
- Permanent HTTPS hosting works through Lambda Function URL, and the Android PWA can be installed from that URL.
- Daily note is included with an LLM-generated positive quote and reflection prompt when an LLM is enabled.
- Finance brief now leads with broader market intelligence, ETF context, and macro impact notes.
- Read-aloud supports saved Mistral MP3 playback first, with live Mistral/browser fallback if needed.

## Next Priorities

### Morning Brief Quality

- Improve article summaries so each story has a concise, useful summary and a clickable read-more link.
- Track source health so broken or slow RSS feeds are visible in `/status`.
- Add duplicate detection so the same story is not repeated too often.
- Add follow-up Q&A for brief items, such as `POST /brief/story/{story_id}/ask`, grounded only in the article text and source link.
- Improve daily note personalization once the app has richer user preferences.

### Finance and Macro Brief

- Continue improving the broader domestic/global financial briefing.
- Cover macro topics that affect ETFs, housing, and long-term investing: interest rates, inflation, employment, GDP, central bank decisions, bond yields, currency moves, and housing/real estate trends.
- Include Canadian and global market context, not just US stock-market headlines.
- Surface companies, ETFs, sectors, and stocks worth monitoring, while clearly avoiding personalized investment advice or buy/sell recommendations.
- Expand ETF-first explanations with more source-grounded detail and better Canadian context.
- Keep improving how the user's ETF holdings/watchlist prioritize relevance without turning the section into personalized financial advice.

### Scheduler Intelligence

- Add real Google Calendar support in hosted AWS mode instead of mock calendar mode.
- Improve recurring task planning for requests like "study for 2 hours 5 days a week".
- Let the assistant propose a set of times, explain why it chose them, and wait for user approval.
- Store feedback as explicit scheduling preferences, such as sleep hours, work hours, preferred study windows, and blocked days.
- Let the user approve one slot, some slots, or all slots.
- Add conflict explanations when a proposed time is rejected.

### Sports Brief

- Improve sports source reliability beyond RSS where free APIs are available.
- Add league/team preference controls that feel first-class in the UI.
- Add scores, schedules, standings, injuries, and transaction/news updates.
- Improve team and nickname matching so abbreviations like OKC map to Oklahoma City Thunder.

### UI and User Experience

- Continue polishing the brief history view so past briefs can be searched, filtered, and reopened from the app.
- Continue improving scheduler proposal cards and confirmation flows.
- Add clearer error banners for auth, feed failures, audio failures, notification failures, and LLM fallback.
- Improve mobile layout and touch targets.
- Add a settings screen for preferences, source lists, schedule time, and status.

### Read Aloud and Voice Experience

- Improve spoken copy quality for Mistral-generated audio so finance tickers, acronyms, and source labels sound more natural.
- Add better progress indicators for section/chunk playback.
- Add skip-next and skip-previous controls for audio chunks or sections.
- Add voice/model configuration once Mistral exposes a stable set of preferred voices.
- Track Mistral TTS usage and failure rates so the app stays within the no-cost/low-cost target.

### Android App Path

- Keep polishing the installed PWA experience now that the hosted Lambda Function URL is permanent.
- Improve update handling so Android reliably picks up new app shell/service-worker versions without manual site-data clearing.
- Later, wrap the app as an Android package using a free/open-source path such as Trusted Web Activity or Capacitor.
- Add Android-specific polish such as share targets and local notification reminders.

### Notifications

- Add a dedicated settings screen for notification subscription status and re-enrollment.
- Add optional one-off test notification support behind settings/admin UI instead of the main page.
- Add CloudWatch alarms for failed morning notification runs.
- Add a fallback notification message if text brief generation succeeds but audio generation repeatedly fails.

### Reliability and Operations

- Add automated hosted smoke tests that can run after every deploy.
- Add CloudWatch alarm ideas for Lambda errors, failed scheduled notification sends, and failed audio prebuilds.
- Add AWS Budget setup instructions and periodic cost review steps.
- Add source health metrics for RSS and article fetch latency.
- Add SSM secret rotation notes.

## Later Ideas

- Multi-user support with separate profiles and preference records.
- Proper authentication before exposing the app to multiple users or a wider audience.
- Voice input for quick scheduling.
- SMS or WhatsApp notifications for selected alerts if a free/acceptable provider is found.
- Calendar-aware proactive suggestions for weekly planning.
- Personal knowledge memory for stable preferences, while keeping sensitive data minimal.
- User-configurable brief sections, ordering, notification timing, and audio length.
