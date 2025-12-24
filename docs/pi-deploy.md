# Raspberry Pi deployment

Runs the same app binary against `/dev/ttyUSB0` to drive the ADDS terminal.

## Prep the Pi (once)

```bash
sudo apt update
sudo apt -y install python3-pip python3-venv
sudo mkdir -p /opt/adds-ai
sudo chown -R pi:pi /opt/adds-ai
```

## Push code from macOS

```bash
PI_HOST=raspberrypi.local ./scripts/deploy_pi.sh
```

`deploy_pi.sh` rsyncs the repo, creates a venv, and installs `openai`.

## Run interactively

```bash
ssh -t pi@raspberrypi.local '
  cd /opt/adds-ai
  . .venv/bin/activate
  export OPENAI_API_KEY=...
  ADDS_COLS=80 ADDS_ROWS=24 python -m adds_ai.app --tty /dev/ttyUSB0
'
```

Confirm the FTDI cable shows up as `/dev/ttyUSB0` (`ls /dev/ttyUSB*`). Set the ADDS to 9600 8N1, ANSI/VT100 mode, 80×24. You should see the same UI as `screen` locally.

## Appliance mode (systemd)

1. Store env in `/etc/adds-ai.env`:
   ```bash
   sudo tee /etc/adds-ai.env >/dev/null <<'EOF'
   OPENAI_API_KEY=YOUR_KEY
   OPENAI_MODEL=gpt-4o-mini
   ADDS_COLS=80
   ADDS_ROWS=24
   EOF
   sudo chmod 600 /etc/adds-ai.env
   ```
2. Install the unit:
   ```bash
   sudo cp /opt/adds-ai/systemd/adds-ai.service /etc/systemd/system/adds-ai.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now adds-ai.service
   ```

On reboot the ADDS should immediately show the chat UI.
