# Personal AI Assistant Roadmap

This file tracks improvement ideas beyond the current MVP. The README should
stay focused on setup, running, and deployment.

## MVP Status

- Hosted AWS Lambda app is live.
- DynamoDB persistence works for preferences, brief history, proposals, and scheduler feedback.
- SSM Parameter Store holds hosted secrets.
- Mistral is enabled for LLM-backed behavior.
- EventBridge Scheduler sends the morning brief at 9 AM America/Toronto.
- Gmail SMTP email delivery has been verified end to end.

## Next Priorities

### Morning Brief Quality

- Improve article summaries so each story has a concise, useful summary and a clickable read-more link.
- Track source health so broken or slow RSS feeds are visible in `/status`.
- Add duplicate detection so the same story is not repeated too often.
- Add follow-up Q&A for brief items, such as `POST /brief/story/{story_id}/ask`, grounded only in the article text and source link.
- Add a short gratitude or positive quote of the day to start the brief.

### Finance and Macro Brief

- Shift finance away from only "my watchlist" and toward a broader domestic/global financial briefing.
- Cover macro topics that affect ETFs, housing, and long-term investing: interest rates, inflation, employment, GDP, central bank decisions, bond yields, currency moves, and housing/real estate trends.
- Include Canadian and global market context, not just US stock-market headlines.
- Surface companies, ETFs, sectors, and stocks worth monitoring, while clearly avoiding personalized investment advice or buy/sell recommendations.
- Add ETF-first explanations like "why this matters to broad equity ETFs", "why this matters to bond ETFs", and "why this matters to housing/mortgage costs".
- Keep the user's ETF holdings/watchlist as a personalization input, but use it to prioritize relevance rather than limiting the finance section.

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

- Add a brief history view so past emails can be reviewed from the app.
- Improve scheduler proposal cards and confirmation flows.
- Add clearer error banners for token/auth, feed failures, email failures, and LLM fallback.
- Improve mobile layout and touch targets.
- Add a settings screen for preferences, source lists, schedule time, and status.

### Android App Path

- Start with a mobile-friendly progressive web app (PWA) so the current hosted UI can be added to an Android home screen.
- Add a web app manifest, app icons, theme colors, and basic offline shell support.
- Later, wrap the app as an Android package using a free/open-source path such as Trusted Web Activity or Capacitor.
- Add Android-specific polish only after the web app is stable: push notifications, share targets, and local notification reminders.

### Reliability and Operations

- Add automated hosted smoke tests that can run after every deploy.
- Add CloudWatch alarm ideas for Lambda errors and failed scheduled email sends.
- Add AWS Budget setup instructions and periodic cost review steps.
- Add source health metrics for RSS and article fetch latency.
- Add SSM secret rotation notes.

## Later Ideas

- Multi-user support with separate profiles and preference records.
- Stronger authentication than a shared app token.
- Voice input for quick scheduling.
- SMS, WhatsApp, or push notifications for selected alerts.
- Calendar-aware proactive suggestions for weekly planning.
- Personal knowledge memory for stable preferences, while keeping sensitive data minimal.
- User-configurable brief sections, ordering, and email length.
