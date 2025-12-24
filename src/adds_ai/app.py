import argparse
import os
import select
import textwrap
import time
from typing import List

from . import ansi
from .config import load_config
from .llm_openai import OpenAIClient, StreamResult
from .prompts import load_presets, load_system_prompt, select_preset
from .retrieval import find_matches, format_context, load_kb
from .ttyio import open_tty, read_bytes, write_bytes


def wrap(text: str, width: int) -> List[str]:
    out: List[str] = []
    for para in text.splitlines() or [""]:
        if para == "":
            out.append("")
        else:
            out.extend(
                textwrap.wrap(
                    para,
                    width=width,
                    replace_whitespace=False,
                    drop_whitespace=False,
                )
                or [""]
            )
    return out


class UI:
    def __init__(
        self,
        cols: int,
        rows: int,
        model: str,
        preset: str,
        refresh_ms: int,
        no_ansi: bool,
    ):
        self.cols, self.rows = cols, rows
        self.model = model
        self.preset = preset
        self.refresh_ms = refresh_ms
        self.no_ansi = no_ansi
        self.lines: List[str] = []
        self.input_buf = ""
        self.status = "Idle"
        self.show_ctx = True
        self.last_matches: List[str] = []
        self.session_tokens = 0
        self.session_cost = 0.0
        self.interrupted = False

    def add_block(self, prefix: str, text: str) -> None:
        for ln in wrap(prefix + text, self.cols):
            self.lines.append(ln[: self.cols])
        self.lines.append("")

    def render_plain(self) -> bytes:
        top = 0
        bottom = self.rows - 2
        height = bottom - top + 1
        view = self.lines[-height:]
        buf = []
        buf.append(f"[ADDS AI Chat | model: {self.model}]")
        buf.append("")
        buf.extend(view)
        buf.append(f"[{self.status}]")
        buf.append("> " + self.input_buf)
        return ("\n".join(buf) + "\n").encode(errors="ignore")

    def render(self) -> bytes:
        if self.no_ansi:
            return self.render_plain()

        b = bytearray()
        b += ansi.hide_cursor()
        b += ansi.clear()

        # header
        b += ansi.rev(True)
        b += ansi.move(1, 1)
        hdr = f" ADDS AI Chat | model: {self.model} | preset: {self.preset} | /help /clear /quit "
        b += hdr[: self.cols].ljust(self.cols).encode()
        b += ansi.reset()

        # transcript window
        top = 2
        bottom = self.rows - 2
        height = bottom - top + 1
        view = self.lines[-height:]

        for i in range(height):
            b += ansi.move(top + i, 1)
            b += ansi.clear_eol()
            if i < len(view):
                b += view[i].encode(errors="ignore")

        # status
        b += ansi.rev(True)
        b += ansi.move(self.rows - 1, 1)
        ctx_note = ""
        if self.last_matches:
            ctx_note = " | ctx:on" if self.show_ctx else " | ctx:off"
        cost_str = f" | ${self.session_cost:.4f}" if self.session_cost > 0 else ""
        tok_str = f" | {self.session_tokens}tok" if self.session_tokens > 0 else ""
        st = f" {self.status}{ctx_note}{tok_str}{cost_str} "
        b += st[: self.cols].ljust(self.cols).encode()
        b += ansi.reset()

        # input
        b += ansi.move(self.rows, 1)
        b += ansi.clear_eol()
        prompt = "> " + self.input_buf
        b += prompt[-self.cols :].encode(errors="ignore")

        b += ansi.show_cursor()
        return bytes(b)


def do_stream(ui: UI, llm: OpenAIClient, fd: int, system_prompt: str, preset_text: str, user_msg: str, kb, web_search: bool = False) -> None:
    """Handle streaming a response with ESC interrupt, citations, and token tracking."""
    from .ttyio import read_bytes, write_bytes

    def flush() -> None:
        write_bytes(fd, ui.render())

    ui.status = "Thinking…"
    flush()

    out: List[str] = []
    start = time.time()
    matches = find_matches(kb, user_msg)
    ui.last_matches = [m[0] for m in matches]
    retrieval_context = format_context(matches) if ui.show_ctx else ""

    system_block_parts = [system_prompt, preset_text]
    if retrieval_context:
        system_block_parts.append(retrieval_context)
    system_block = "\n\n".join([p for p in system_block_parts if p]).strip()

    payload = [
        {"role": "system", "content": system_block},
        {"role": "user", "content": user_msg},
    ]

    stream = llm.stream(model=ui.model, input_payload=payload, web_search=web_search)

    ai_block_start = len(ui.lines)
    last_render = time.time()
    ui.interrupted = False
    final_result: StreamResult | None = None

    for event in stream:
        # Check for ESC key (non-blocking)
        r, _, _ = select.select([fd], [], [], 0)
        if r:
            ch = read_bytes(fd, 1)
            if ch and ch[0] == 27:  # ESC
                ui.interrupted = True
                out.append(" [interrupted]")
                break

        if isinstance(event, str):
            out.append(event)
            if time.time() - last_render > ui.refresh_ms / 1000.0:
                del ui.lines[ai_block_start:]
                ui.add_block("AI: ", "".join(out))
                ui.status = "Streaming… (ESC to stop)"
                flush()
                last_render = time.time()
        elif isinstance(event, StreamResult):
            final_result = event

    # Final render
    elapsed_ms = int((time.time() - start) * 1000)
    del ui.lines[ai_block_start:]
    ui.add_block("AI: ", "".join(out).strip())

    # Show citations if any
    if final_result and final_result.citations:
        ui.add_block("SRC: ", " | ".join(final_result.citations[:3]))  # Limit to 3

    # Update session stats
    if final_result:
        ui.session_tokens = llm.session_tokens
        ui.session_cost = llm.session_cost

    status_parts = ["Idle", f"{elapsed_ms}ms"]
    if ui.interrupted:
        status_parts.insert(1, "stopped")
    ui.status = " | ".join(status_parts)
    flush()


