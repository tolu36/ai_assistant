#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-aiassistant}"
APP_DIR="${APP_DIR:-/opt/ai-assistant}"
REPO_URL="${REPO_URL:-}"
SERVICE_NAME="${SERVICE_NAME:-ai-assistant}"
APP_PORT="${APP_PORT:-8000}"

if [[ -z "$REPO_URL" && ! -d "$APP_DIR/.git" ]]; then
  echo "Set REPO_URL to your GitHub repo URL before running this script." >&2
  echo "Example: REPO_URL=https://github.com/your-user/ai_assistant.git sudo -E bash deploy/oracle/bootstrap_ubuntu.sh" >&2
  exit 2
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 2
fi

apt-get update
apt-get install -y \
  ca-certificates \
  cron \
  curl \
  git \
  python3 \
  python3-pip \
  python3-venv

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "$APP_USER"
fi

mkdir -p "$APP_DIR" /var/log/ai-assistant
chown -R "$APP_USER:$APP_USER" "$APP_DIR" /var/log/ai-assistant

if [[ -d "$APP_DIR/.git" ]]; then
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
else
  sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
fi

sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Created $APP_DIR/.env from .env.example. Edit it before starting the service."
fi

cat >/etc/systemd/system/${SERVICE_NAME}.service <<SERVICE
[Unit]
Description=Personal AI Assistant FastAPI app
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${APP_DIR}/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

cat >/etc/cron.d/ai-assistant-morning-brief <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
CRON_TZ=America/Toronto
0 9 * * * ${APP_USER} cd ${APP_DIR} && ${APP_DIR}/.venv/bin/python scripts/send_morning_brief.py >> /var/log/ai-assistant/morning-brief.log 2>&1
CRON

chmod 644 /etc/cron.d/ai-assistant-morning-brief
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

echo "Bootstrap complete."
echo "Next:"
echo "1. Edit $APP_DIR/.env with your real SMTP, Mistral, sports, and finance values."
echo "2. Run: sudo systemctl start ${SERVICE_NAME}"
echo "3. Run: sudo -u ${APP_USER} bash -lc 'cd ${APP_DIR} && .venv/bin/python scripts/send_morning_brief.py --dry-run'"
