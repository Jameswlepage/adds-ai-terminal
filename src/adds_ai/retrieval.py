from pathlib import Path
from typing import Dict, List, Tuple

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MAX_MATCHES = 3
MAX_CHARS = 800


def load_kb(path: Path | None = None) -> Dict[str, str]:
    p = path or DATA_DIR / "kb.yaml"
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    kb: Dict[str, str] = {}
    for key, val in raw.items():
        if isinstance(val, dict) and "blurb" in val:
            kb[str(key)] = str(val["blurb"]).strip()
    return kb


def find_matches(kb: Dict[str, str], text: str) -> List[Tuple[str, str]]:
    if not kb or not text:
        return []
    lowered = text.lower()
    matches = []
    for key, blurb in kb.items():
        if key.lower() in lowered:
            matches.append((key, blurb))
    # deterministic: longest keyword first, then alpha
    matches.sort(key=lambda kv: (-len(kv[0]), kv[0].lower()))
    return matches[:MAX_MATCHES]


def format_context(matches: List[Tuple[str, str]]) -> str:
    if not matches:
        return ""
    lines = ["[Retrieved context]"]
    total = 0
    for key, blurb in matches:
        entry = f"- {key}: {blurb}"
        total += len(entry)
        if total > MAX_CHARS:
            break
        lines.append(entry)
    return "\n".join(lines)
