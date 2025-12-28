#!/usr/bin/env bash
set -euo pipefail
PI_HOST="${PI_HOST:-eis-pi.local}"
PI_USER="${PI_USER:-eis-pi}"
RSYNC_EXCLUDES="--exclude .venv --exclude __pycache__ --exclude .git"

rsync -av $RSYNC_EXCLUDES ./ "$PI_USER"@"$PI_HOST":/opt/adds-ai/
ssh "$PI_USER"@"$PI_HOST" '
  set -e
  cd /opt/adds-ai
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -U pip
  pip install openai pyyaml
'
echo "Deployed to $PI_HOST:/opt/adds-ai"