def parse_args():
    env = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--tty", required=True, help="TTY device path (e.g. /dev/ttys010 or /dev/ttyUSB0)")
    ap.add_argument("--cols", type=int, default=env.cols)
    ap.add_argument("--rows", type=int, default=env.rows)
    ap.add_argument("--model", default=env.model)
    ap.add_argument("--refresh-ms", type=int, default=env.refresh_ms)
    ap.add_argument("--no-ansi", action="store_true", default=env.no_ansi)
    ap.add_argument("--preset", default=env.preset, help="Prompt preset name")
    return ap.parse_args(), env


def main():
    args, env = parse_args()

    fd = open_tty(args.tty)
    presets = load_presets()
    preset_name, preset_text = select_preset(presets, args.preset)
    system_prompt = load_system_prompt()
    kb = load_kb()
    ui = UI(
        cols=args.cols,
        rows=args.rows,
        model=args.model,
        preset=preset_name,
        refresh_ms=args.refresh_ms,
        no_ansi=args.no_ansi,
    )
    ui.add_block("SYS: ", "Ready. Type /help for commands.")

    llm = OpenAIClient()
    write_bytes(fd, ui.render())

    def flush() -> None:
        write_bytes(fd, ui.render())

    while True:
        # non-blocking read with select
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            continue
        ch = read_bytes(fd, 1)
        if not ch:
            continue

        c = ch[0]

        # Enter
        if c in (10, 13):
            line = ui.input_buf.strip()
            ui.input_buf = ""
            if not line:
                flush()
                continue

            # commands
            if line.startswith("/"):
                cmd = line.split()
                if cmd[0] in ("/q", "/quit"):
                    return
                if cmd[0] == "/clear":
                    ui.lines.clear()
                    ui.add_block("SYS: ", "Cleared.")
                elif cmd[0] == "/help":
                    ui.add_block("SYS: ", "Commands: /help /clear /quit /preset [name] /ctx /tutorial /search [query] | ESC to stop")
                elif cmd[0] == "/preset":
                    if len(cmd) == 1:
                        names = ", ".join(presets.keys()) if presets else "(none)"
                        ui.add_block("SYS: ", f"Presets: {names}")
                    else:
                        name = cmd[1]
                        if name in presets:
                            ui.preset = name
                            preset_text = presets[name]
                            ui.add_block("SYS: ", f"Preset set to {name}")
                        else:
                            ui.add_block("SYS: ", f"Unknown preset: {name}")
                elif cmd[0] == "/ctx":
                    ui.show_ctx = not ui.show_ctx
                    state = "on" if ui.show_ctx else "off"
                    ui.add_block("SYS: ", f"Retrieval context {state}")
                elif cmd[0] == "/tutorial":
                    # Use the tutorial preset for this message
                    tutorial_prompt = presets.get("tutorial", "Explain this system.")
                    do_stream(
                        ui, llm, fd, system_prompt, tutorial_prompt,
                        "Give me a complete tutorial of ADDS AI.",
                        kb, web_search=False
                    )
                    continue
                elif cmd[0] == "/search":
                    query = " ".join(cmd[1:]) if len(cmd) > 1 else ""
                    if not query:
                        ui.add_block("SYS: ", "Usage: /search <query>")
                    else:
                        ui.add_block("YOU: ", f"[search] {query}")
                        do_stream(
                            ui, llm, fd, system_prompt, preset_text,
                            query, kb, web_search=True
                        )
                        continue
                else:
                    ui.add_block("SYS: ", f"Unknown: {cmd[0]}")
                ui.status = "Idle"
                flush()
                continue

            # normal chat
            ui.add_block("YOU: ", line)
            do_stream(ui, llm, fd, system_prompt, preset_text, line, kb, web_search=False)
            continue

        # Backspace / DEL
        if c in (8, 127):
            ui.input_buf = ui.input_buf[:-1]
            flush()
            continue

        # Ctrl+U
        if c == 21:
            ui.input_buf = ""
            flush()
            continue

        # printable ASCII only
        if 32 <= c <= 126:
            ui.input_buf += chr(c)
            flush()


if __name__ == "__main__":
    main()
