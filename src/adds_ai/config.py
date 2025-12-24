import os
from dataclasses import dataclass


@dataclass
class AppConfig:
    cols: int
    rows: int
    model: str
    refresh_ms: int
    no_ansi: bool
    preset: str | None


def load_config() -> AppConfig:
    cols = int(os.getenv("ADDS_COLS", "80"))
    rows = int(os.getenv("ADDS_ROWS", "24"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    refresh_ms = int(os.getenv("ADDS_REFRESH_MS", "100"))
    no_ansi = os.getenv("ADDS_NO_ANSI", "0") == "1"
    preset = os.getenv("ADDS_PRESET")
    return AppConfig(cols=cols, rows=rows, model=model, refresh_ms=refresh_ms, no_ansi=no_ansi, preset=preset)
