# AWS Always-Free-Friendly Serverless Setup

This deployment avoids an EC2 VPS. It uses AWS services that fit a very small
personal app better:

- Lambda Function URL for the FastAPI UI/API
- DynamoDB for preferences, brief history, proposals, and scheduler feedback
- Cloudflare R2 for generated morning brief MP3 chunks
- EventBridge Scheduler for a pre-9 AM preparation run and the 9 AM America/Toronto email/notification run
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
- Lambda Function URL is public; this single-user MVP currently has no app-level
  authentication, so keep the URL private until proper authentication is added
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
aws ssm put-parameter --name /personal-ai-assistant/prod/smtp_password --type SecureString --value "YOUR_GMAIL_APP_PASSWORD" --overwrite --profile ai-assistant --region us-east-2
aws ssm put-parameter --name /personal-ai-assistant/prod/mistral_api_key --type SecureString --value "YOUR_MISTRAL_API_KEY" --overwrite --profile ai-assistant --region us-east-2
aws ssm put-parameter --name /personal-ai-assistant/prod/app_access_token --type SecureString --value "YOUR_APP_ACCESS_TOKEN" --overwrite --profile ai-assistant --region us-east-2
aws ssm put-parameter --name /personal-ai-assistant/prod/brief_audio_object_access_key_id --type SecureString --value "YOUR_R2_ACCESS_KEY_ID" --overwrite --profile ai-assistant --region us-east-2
aws ssm put-parameter --name /personal-ai-assistant/prod/brief_audio_object_secret_access_key --type SecureString --value "YOUR_R2_SECRET_ACCESS_KEY" --overwrite --profile ai-assistant --region us-east-2
```

Use standard SecureString parameters and the AWS-managed SSM key. Do not create
a customer-managed KMS key for this MVP.

## Cloudflare R2 Audio Storage

Create one R2 bucket in Cloudflare for generated MP3 chunks. Generate an R2 API
token with Object Read & Write permission scoped to that bucket. Use the S3 API
endpoint from the R2 dashboard:

```text
https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
```

Set an R2 lifecycle rule for the `brief-audio/` prefix that deletes objects
after 7 days. This mirrors `BriefAudioRetentionDays` and keeps the audio cache
inside the free tier target.

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
FinanceTopics: interest rates,Bank of Canada,inflation,housing,bond yields,global economy,employment,currency
FinanceWatchlist: XEQT.TO,VEQT.TO,VFV.TO,XIC.TO,ZAG.TO,CASH.TO,VTI,VOO,VT
NewsSummaryProvider: off
FinanceIntelligenceProvider: auto
DailyQuoteEnabled: true
DailyNoteProvider: auto
ModelProvider: fallback
PipelineScheduleExpression: cron(45 8 * * ? *)
ScheduleExpression: cron(0 9 * * ? *)
ScheduleTimezone: America/Toronto
BriefAudioRetentionDays: 7
CloudflareR2BucketName: your-r2-bucket-name
CloudflareR2EndpointUrl: https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
BriefAudioObjectPrefix: brief-audio
```

SAM will output `AppUrl`. Open that URL in your browser. The current MVP does
not prompt for an app access token.

## Test After Deployment

Open the app URL from the SAM output and update preferences in the UI.

Then test API access from PowerShell:

```powershell
$url = "YOUR_LAMBDA_FUNCTION_URL"
curl.exe "$url/preferences"
curl.exe "$url/brief/morning"
curl.exe "$url/status"
```

The morning pipeline schedules are created by `deploy/aws/template.yaml`. The
preparation run starts at 8:45 AM America/Toronto so brief audio can be ready
before 9 AM. The email/notification run stays at 9 AM America/Toronto. Each
schedule retries failed runs at most 3 times within one hour.

Keep this as the only active production schedule. Do not add another scheduled
runner for `scripts/send_morning_brief.py`, or the app can send duplicate
emails from separate runtimes with different configuration and preferences.

## Updating The App

After code changes:

```powershell
sam build --template-file deploy/aws/template.yaml
sam deploy --resolve-s3 --no-confirm-changeset --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --profile ai-assistant --region us-east-2 --stack-name personal-ai-assistant --template-file .aws-sam/build/template.yaml
```

To enable Mistral-backed article summaries, finance intelligence, and daily
notes after the stack exists:

```powershell
sam deploy --resolve-s3 --no-confirm-changeset --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --profile ai-assistant --region us-east-2 --stack-name personal-ai-assistant --template-file .aws-sam/build/template.yaml --parameter-overrides ModelProvider=mistral NewsSummaryProvider=llm FinanceIntelligenceProvider=llm DailyNoteProvider=llm DailyQuoteEnabled=true
```

Use `NewsSummaryProvider=auto` if you want the app to use LLM summaries only
when the configured model provider is enabled. Use `NewsSummaryProvider=off`
to return to RSS-provided summaries. The same pattern applies to
`FinanceIntelligenceProvider` and `DailyNoteProvider`: use `auto` for LLM when
available, `llm` to force an LLM attempt, and `off` for deterministic fallback.

## Important Cost Controls

- Use `MODEL_PROVIDER=fallback` or `mistral`; do not package local
  Transformers/Torch into Lambda.
- Keep DynamoDB provisioned throughput at `1` read and `1` write capacity unit.
- Keep generated audio in Cloudflare R2 Standard storage and set a lifecycle
  rule to delete the `brief-audio/` prefix after 7 days. The app also deletes
  R2 objects older than `BriefAudioRetentionDays` during audio generation.
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
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Cloudflare R2 S3 API: https://developers.cloudflare.com/r2/api/s3/
- Cloudflare R2 object lifecycles: https://developers.cloudflare.com/r2/buckets/object-lifecycles/
- Lambda Function URLs: https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html
- DynamoDB provisioned capacity mode: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/provisioned-capacity-mode.html
- EventBridge Scheduler: https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html
- AWS SAM deploy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html
