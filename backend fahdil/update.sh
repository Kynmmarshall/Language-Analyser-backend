#!/usr/bin/env bash
# Pulls the latest backend code, syncs the virtualenv, and (re)starts the API under
# PM2. Safe to run repeatedly — first run creates what's missing, later runs just sync
# and restart.
#
# Usage on the VPS:
#   cd /path/to/yo-b/backend
#   ./update.sh
#
# One-time setup before the first run:
#   sudo apt install python3 python3-venv
#   npm install -g pm2
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PM2_APP_NAME="yo-b-backend"

echo "==> [1/5] Pulling latest code"
if [ -d .git ]; then
  git pull --ff-only
else
  echo "    (not a git checkout — skipping pull; deploy your files here manually)"
fi

echo "==> [2/5] Ensuring the virtualenv exists (.venv)"
if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi

echo "==> [3/5] Installing/updating dependencies"
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet

echo "==> [4/5] Making scripts executable and preparing log directory"
chmod +x deploy/start.sh
mkdir -p deploy/logs

echo "==> [5/5] (Re)starting the PM2 process: $PM2_APP_NAME"
if pm2 describe "$PM2_APP_NAME" > /dev/null 2>&1; then
  pm2 restart "$PM2_APP_NAME" --update-env
else
  pm2 start deploy/ecosystem.config.js
fi
pm2 save

echo "==> Done. Check status with: pm2 status $PM2_APP_NAME"
echo "==> Tail logs with:          pm2 logs $PM2_APP_NAME"
