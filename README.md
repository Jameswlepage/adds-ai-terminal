# ADDS AI Terminal (Serial TTY Chat Appliance)

This project turns a vintage RS-232 text terminal (e.g., ADDS 4000/260) into a modern AI chat console.

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

## Dev modes

### Mode A: Local faithful simulation (no Pi, no terminal)
Uses a PTY pair to simulate a serial link end-to-end.

```

adds-ai (writes to PTY A) <—pty—> screen (reads PTY B)

```

This catches the real problems early:
- CR/LF behavior
- redraw flicker and pacing
- 80×24 wrapping
- raw TTY input behavior

### Mode B: Deploy to Pi + real terminal
Exact same app, just run against `/dev/ttyUSB0`.

## Repository layout (recommended)

```

adds-ai-terminal/
README.md
LICENSE
pyproject.toml
src/adds_ai/
app.py          # UI + main loop
ttyio.py        # raw TTY open/read/write
ansi.py         # ANSI helpers
llm_openai.py   # Responses API client
prompts.py      # system prompt + presets
retrieval.py    # keyword retrieval (local KB)
config.py       # env/args
data/
system_prompt.txt
presets.yaml
kb.yaml
scripts/
pty_pair.sh
run_dev.sh
deploy_pi.sh
systemd/
adds-ai.service

````

## Configuration

### Environment variables
- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `ADDS_COLS` (default: `80`)
- `ADDS_ROWS` (default: `24`)
- `ADDS_PRESET` (default preset name, optional)

### Files in `data/`
- `system_prompt.txt` — global system instruction text
- `presets.yaml` — named prompt presets (tone/task)
- `kb.yaml` — local keyword knowledge base (blurbs)

## Prompting model

Every request is composed as:

1) `system_prompt` (base behavior)
2) `preset_prompt` (selected mode, e.g., “concise assistant”, “coding”, “terminal UI”)
3) `retrieval_context` (keyword matched blurbs)
4) user message

The app uses OpenAI **Responses API** with streaming output.

## Quickstart (Local Dev)

### Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
export OPENAI_API_KEY=...
```

### Run the faithful serial simulation

```bash
./scripts/run_dev.sh
```

This starts:

* a PTY pair
* a `screen` session as the “monitor”
* the app attached to the other PTY

## Deploy to Pi

1. Copy repo to Pi:

```bash
PI_HOST=raspberrypi.local ./scripts/deploy_pi.sh
```

2. Set `/etc/adds-ai.env` on the Pi:

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
ADDS_COLS=80
ADDS_ROWS=24
```

3. Enable systemd service:

```bash
sudo cp /opt/adds-ai/systemd/adds-ai.service /etc/systemd/system/adds-ai.service
sudo systemctl daemon-reload
sudo systemctl enable --now adds-ai.service
```

## License

MIT License unless you swap for Apache-2.0/GPLv3 per your goals.
