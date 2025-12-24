#!/usr/bin/env bash
set -euo pipefail

./scripts/pty_pair.sh >/dev/null
APP_TTY="$(sed -n '1p' /tmp/adds_ai_ptys.txt)"
MON_TTY="$(sed -n '2p' /tmp/adds_ai_ptys.txt)"
SOCAT_PID_FILE="/tmp/adds_ai_socat.pid"

echo "App TTY: $APP_TTY"
echo "Monitor TTY: $MON_TTY"
echo "Launching monitor (screen). Exit screen with Ctrl-A then k."

cleanup() {
  if [[ -n "${SCREEN_PID:-}" ]]; then
    kill "$SCREEN_PID" 2>/dev/null || true
  fi
  if [[ -f "$SOCAT_PID_FILE" ]] && kill -0 "$(cat "$SOCAT_PID_FILE")" 2>/dev/null; then
    kill "$(cat "$SOCAT_PID_FILE")" 2>/dev/null || true
    rm -f "$SOCAT_PID_FILE"
  fi
}
trap cleanup EXIT

# Launch monitor
screen "$MON_TTY" 9600 &
SCREEN_PID=$!

# Run app against the other PTY
ADDS_COLS="${ADDS_COLS:-80}" ADDS_ROWS="${ADDS_ROWS:-24}" python -m adds_ai.app --tty "$APP_TTY"
