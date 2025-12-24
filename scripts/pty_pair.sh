#!/usr/bin/env bash
set -euo pipefail

# Creates a connected PTY pair and prints their device paths.
# One end is for the app, the other end is for "screen" (your simulated monitor).

PTYS_FILE="/tmp/adds_ai_ptys.txt"
PID_FILE="/tmp/adds_ai_socat.pid"
LOG_FILE="/tmp/adds_ai_socat.log"

# Clean up any stale socat
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  kill "$(cat "$PID_FILE")" || true
fi
rm -f "$PID_FILE" "$PTYS_FILE" "$LOG_FILE"

# Start socat in the background
socat -d -d pty,raw,echo=0,icanon=0 pty,raw,echo=0,icanon=0 2> "$LOG_FILE" &
SOCAT_PID=$!
echo "$SOCAT_PID" > "$PID_FILE"

# Wait for PTY lines to appear
for _ in {1..50}; do
  if grep -q "PTY is" "$LOG_FILE"; then
    break
  fi
  sleep 0.1
done

grep "PTY is" "$LOG_FILE" | awk '{print $NF}' > "$PTYS_FILE"
cat "$PTYS_FILE"
echo
echo "PTYs saved to $PTYS_FILE (app end first, monitor end second)."
echo "socat pid: $SOCAT_PID"
