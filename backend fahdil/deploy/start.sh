#!/usr/bin/env bash
# Runs the API the same way whether started by hand or by PM2.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."   # backend/ (this file lives in backend/deploy/)

if [ ! -x ".venv/bin/python3" ]; then
  echo "deploy/start.sh: .venv not found — run update.sh first." >&2
  exit 1
fi

exec .venv/bin/python3 wsgi.py
