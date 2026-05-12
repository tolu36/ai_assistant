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
- Daily note is included with an LLM-generated positive quote and reflection prompt when an LLM is enabled.
- Finance brief now leads with broader market intelligence, ETF context, and macro impact notes.

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

- Continue polishing the brief history view so past emails can be searched, filtered, and reopened from the app.
- Continue improving scheduler proposal cards and confirmation flows.
- Add clearer error banners for token/auth, feed failures, email failures, and LLM fallback.
- Improve mobile layout and touch targets.
- Add a settings screen for preferences, source lists, schedule time, and status.

### Read Aloud and Voice Experience

- Add a read-aloud control for the morning brief so the app can speak the daily note, news, sports, and finance sections.
- Start with browser/Android text-to-speech using the Web Speech API where available, keeping it free and local to the device.
- Add controls for play, pause, stop, section skipping, and reading speed.
- Create a cleaner spoken version of the brief so links, source labels, and repeated headings do not sound awkward.
- Later, evaluate higher-quality cloud TTS only if the free browser/device voice is not good enough.

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
