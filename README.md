# adds-ai-terminal

Terminal-first AI chat appliance that talks over a real TTY device. Develop locally against a PTY pair on macOS, then deploy unchanged to a Raspberry Pi driving an ADDS 4000/260 over USB-to-DB25.

## Quick start (macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
export OPENAI_API_KEY=sk-...
./scripts/run_dev.sh
```

The script spins up a PTY pair, launches `screen` on the monitor side, and runs the app on the other. Exit screen with `Ctrl-A` then `k`.

## Run manually

```bash
./scripts/pty_pair.sh
APP_TTY=$(sed -n '1p' /tmp/adds_ai_ptys.txt)
python -m adds_ai.app --tty "$APP_TTY"
```

## Deploy to Raspberry Pi

```bash
PI_HOST=raspberrypi.local ./scripts/deploy_pi.sh
ssh -t pi@"$PI_HOST" 'cd /opt/adds-ai && . .venv/bin/activate && ADDS_COLS=80 ADDS_ROWS=24 OPENAI_API_KEY=... python -m adds_ai.app --tty /dev/ttyUSB0'
```

See `docs/serial-dev.md` and `docs/pi-deploy.md` for details and `systemd/adds-ai.service` for appliance mode.
