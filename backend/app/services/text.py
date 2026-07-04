from __future__ import annotations

import io
import re
from pathlib import Path

from pypdf import PdfReader


PDF_PARSER_VERSION = "pypdf-layout-v4"


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def read_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages[:8]:
        try:
            # Layout mode preserves section headings and list boundaries. Those
            # boundaries are essential for distinguishing skills, projects and
            # experience. The old whitespace collapse turned a whole CV into one
            # sentence and caused adjacent columns/sections to contaminate facts.
            try:
                parts.append(page.extract_text(extraction_mode="layout") or "")
            except (TypeError, ValueError):
                parts.append(page.extract_text() or "")
        except Exception:
            continue
    lines: list[str] = []
    for raw_line in "\n\n".join(parts).replace("\u00a0", " ").splitlines():
        # Layout extraction uses wide whitespace gaps between columns. Treat
        # each column fragment as its own logical line so right-column skills
        # cannot be appended to a left-column project description.
        fragments = [re.sub(r"[ \t]+", " ", part).strip() for part in re.split(r"[ \t]{3,}", raw_line.strip())]
        fragments = [part for part in fragments if part]
        if fragments:
            lines.extend(fragments)
        elif lines and lines[-1] != "":
            lines.append("")
    text = "\n".join(lines).strip()
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    return _repair_split_vocabulary(text)


def _repair_split_vocabulary(text: str) -> str:
    # Some PDFs position a single word as multiple text runs and pypdf places a
    # newline between them (for example `co\nmmunication`). Repair only known
    # profile vocabulary, which avoids unsafe generic joining of normal lines.
    from .ontology import SKILLS

    words = {
        token.lower()
        for definition in SKILLS
        for alias in definition.aliases
        for token in re.findall(r"[A-Za-z]{6,}", alias)
    }
    words.update({"english", "hebrew", "arabic", "professional", "experience", "education"})
    for word in sorted(words, key=len, reverse=True):
        for split in range(2, len(word) - 2):
            pattern = rf"\b{re.escape(word[:split])}\s*\n\s*{re.escape(word[split:])}\b"
            text = re.sub(pattern, word, text, flags=re.IGNORECASE)
    return text


def safe_filename(value: str) -> str:
    name = Path(value).name or "document.pdf"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name)[:120]
