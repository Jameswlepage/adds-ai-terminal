#!/usr/bin/env bash
set -euo pipefail

./scripts/pty_pair.sh >/dev/null
APP_TTY="$(sed -n '1p' /tmp/adds_ai_ptys.txt)"
MON_TTY="$(sed -n '2p' /tmp/adds_ai_ptys.txt)"

echo "App TTY: $APP_TTY"
echo "Monitor TTY: $MON_TTY"
echo "Launching monitor (screen). Exit screen with Ctrl-A then k."

# Launch monitor
screen "$MON_TTY" 9600 &
SCREEN_PID=$!

# Run app against the other PTY
ADDS_COLS="${ADDS_COLS:-80}" ADDS_ROWS="${ADDS_ROWS:-24}" python -m adds_ai.app --tty "$APP_TTY"

kill "$SCREEN_PID" 2>/dev/null || true
