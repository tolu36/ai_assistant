# AWS Always-Free-Friendly Serverless Setup

This deployment avoids an EC2 VPS. It uses AWS services that fit a very small
personal app better:

- Lambda Function URL for the FastAPI UI/API
- DynamoDB for preferences, brief history, proposals, and scheduler feedback
- EventBridge Scheduler for the 9 AM America/Toronto email
- Gmail SMTP for email delivery
- Mistral or deterministic fallback for LLM behavior
- Systems Manager Parameter Store SecureString values for hosted secrets

This is "always-free-friendly" for 1-2 users because request volume and storage
should stay far below the always-free service limits. It is not fully AWS-only:
email still uses Gmail SMTP and optional LLM calls still use Mistral.

## Tradeoffs

Pros:

- No EC2 server to patch or keep running
- Dynamic preferences persist in DynamoDB
- The UI and scheduled job share the same stored state
- No API Gateway cost layer

Cons:

- Lambda cold starts can make the first request slower
- Local SQLite is replaced by DynamoDB in hosted mode
- Lambda Function URL is public, so the app uses an `APP_ACCESS_TOKEN`
- Hosted secrets must exist in SSM before the Lambda is deployed with
  `SECRETS_PROVIDER=ssm`
- Google Calendar OAuth is not configured for this serverless path yet; use
  `CALENDAR_PROVIDER=mock` unless you explicitly add hosted calendar secrets

## Local Prerequisites

Install:

- AWS CLI
- AWS SAM CLI
- Python 3.11
- Git
- GNU Make

On Windows, the smoothest path is usually WSL/Ubuntu because the SAM build uses
the repo `Makefile` to package only lightweight Lambda dependencies.

Then configure AWS credentials:

```powershell
aws configure
```

Use a region close to you, for example:

```text
us-east-2
```

## SSM Secrets

Create these SecureString parameters before deploying the SSM-backed template:

```bash
aws ssm put-parameter --name /personal-ai-assistant/prod/app_access_token --type SecureString --value "YOUR_APP_TOKEN" --overwrite --profile ai-assistant --region us-east-2
aws ssm put-parameter --name /personal-ai-assistant/prod/smtp_password --type SecureString --value "YOUR_GMAIL_APP_PASSWORD" --overwrite --profile ai-assistant --region us-east-2
aws ssm put-parameter --name /personal-ai-assistant/prod/mistral_api_key --type SecureString --value "YOUR_MISTRAL_API_KEY" --overwrite --profile ai-assistant --region us-east-2
```

Use standard SecureString parameters and the AWS-managed SSM key. Do not create
a customer-managed KMS key for this MVP.

## Deploy

From the repo root:

```powershell
sam build --template-file deploy/aws/template.yaml
sam deploy --guided --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND
```

When SAM prompts for parameters, use values like:

```text
Stack Name: personal-ai-assistant
AWS Region: us-east-2
AppName: personal-ai-assistant
SsmParameterPrefix: /personal-ai-assistant/prod
SmtpHost: smtp.gmail.com
SmtpPort: 587
SmtpUsername: your_email@gmail.com
MorningBriefFromEmail: your_email@gmail.com
MorningBriefToEmail: your_email@gmail.com
SportsInterests: NBA,NFL
SportsTeams: OKC Thunder,Toronto Raptors
FinanceWatchlist: XEQT.TO,VEQT.TO,VFV.TO,XIC.TO,ZAG.TO,CASH.TO,VTI,VOO,VT
NewsSummaryProvider: off
ModelProvider: fallback
ScheduleExpression: cron(0 9 * * ? *)
ScheduleTimezone: America/Toronto
```

SAM will output `AppUrl`. Open that URL in your browser.

The first API request will prompt for your app access token. Use the same value
stored in `/personal-ai-assistant/prod/app_access_token`.

## Test After Deployment

Open the app URL from the SAM output and update preferences in the UI.

Then test API access from PowerShell:

```powershell
$token = "YOUR_APP_ACCESS_TOKEN"
$url = "YOUR_LAMBDA_FUNCTION_URL"
curl.exe -H "X-App-Token: $token" "$url/preferences"
curl.exe -H "X-App-Token: $token" "$url/brief/morning"
curl.exe -H "X-App-Token: $token" "$url/status"
```

The morning email schedule is created by `deploy/aws/template.yaml` and runs at
9 AM America/Toronto. It retries failed runs at most 3 times within one hour.

Keep this as the only active production schedule. Do not add another scheduled
runner for `scripts/send_morning_brief.py`, or the app can send duplicate
emails from separate runtimes with different configuration and preferences.

## Updating The App

After code changes:

```powershell
sam build --template-file deploy/aws/template.yaml
sam deploy --resolve-s3 --no-confirm-changeset --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --profile ai-assistant --region us-east-2 --stack-name personal-ai-assistant --template-file .aws-sam/build/template.yaml
```

To enable Mistral-backed article summaries after the stack exists:

```powershell
sam deploy --resolve-s3 --no-confirm-changeset --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --profile ai-assistant --region us-east-2 --stack-name personal-ai-assistant --template-file .aws-sam/build/template.yaml --parameter-overrides ModelProvider=mistral NewsSummaryProvider=llm
```

Use `NewsSummaryProvider=auto` if you want the app to use LLM summaries only
when the configured model provider is enabled. Use `NewsSummaryProvider=off`
to return to RSS-provided summaries.

## Important Cost Controls

- Use `MODEL_PROVIDER=fallback` or `mistral`; do not package local
  Transformers/Torch into Lambda.
- Keep DynamoDB provisioned throughput at `1` read and `1` write capacity unit.
- Do not add API Gateway unless you want to learn it or need its features.
- Do not use RDS for this MVP.
- Keep `CALENDAR_PROVIDER=mock` until Google Calendar OAuth is redesigned for
  hosted serverless use.

## Files Added For AWS

- `app/aws_lambda.py` - Lambda handler for Function URL and scheduled events
- `deploy/aws/template.yaml` - SAM/CloudFormation resources
- `requirements-aws.txt` - lightweight Lambda dependencies
- `Makefile` - SAM build target that avoids packaging Torch/Transformers

## Official References

- AWS Free Tier: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html
- AWS Lambda quotas/free tier: https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- Lambda Function URLs: https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html
- DynamoDB provisioned capacity mode: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/provisioned-capacity-mode.html
- EventBridge Scheduler: https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html
- AWS SAM deploy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html
