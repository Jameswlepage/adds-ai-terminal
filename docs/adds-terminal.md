# ADDS 4000/260 notes

- Set terminal for ANSI/VT100 emulation, 80×24, 9600 baud, 8N1.
- Use USB→DB25 FTDI null-modem cable on the Pi; it appears as `/dev/ttyUSB0`.
- Disable local echo on the terminal; the app renders the cursor and prompt.
- If output smears or flickers, throttle redraws (`ADDS_REFRESH_MS`, `--refresh-ms`) and avoid excessive screen clears.
- If streaming pauses, try toggling hardware flow control (RTS/CTS) or lower baud to test stability.
