# ADDS AI Terminal (Serial TTY Chat Appliance)

This project turns a vintage RS-232 text terminal (e.g., ADDS 4000/260) into a modern AI chat console.

![Terminal Example (hotlink)](https://i.ebayimg.com/images/g/R3MAAOSwi0lg03aS/s-l1600.webp)

It is built to be:
- **Faithful to real serial terminals**: the app renders to a TTY device (PTY in dev; `/dev/ttyUSB0` on the Pi).
- **Deployable as an appliance**: runs on a Raspberry Pi, outputs directly to the terminal over RS-232.
- **Open-source friendly**: minimal dependencies, deterministic UI, and clean separation of UI vs. LLM backend.

## What this is actually for

Most “AI chat” UIs assume a modern terminal emulator with full Unicode and fast redraw. Vintage terminals are different:
- limited character sets
- limited ANSI features
- serial latency and flow control
- strict 80×24 ergonomics

This project is a reference implementation for building **LLM-powered, text-mode applications** that run on real serial terminals.

## Key features

- **ANSI/VT-style full-screen UI** designed for 80×24 terminals
- **System prompt** support (global behavior and safety rules)
- **Prompt presets** (switch personas/tasks quickly)
- **Basic keyword retrieval** (local blurbs injected into the prompt)
  - Example: query includes “James LePage” → inject stored blurb about James
- **OpenAI Responses API** streaming (fast, modern API surface)

## Hardware target

- Raspberry Pi host (any Pi that can run Linux + Python)
- RS-232 link to the terminal (USB-serial FTDI strongly preferred)
- Terminal: ADDS 4000/260 or similar RS-232 “green screen” terminal

The terminal is the display. The Pi is the host.

## How it runs

- **Local simulation (macOS)**: PTY pair + `screen` to mimic serial behavior.
- **Real hardware (Pi + terminal)**: Same app targeting `/dev/ttyUSB0`; Pi talks RS-232 to the ADDS.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
export OPENAI_API_KEY=...  # set your key
./scripts/run_dev.sh       # spins PTY pair + screen + app
```

Deploy to Pi (USB serial on `/dev/ttyUSB0`):

```bash
PI_HOST=raspberrypi.local ./scripts/deploy_pi.sh
ssh -t pi@"$PI_HOST" 'cd /opt/adds-ai && . .venv/bin/activate && \
  OPENAI_API_KEY=... ADDS_COLS=80 ADDS_ROWS=24 python -m adds_ai.app --tty /dev/ttyUSB0'
```

For appliance mode, add `/etc/adds-ai.env` and enable `systemd/adds-ai.service`. See docs below.

## Docs

- Faithful serial dev loop: `docs/serial-dev.md`
- Pi deployment and systemd: `docs/pi-deploy.md`
- Terminal notes: `docs/adds-terminal.md`
- Prompt/preset/retrieval data: `data/` folder (`system_prompt.txt`, `presets.yaml`, `kb.yaml`)

## License

MIT License.
