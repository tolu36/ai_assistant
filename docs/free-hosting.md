# Free Hosting Notes

This MVP has two different hosting needs:

1. A scheduled daily job that sends the morning email.
2. An optional always-on server for the FastAPI UI.

For dynamic app preferences on AWS, use the serverless path in
`docs/aws-always-free-serverless.md`. It uses Lambda Function URLs, DynamoDB,
and EventBridge Scheduler instead of an EC2 VPS.

Oracle Cloud Always Free is still the better free path if you specifically want
a traditional VPS. It is a real VM option, but it requires an Oracle account
and available capacity in your home region. The setup guide is in
`docs/oracle-vps-setup.md`.

## Recommended MVP Path

Use AWS serverless when you want dynamic preferences without a server:

- Lambda Function URLs serve the FastAPI app without API Gateway.
- DynamoDB stores preferences and brief history.
- EventBridge Scheduler invokes the morning email at 9 AM America/Toronto.
- Gmail SMTP still sends the email.

Use Oracle Cloud Always Free when you want the FastAPI app running all day and
want a traditional Linux server:

- Oracle documents Always Free compute VM instances.
- Oracle documents Ampere A1 Arm capacity equivalent to 4 OCPUs and 24 GB memory
  across Always Free A1 instances.
- Capacity can be unavailable in some regions.

Official references:

- Oracle Cloud Free Tier: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm
- Oracle Always Free resources: https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm

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

For this MVP, use AWS serverless if the goal is to learn AWS always-free-style
services. Use Oracle Cloud Always Free if the goal is to learn VPS operations.
