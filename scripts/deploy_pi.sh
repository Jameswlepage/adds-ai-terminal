#!/usr/bin/env bash
set -euo pipefail
PI_HOST="${PI_HOST:-raspberrypi.local}"
RSYNC_EXCLUDES="--exclude .venv --exclude __pycache__ --exclude .git"

rsync -av $RSYNC_EXCLUDES ./ pi@"$PI_HOST":/opt/adds-ai/
ssh pi@"$PI_HOST" '
  set -e
  cd /opt/adds-ai
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -U pip
  pip install openai
'
echo "Deployed to $PI_HOST:/opt/adds-ai"
