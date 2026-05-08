# Free Hosting Notes

This MVP has two different hosting needs:

1. A scheduled daily job that sends the morning email.
2. An optional always-on server for the FastAPI UI.

For a static scheduled email, GitHub Actions is the easiest free default. It
can run the brief email script once per day without keeping a server online.

For dynamic app preferences, Oracle Cloud Always Free is the better free path.
It is a real VM option, but it requires an Oracle account and available capacity
in your home region. The setup guide is in `docs/oracle-vps-setup.md`.

## Recommended MVP Path

Use GitHub Actions only if you are comfortable editing preferences as GitHub
variables:

- It is free for public repositories and includes free minutes for private repos
  depending on your GitHub plan.
- It supports scheduled workflows with POSIX cron and timezone-aware scheduling.
- It stores SMTP credentials as repository secrets.
- It does not require a 24/7 server for a once-daily email.

Use Oracle Cloud Always Free when you want the FastAPI app running all day and
want preference changes from the UI to affect the next 9 AM email:

- Oracle documents Always Free compute VM instances.
- Oracle documents Ampere A1 Arm capacity equivalent to 4 OCPUs and 24 GB memory
  across Always Free A1 instances.
- Capacity can be unavailable in some regions, so GitHub Actions is still the
  lower-friction scheduled-job path.

Official references:

- GitHub Actions workflow syntax: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Actions billing and free usage: https://docs.github.com/en/actions/learn-github-actions/usage-limits-billing-and-administration
- Oracle Cloud Free Tier: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm
- Oracle Always Free resources: https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm

## GitHub Actions Setup

The workflow is in `.github/workflows/morning-brief-email.yml`.

Add these required repository secrets:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `MORNING_BRIEF_TO_EMAIL`

Optional repository secrets:

- `MORNING_BRIEF_FROM_EMAIL`
- `MORNING_BRIEF_SUBJECT_PREFIX`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`

Optional repository variables:

- `NEWS_RSS_FEEDS`
- `SPORTS_INTERESTS`
- `SPORTS_TEAMS`
- `FINANCE_WATCHLIST`
- `FINANCE_RSS_FEEDS`

The workflow runs at 9:00 AM in `America/Toronto` and can also be started
manually with `workflow_dispatch`. It validates SMTP settings before fetching
feeds so missing secrets fail quickly.

Before running the workflow, test the same SMTP values locally:

```powershell
conda run -n ai_ast python scripts/send_morning_brief.py --dry-run
conda run -n ai_ast python scripts/send_morning_brief.py
```

If the real send reports that the sender is missing, set either
`MORNING_BRIEF_FROM_EMAIL` or `SMTP_USERNAME`.

## Oracle Cloud Always Free VPS Setup

High-level deployment path:

1. Create an Oracle Cloud Free Tier account.
2. Create an Always Free compute VM in your home region.
3. Use Ubuntu, open inbound port `8000` only if you need remote UI access, and
   keep SSH restricted.
4. Install Python and clone this repo.
5. Create a virtual environment and install `requirements.txt`.
6. Put secrets in a server-only `.env` file.
7. Run the app with `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
8. Add a server cron job for the email script:

```bash
0 9 * * * cd /path/to/ai_assistant && /path/to/python scripts/send_morning_brief.py
```

For this MVP, use Oracle Cloud Always Free if you want dynamic preferences
without adding a separate hosted database.
