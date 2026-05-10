# Oracle Cloud Always Free VPS Setup

This is the recommended setup when preferences should be dynamic. The FastAPI
app, SQLite databases, and 9 AM email job all run on the same free VPS, so the
UI can update preferences and the next morning email will use those preferences.

## Why VPS

The Oracle VPS path is useful when you want a traditional always-on Linux
server instead of AWS serverless. The app, SQLite data, and cron job all live
on the same machine.

The Oracle VPS keeps:

- `data/preferences.db`
- `data/brief_history.db`
- `data/scheduler.db`
- `.env`

That means you can change sports teams, finance watchlists, and other settings
through the app UI, and the scheduled email will use the same local data.

## Oracle Resources To Create

Create one Always Free VM:

- Image: Ubuntu
- Shape: `VM.Standard.A1.Flex` if available
- Size: 1 OCPU and 6 GB memory is enough for this MVP
- Boot volume: default 50 GB
- Public IPv4: enabled
- SSH key: use your local public key

Oracle documents that Always Free compute must be created in your home region.
It also documents that the A1 Always Free allocation is equivalent to 4 OCPUs
and 24 GB memory total across A1 instances.

## Network Rules

Keep SSH restricted to your IP where possible.

Open these inbound ports only if needed:

- `22/tcp` for SSH
- `8000/tcp` for the FastAPI UI while testing

For production-style access later, put Nginx/Caddy in front of the app and open
only `80/tcp` and `443/tcp`.

## Local Prep

Make sure your code is pushed to GitHub. Do not commit `.env`, `data/`,
`credentials/`, or token files.

On Windows, generate an SSH key if you do not already have one:

```powershell
ssh-keygen -t ed25519 -C "oracle-ai-assistant"
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

Paste the public key into Oracle when creating the instance.

## First SSH Login

After the VM is running:

```powershell
ssh ubuntu@YOUR_ORACLE_PUBLIC_IP
```

If your image uses a different username, Oracle will show it on the instance
details page.

## Bootstrap The App

On the VM:

```bash
git clone https://github.com/YOUR_GITHUB_USER/YOUR_REPO.git /tmp/ai_assistant
cd /tmp/ai_assistant
sudo REPO_URL=https://github.com/YOUR_GITHUB_USER/YOUR_REPO.git bash deploy/oracle/bootstrap_ubuntu.sh
```

The bootstrap script:

- installs Python, Git, cron, and venv support
- creates an `aiassistant` Linux user
- clones or updates the app at `/opt/ai-assistant`
- creates a Python virtual environment
- installs `requirements.txt`
- creates a systemd service named `ai-assistant`
- creates a cron job for 9 AM America/Toronto

## Copy Secrets

Do not put real secrets in GitHub. Put them in `/opt/ai-assistant/.env` on the
VPS.

From your local machine, copy your local `.env` to the VPS:

```powershell
scp .env ubuntu@YOUR_ORACLE_PUBLIC_IP:/tmp/ai-assistant.env
ssh ubuntu@YOUR_ORACLE_PUBLIC_IP
sudo mv /tmp/ai-assistant.env /opt/ai-assistant/.env
sudo chown aiassistant:aiassistant /opt/ai-assistant/.env
sudo chmod 600 /opt/ai-assistant/.env
```

## Test On The VPS

```bash
sudo -u aiassistant bash -lc 'cd /opt/ai-assistant && .venv/bin/python scripts/send_morning_brief.py --check-email-config'
sudo -u aiassistant bash -lc 'cd /opt/ai-assistant && .venv/bin/python scripts/send_morning_brief.py --dry-run'
sudo -u aiassistant bash -lc 'cd /opt/ai-assistant && .venv/bin/python scripts/send_morning_brief.py'
```

Then start the app:

```bash
sudo systemctl start ai-assistant
sudo systemctl status ai-assistant --no-pager
```

Open:

```text
http://YOUR_ORACLE_PUBLIC_IP:8000/
```

## Check The Morning Email Job

The cron job is installed at:

```text
/etc/cron.d/ai-assistant-morning-brief
```

Logs go to:

```text
/var/log/ai-assistant/morning-brief.log
```

Check logs:

```bash
sudo tail -100 /var/log/ai-assistant/morning-brief.log
```

## Updating The App

After pushing code changes to GitHub, SSH into the VPS and run:

```bash
cd /opt/ai-assistant
sudo bash deploy/oracle/update_app.sh
```

## Security Notes

- Keep `.env` off GitHub.
- Restrict SSH ingress to your IP if possible.
- Do not expose port `8000` permanently if you do not need remote UI access.
- Back up `/opt/ai-assistant/data/` periodically.
- If the Oracle console reports "out of host capacity," try another availability
  domain or wait and retry.

## Official References

- Oracle Free Tier: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm
- Oracle Always Free resources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Oracle instance creation: https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm
- Oracle security lists: https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm
