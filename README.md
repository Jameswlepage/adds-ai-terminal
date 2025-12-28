# AMBER AI Terminal

A vintage RS-232 text terminal (ADDS 4000/260, VT100, etc.) turned into an AI chat appliance.

![EIS / ADDS Terminal with OpenAI chat, in text mode](https://github.com/user-attachments/assets/6cc517c0-9d33-4145-b47f-29afd25fd0ba)

Built for real serial terminals: renders to a TTY device (PTY in dev; `/dev/ttyUSB0` on a Pi), handles serial latency and flow control, and respects strict 80x24 constraints.

## Features

- **Multiple display modes**: Full-screen ANSI, plain output, or line-oriented text mode
- **Streaming responses** with ESC to interrupt mid-generation
- **Web search** with inline citations (`[1]`, `[2]`) and auto-trigger on keywords like "news", "latest", "current"
- **Prompt presets**: Switch personas quickly (coding, research, ops, tutorial)
- **Knowledge base retrieval**: Keyword-matched context injection
- **Session tracking**: Token count and cost displayed in status bar
- **Transcript scrolling** with arrow keys

## Hardware

- Raspberry Pi (any model running Linux + Python)
- USB-serial adapter (FTDI preferred) with RS-232 to the terminal
- Terminal: ADDS 4000/260, VT100, or similar

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
export OPENAI_API_KEY=...
./scripts/run_dev.sh       # PTY pair + screen + app
```

Deploy to Pi:

```bash
PI_HOST=raspberrypi.local ./scripts/deploy_pi.sh
ssh -t pi@"$PI_HOST" 'cd /opt/adds-ai && . .venv/bin/activate && \
  OPENAI_API_KEY=... python -m adds_ai.app --tty /dev/ttyUSB0'
```

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show commands |
| `/new` | Clear conversation |
| `/clear` | Clear screen |
| `/preset [name]` | Switch preset |
| `/model [name]` | Change model |
| `/search [query]` | Web search |
| `/ctx` | Toggle knowledge base |
| `/quit` | Exit |

**Shortcuts**: `/1` search, `/2` toggle ctx, `/3` tutorial, `/4` models

**Keys**: ESC interrupts response, Up/Down scrolls, Ctrl+U clears input

## Configuration

```
--tty PATH       TTY device (e.g. /dev/ttyUSB0)
--text-mode      Line-oriented output (no cursor addressing)
--no-ansi        Disable ANSI sequences
--preset NAME    Default preset
--model NAME     LLM model
```

Environment: `OPENAI_API_KEY`, `OPENAI_MODEL`, `ADDS_COLS`, `ADDS_ROWS`, `ADDS_TEXT_MODE`, `ADDS_NO_ANSI`

## Docs

- `docs/serial-dev.md` - Local dev with PTY pairs
- `docs/pi-deploy.md` - Pi deployment and systemd
- `docs/adds-terminal.md` - Terminal notes
- `data/` - System prompt, presets, knowledge base

## License

MIT
