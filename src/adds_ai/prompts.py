import os
from pathlib import Path
from typing import Dict, Tuple

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_system_prompt(path: Path | None = None) -> str:
    p = path or DATA_DIR / "system_prompt.txt"
    try:
        return p.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def load_presets(path: Path | None = None) -> Dict[str, str]:
    p = path or DATA_DIR / "presets.yaml"
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    presets: Dict[str, str] = {}
    for key, val in data.items():
        if isinstance(val, dict) and "prompt" in val:
            presets[str(key)] = str(val["prompt"]).strip()
    return presets


def select_preset(presets: Dict[str, str], name: str | None) -> Tuple[str, str]:
    if not presets:
        return "", ""
    chosen = name or os.getenv("ADDS_PRESET") or "default"
    if chosen not in presets:
        chosen = "default" if "default" in presets else next(iter(presets))
    return chosen, presets[chosen]
