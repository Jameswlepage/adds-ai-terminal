# Serial-first dev (macOS)

Goal: run the app attached to a real TTY device via a PTY pair so you catch CR/LF, redraw, and latency issues.

## Prereqs

- `socat` and `screen` installed (macOS: `brew install socat screen`)
- Python 3.10+, `openai` lib, `OPENAI_API_KEY` exported

## Spin up PTY pair

```bash
./scripts/pty_pair.sh
cat /tmp/adds_ai_ptys.txt
# line 1: app end
# line 2: monitor end (open with screen)
```

## Full dev loop

```bash
source .venv/bin/activate
export OPENAI_API_KEY=...
./scripts/run_dev.sh
```

`screen` attaches to the monitor end of the PTY; exit with `Ctrl-A` then `k`. The app writes to the other PTY, reading raw bytes—no cooked input from your Terminal.

## Manual run

```bash
APP_TTY=$(sed -n '1p' /tmp/adds_ai_ptys.txt)
ADDS_COLS=80 ADDS_ROWS=24 python -m adds_ai.app --tty "$APP_TTY"
```

## Troubleshooting

- Stair-stepping lines: force CR+LF on any manual prints; the UI mostly uses cursor addressing.
- Flicker: increase `ADDS_REFRESH_MS` or pass `--refresh-ms 150`.
- Garbled header: ensure terminal/`screen` window is 80×24; ANSI/VT100 mode on the real terminal.
- Stuck streaming: some serial adapters want RTS/CTS disabled; toggle flow control.
