#!/usr/bin/env bash
set -euo pipefail

# Creates a connected PTY pair and prints their device paths.
# One end is for the app, the other end is for "screen" (your simulated monitor).
socat -d -d pty,raw,echo=0,icanon=0 pty,raw,echo=0,icanon=0 2>&1 \
  | awk '/PTY is/ {print $NF}' \
  | tee /tmp/adds_ai_ptys.txt

echo
echo "PTYs saved to /tmp/adds_ai_ptys.txt"
echo "First line: app end; second line: monitor end (screen)."
