from __future__ import annotations

import io
import json
import re
import urllib.request
from dataclasses import dataclass, field

from pypdf import PdfReader

from ..config import get_settings


PDF_PARSER_VERSION = "pypdf-layout-v5+ocr-fallback-v1"


@dataclass(frozen=True)
class DocumentReadResult:
    text: str
    method: str
    scanned_pdf_detected: bool
    ocr_attempted: bool
    ocr_confidence: float | None = None
    ocr_engine: str = ""
    page_evidence: list[dict[str, object]] = field(default_factory=list)

    def metadata(self) -> dict[str, object]:
        return {
            "chars": len(self.text),
            "parser_version": PDF_PARSER_VERSION,
            "read_method": self.method,
            "scanned_pdf_detected": self.scanned_pdf_detected,
            "ocr_attempted": self.ocr_attempted,
            "ocr_confidence": self.ocr_confidence,
            "ocr_engine": self.ocr_engine,
            "ocr_pages": self.page_evidence,
        }


def read_pdf_document(data: bytes) -> DocumentReadResult:
    extracted = _read_pypdf(data)
    scanned = _meaningful_character_count(extracted) < 80
    if not scanned:
        return DocumentReadResult(extracted, "pypdf_layout", False, False)

    ocr = _read_configured_ocr(data)
    if _meaningful_character_count(ocr.text) >= 80:
        return DocumentReadResult(
            ocr.text,
            "ocr_service",
            True,
            True,
            ocr.confidence,
            ocr.engine,
            ocr.pages,
        )
    return DocumentReadResult(extracted, "pypdf_layout", True, bool(get_settings().ocr_service_url))


def _read_pypdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages[:8]:
        try:
            try:
                parts.append(page.extract_text(extraction_mode="layout") or "")
            except (TypeError, ValueError):
                parts.append(page.extract_text() or "")
        except Exception:
            continue
    lines: list[str] = []
    for raw_line in "\n\n".join(parts).replace("\u00a0", " ").splitlines():
        fragments = [
            re.sub(r"[ \t]+", " ", part).strip()
            for part in re.split(r"[ \t]{3,}", raw_line.strip())
        ]
        fragments = [part for part in fragments if part]
        if fragments:
            lines.extend(fragments)
        elif lines and lines[-1] != "":
            lines.append("")
    text = "\n".join(lines).strip()
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    return _repair_split_vocabulary(text)


@dataclass(frozen=True)
class OCRServiceResult:
    text: str = ""
    confidence: float | None = None
    engine: str = ""
    pages: list[dict[str, object]] = field(default_factory=list)


def _read_configured_ocr(data: bytes) -> OCRServiceResult:
    settings = get_settings()
    if not settings.ocr_service_url:
        return OCRServiceResult()
    headers = {"Content-Type": "application/pdf", "Accept": "application/json"}
    if settings.ocr_service_token:
        headers["Authorization"] = f"Bearer {settings.ocr_service_token}"
    request = urllib.request.Request(settings.ocr_service_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8", errors="ignore"))
    except Exception:
        return OCRServiceResult()
    if not isinstance(payload, dict):
        return OCRServiceResult()
    raw_pages = payload.get("pages")
    pages = [item for item in raw_pages if isinstance(item, dict)] if isinstance(raw_pages, list) else []
    try:
        confidence = float(payload.get("confidence"))
    except (TypeError, ValueError):
        confidence = None
    return OCRServiceResult(
        text=str(payload.get("text") or "").strip(),
        confidence=confidence,
        engine=str(payload.get("engine") or ""),
        pages=pages,
    )


def _meaningful_character_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]", text))


def _repair_split_vocabulary(text: str) -> str:
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
