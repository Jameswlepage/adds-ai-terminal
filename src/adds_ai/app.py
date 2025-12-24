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
        self.mode = "splash"  # splash | chat
        self.splash_input = ""
        self.splash_input_limit = max(8, min(self.cols - 20, 40))
        self.user_label = "YOU"
        self.user_name = "YOU"
        self.input_buf = ""
        self.status = "Idle"
        self.show_ctx = True
        self.last_matches: List[str] = []
        self.session_tokens = 0
        self.session_cost = 0.0
        self.interrupted = False
        self.history: List[dict] = []  # Conversation history
        self.max_history = 20  # Max messages to keep
        self.scroll_offset = 0
        self.personalization_sent = False
        self.personalization_note = ""
        self.empty_state = False
        self.available_models: List[str] = [
            "gpt-5.2-2025-12-11",
            "gpt-5-nano-2025-08-07",
            "gpt-4o",
        ]
        self.shortcuts = {
            "/1": "search",
            "/2": "ctx",
            "/3": "tutorial",
            "/4": "models",
        }
        self.commands = [
            "/help",
            "/new",
            "/clear",
            "/quit",
            "/preset",
            "/model",
            "/ctx",
            "/tutorial",
            "/search",
        ]

    def add_block(self, prefix: str, text: str) -> None:
        for ln in wrap(prefix + text, self.cols):
            self.lines.append(ln[: self.cols])
        self.lines.append("")

    def user_prefix(self) -> str:
        return f"{self.user_label}: "

    def add_to_history(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # Trim to max_history (keep pairs to maintain context)
        while len(self.history) > self.max_history:
            self.history.pop(0)

    def clear_history(self) -> None:
        self.history.clear()

    def add_shortcut_grid(self, center: bool = True) -> None:
        """Render a 2x2 grid of shortcut suggestions into the transcript."""
        width = min(self.cols, 78)
        gap = 4
        cell_w = max(18, (width - gap - 4) // 2)
        top = "+" + "-" * cell_w + "+"

        def box_row(left: str, right: str) -> str:
            return (
                "|" + left[:cell_w].ljust(cell_w) + "|" + " " * gap + "|" + right[:cell_w].ljust(cell_w) + "|"
            )

        row_gap = " " * (len(top) * 2 + gap)
        rows_top = [
            top + " " * gap + top,
            box_row("/1 Search web (/search <topic>)", "/2 Toggle context (/ctx)"),
            box_row("Get current info with citations", "Turn retrieval context on/off"),
            top + " " * gap + top,
        ]
        rows_bottom = [
            top + " " * gap + top,
            box_row("/3 Tutorial (/tutorial)", "/4 Models (/model <id>)"),
            box_row("How to use AMBER AI", "List or set available models"),
            top + " " * gap + top,
        ]
        rows = rows_top + [row_gap] + rows_bottom
        grid_lines = rows + [""]

        if center:
            height = self.viewport_height()
            remaining = height - len(self.lines) - len(grid_lines)
            pad = max(0, remaining // 2)
            self.lines.extend([""] * pad)

        self.lines.extend(grid_lines)
        self.empty_state = True

    def viewport_height(self) -> int:
        """Visible rows for the transcript area."""
        if self.no_ansi:
            return max(1, self.rows - 1)
        return max(1, self.rows - 3)

    def _clamp_scroll(self, height: int) -> None:
        max_offset = max(len(self.lines) - height, 0)
        if self.scroll_offset > max_offset:
            self.scroll_offset = max_offset

    def _view_slice(self, height: int) -> List[str]:
        self._clamp_scroll(height)
        start = max(len(self.lines) - height - self.scroll_offset, 0)
        end = start + height
        return self.lines[start:end]

    def render_plain(self) -> bytes:
        top = 0
        bottom = self.rows - 2
        height = bottom - top + 1
        view = self._view_slice(height)
        buf = []
        buf.append(f"[ADDS AI Chat | model: {self.model}]")
        buf.append("")
        buf.extend(view)
        buf.append(f"[{self.status}]")
        buf.append("> " + self.input_buf)
        return ("\n".join(buf) + "\n").encode(errors="ignore")

    def render_splash(self) -> bytes:
        art = [
            "    ___              __                 ___    ____",
            "   /   |  ____ ___  / /_  ___  _____   /   |  /  _/",
            "  / /| | / __ `__ \\/ __ \\/ _ \\/ ___/  / /| |  / /  ",
            " / ___ |/ / / / / / /_/ /  __/ /     / ___ |_/ /   ",
            "/_/  |_/_/ /_/ /_/_.___/\\___/_/     /_/  |_/___/   ",
        ]
        subheader = ""
        call_sign_label = "Your Name"
        prompt = self.splash_input[: self.splash_input_limit]

        if self.no_ansi:
            lines: List[str] = []
            lines.extend(art)
            lines.append(subheader)
            lines.append("")
            lines.append(f"[{call_sign_label}]> {prompt}")
            lines.append("(press Enter to login)")
            return ("\n".join(lines) + "\n").encode(errors="ignore")

        b = bytearray()
        b += ansi.hide_cursor()
        b += ansi.clear()

        total_height = len(art) + 1 + 3 + 1  # art + subheader + box + help
        start_row = max(1, (self.rows - total_height) // 2 + 1)
        max_art_width = max(len(a) for a in art)
        col_offset = max(1, (self.cols - max_art_width) // 2 + 1)

        for idx, line in enumerate(art):
            b += ansi.move(start_row + idx, col_offset)
            b += line[: self.cols].encode(errors="ignore")

        if subheader:
            sub_col = max(1, (self.cols - len(subheader)) // 2 + 1)
            b += ansi.move(start_row + len(art) + 1, sub_col)
            b += subheader[: self.cols].encode(errors="ignore")

        box_width = max(20, min(self.cols - 8, 68))
        box_col = max(1, (self.cols - box_width) // 2 + 1)
        box_top = start_row + len(art) + (3 if subheader else 1)
        horiz = "+" + "-" * (box_width - 2) + "+"
        b += ansi.move(box_top, box_col)
        b += horiz.encode()

        label = f"| {call_sign_label}: "
        field_width = box_width - len(label) - 2
        trimmed = prompt[:field_width]
        field = (label + trimmed).ljust(box_width - 1) + "|"
        b += ansi.move(box_top + 1, box_col)
        b += field.encode(errors="ignore")

        b += ansi.move(box_top + 2, box_col)
        b += horiz.encode()

        help_line = "(Enter to login)"
        help_col = max(1, (self.cols - len(help_line)) // 2 + 1)
        b += ansi.move(box_top + 4, help_col)
        b += help_line[: self.cols].encode(errors="ignore")

        cursor_col = box_col + len(label) + len(trimmed)
        b += ansi.move(box_top + 1, cursor_col)
        b += ansi.show_cursor()
        return bytes(b)

    def render(self) -> bytes:
        if self.mode == "splash":
            return self.render_splash()
        if self.no_ansi:
            return self.render_plain()

        b = bytearray()
        b += ansi.hide_cursor()
        b += ansi.clear()

        # header
        b += ansi.rev(True)
        b += ansi.move(1, 1)
        preset_str = f" | preset: {self.preset}" if self.preset else ""
        hdr = f" AMBER AI Chat | model: {self.model}{preset_str} | /help /clear /quit "
        b += hdr[: self.cols].ljust(self.cols).encode()
        b += ansi.reset()

        # transcript window
        top = 2
        bottom = self.rows - 2
        height = bottom - top + 1
        view = self._view_slice(height)

        for i in range(height):
            b += ansi.move(top + i, 1)
            b += ansi.clear_eol()
            if i < len(view):
                b += view[i].encode(errors="ignore")

        # status bar (with command suggestions when typing /)
        b += ansi.rev(True)
        b += ansi.move(self.rows - 1, 1)

        # Check for command suggestions
        cmd_hint = ""
        model_hint = ""
        if self.input_buf.startswith("/") and len(self.input_buf) > 0:
            matches = [c for c in self.commands if c.startswith(self.input_buf)]
            if matches and self.input_buf not in self.commands:
                cmd_hint = "  ".join(matches[:4])
        trimmed = self.input_buf.lstrip()
        if trimmed.lower().startswith("/model"):
            partial = trimmed[len("/model"):].strip().lower()
            filtered = (
                [m for m in self.available_models if partial in m.lower()]
                if partial
                else self.available_models
            )
            model_hint = "models: " + ("  ".join(filtered) if filtered else "(none)")

        if cmd_hint:
            st = f" {cmd_hint}"
            if model_hint:
                st += f" | {model_hint}"
            st += " "
        elif model_hint:
            st = f" {model_hint} "
        else:
            ctx_note = ""
            if self.last_matches:
                ctx_note = " | ctx:on" if self.show_ctx else " | ctx:off"
            cost_str = f" | ${self.session_cost:.4f}" if self.session_cost > 0 else ""
            tok_str = f" | {self.session_tokens}tok" if self.session_tokens > 0 else ""
            st = f" {self.status}{ctx_note}{tok_str}{cost_str} "
            if self.empty_state:
                st += " * At your fingers rests the world's knowledge. What will you create?"

        b += st[: self.cols].ljust(self.cols).encode()
        b += ansi.reset()

        # input
        b += ansi.move(self.rows, 1)
        b += ansi.clear_eol()
        prompt = "> " + self.input_buf
        b += prompt[-self.cols :].encode(errors="ignore")

        b += ansi.show_cursor()
        return bytes(b)

    def start_chat(self) -> None:
        name = self.splash_input.strip() or "Operator"
        self.user_label = name.upper()
        self.user_name = name
        self.personalization_note = f"Operator name: {name}. When asked who the user is, answer with this name."
        self.personalization_sent = False
        self.mode = "chat"
        self.lines.clear()
        self.add_block(
            "SYS: ", f"Linked as {self.user_label}. Type /help for commands."
        )
        self.add_shortcut_grid()
        self.splash_input = ""


def do_stream(
    ui: UI,
    llm: OpenAIClient,
    fd: int,
    system_prompt: str,
    preset_text: str,
    user_msg: str,
    kb,
    web_search: bool = False,
) -> None:
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

    # Auto-enable web search for news/current queries unless explicitly overridden
    needs_web = web_search
    if not needs_web:
        text_l = user_msg.lower()
        web_triggers = [
            "news",
            "headline",
            "latest",
            "current",
            "today",
            "this week",
            "breaking",
            "update",
            "search",
            "find",
            "lookup",
        ]
        if any(t in text_l for t in web_triggers):
            needs_web = True

    system_block_parts = [system_prompt, preset_text]
    if not ui.personalization_sent and ui.personalization_note:
        system_block_parts.append(ui.personalization_note)
    if web_search:
        system_block_parts.append("Use web search to answer this request and cite sources.")
    if retrieval_context:
        system_block_parts.append(retrieval_context)
    system_block = "\n\n".join([p for p in system_block_parts if p]).strip()

    # Build payload with conversation history
    payload = [{"role": "system", "content": system_block}]
    payload.extend(ui.history)  # Add conversation history
    payload.append({"role": "user", "content": user_msg})

    # Add user message to history
    ui.add_to_history("user", user_msg)

    stream = llm.stream(model=ui.model, input_payload=payload, web_search=needs_web)

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
    response_text = "".join(out).strip()
    del ui.lines[ai_block_start:]
    ui.add_block("AI: ", response_text)

    # Add AI response to history
    ui.add_to_history("assistant", response_text)

    # Show citations if any
    if final_result and final_result.citations:
        ui.add_block("SRC: ", " | ".join(final_result.citations[:3]))  # Limit to 3

    # Update session stats
    if final_result:
        ui.session_tokens = llm.session_tokens
        ui.session_cost = llm.session_cost
    if not ui.personalization_sent and ui.personalization_note:
        ui.personalization_sent = True

    status_parts = ["Idle", f"{elapsed_ms}ms"]
    if ui.interrupted:
        status_parts.insert(1, "stopped")
    ui.status = " | ".join(status_parts)
    flush()


def parse_args():
    env = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--tty",
        required=True,
        help="TTY device path (e.g. /dev/ttys010 or /dev/ttyUSB0)",
    )
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
            if ui.mode == "splash":
                line = ui.splash_input.strip()
                if line in ("/q", "/quit"):
                    return
                ui.start_chat()
                flush()
                continue

            line = ui.input_buf.strip()
            ui.input_buf = ""
            if not line:
                flush()
                continue

            # commands
            if line.startswith("/"):
                cmd = line.split()

                # Shortcut grid commands
                if line in ui.shortcuts:
                    if line == "/1":
                        ui.add_block("SYS: ", "Shortcut: /search <topic>. Type your query after /search.")
                        ui.input_buf = "/search "
                        flush()
                        continue
                    if line == "/2":
                        ui.show_ctx = not ui.show_ctx
                        state = "on" if ui.show_ctx else "off"
                        ui.add_block("SYS: ", f"Retrieval context {state}")
                        ui.status = "Idle"
                        flush()
                        continue
                    if line == "/3":
                        tutorial_prompt = presets.get("tutorial", "Explain this system.")
                        do_stream(
                            ui,
                            llm,
                            fd,
                            system_prompt,
                            tutorial_prompt,
                            "Give me a complete tutorial of ADDS AI.",
                            kb,
                            web_search=False,
                        )
                        continue
                    if line == "/4":
                        models = ", ".join(ui.available_models)
                        ui.add_block("SYS: ", f"Models: {models}. Set with /model <id>.")
                        ui.input_buf = "/model "
                        flush()
                        continue

                if cmd[0] in ("/q", "/quit"):
                    return
                if cmd[0] == "/clear":
                    ui.lines.clear()
                    ui.add_block("SYS: ", "Cleared.")
                elif cmd[0] == "/help":
                    ui.add_block(
                        "SYS: ",
                        "Commands: /help /new /clear /quit /preset [name] /model [name] /ctx /tutorial /search [query] | ESC to stop",
                    )
                elif cmd[0] == "/new":
                    ui.clear_history()
                    ui.lines.clear()
                    ui.add_block("SYS: ", "New conversation started.")
                    ui.personalization_sent = False
                    ui.add_shortcut_grid()
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
                elif cmd[0] == "/model":
                    if len(cmd) == 1:
                        models = ", ".join(ui.available_models)
                        ui.add_block("SYS: ", f"Current model: {ui.model} | Available: {models}")
                    else:
                        name = " ".join(cmd[1:])
                        ui.model = name
                        if name not in ui.available_models:
                            ui.available_models.append(name)
                        ui.add_block("SYS: ", f"Model set to {name}")
                elif cmd[0] == "/ctx":
                    ui.show_ctx = not ui.show_ctx
                    state = "on" if ui.show_ctx else "off"
                    ui.add_block("SYS: ", f"Retrieval context {state}")
                elif cmd[0] == "/tutorial":
                    # Use the tutorial preset for this message
                    tutorial_prompt = presets.get("tutorial", "Explain this system.")
                    do_stream(
                        ui,
                        llm,
                        fd,
                        system_prompt,
                        tutorial_prompt,
                        "Give me a complete tutorial of ADDS AI.",
                        kb,
                        web_search=False,
                    )
                    continue
                elif cmd[0] == "/search":
                    query = " ".join(cmd[1:]) if len(cmd) > 1 else ""
                    if not query:
                        ui.add_block("SYS: ", "Usage: /search <query>")
                    else:
                        ui.add_block(ui.user_prefix(), f"[search] {query}")
                        do_stream(
                            ui,
                            llm,
                            fd,
                            system_prompt,
                            preset_text,
                            query,
                            kb,
                            web_search=True,
                        )
                        continue
                else:
                    ui.add_block("SYS: ", f"Unknown: {cmd[0]}")
                ui.status = "Idle"
                flush()
                continue

            # normal chat
            ui.empty_state = False
            ui.add_block(ui.user_prefix(), line)
            do_stream(
                ui, llm, fd, system_prompt, preset_text, line, kb, web_search=False
            )
            continue

        # Backspace / DEL (handle multiple codes)
        if c in (8, 127, 0x08, 0x7F):
            if ui.mode == "splash":
                ui.splash_input = ui.splash_input[:-1]
            else:
                ui.input_buf = ui.input_buf[:-1]
            flush()
            continue

        # ESC - handle escape sequences (arrows, scroll, etc.)
        if c == 27:
            height = ui.viewport_height()
            r2, _, _ = select.select([fd], [], [], 0.05)
            if r2:
                seq = read_bytes(fd, 1)
                if seq and seq[0] in (91, 79):  # '[' or 'O'
                    r3, _, _ = select.select([fd], [], [], 0.05)
                    if r3:
                        end = read_bytes(fd, 1)
                        if end:
                            if end[0] == 65:  # Up arrow
                                ui.scroll_offset = min(
                                    ui.scroll_offset + 1,
                                    max(len(ui.lines) - height, 0),
                                )
                                flush()
                            elif end[0] == 66:  # Down arrow
                                ui.scroll_offset = max(ui.scroll_offset - 1, 0)
                                flush()
            # ESC alone or unhandled sequence - ignore
            continue

        # Filter out escape sequence fragments that leaked through
        # (common when scrolling fast - [A, [B, [C, [D, etc.)
        if c == 91:  # '[' character
            # Check if next char is a letter (escape sequence fragment)
            r2, _, _ = select.select([fd], [], [], 0.02)
            if r2:
                next_ch = read_bytes(fd, 1)
                if next_ch and (65 <= next_ch[0] <= 90 or 97 <= next_ch[0] <= 122):
                    # It's an escape fragment like [A - discard both
                    continue
                # Not a fragment, but we consumed a char - need to handle it
                # For now, just skip the '[' and let the next char be processed normally
                # This means '[' followed by non-letter is also discarded
            continue

        # Ctrl+U - clear input
        if c == 21:
            if ui.mode == "splash":
                ui.splash_input = ""
            else:
                ui.input_buf = ""
            flush()
            continue

        # Ignore other control characters
        if c < 32:
            continue

        # printable ASCII only
        if 32 <= c <= 126:
            if ui.mode == "splash":
                if len(ui.splash_input) < ui.splash_input_limit:
                    ui.splash_input += chr(c)
            else:
                ui.input_buf += chr(c)
            flush()


if __name__ == "__main__":
    main()
