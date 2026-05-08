#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-aiassistant}"
APP_DIR="${APP_DIR:-/opt/ai-assistant}"
SERVICE_NAME="${SERVICE_NAME:-ai-assistant}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 2
fi

sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
systemctl restart "${SERVICE_NAME}.service"
systemctl status "${SERVICE_NAME}.service" --no-pager
