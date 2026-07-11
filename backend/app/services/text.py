from __future__ import annotations

import re
from pathlib import Path


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def safe_filename(value: str) -> str:
    name = Path(value).name or "document.pdf"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name)[:120]
