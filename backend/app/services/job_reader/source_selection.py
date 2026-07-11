from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DescriptionSelection:
    text: str
    used_dom: bool
    structured_quality: float
    dom_quality: float


def choose_description(structured_text: str, dom_text: str) -> DescriptionSelection:
    """Choose posting content independently from structured identity metadata."""

    structured_text = structured_text.strip()
    dom_text = dom_text.strip()
    structured_quality = description_quality(structured_text)
    dom_quality = description_quality(dom_text)
    if not structured_text:
        return DescriptionSelection(dom_text, bool(dom_text), structured_quality, dom_quality)
    if not dom_text:
        return DescriptionSelection(structured_text, False, structured_quality, dom_quality)

    materially_richer = len(dom_text) >= max(1_000, int(len(structured_text) * 1.45))
    stronger_evidence = dom_quality >= structured_quality + 0.12
    stale_preview = len(structured_text) < 850 and len(dom_text) >= 1_300
    use_dom = (materially_richer and dom_quality >= structured_quality) or stronger_evidence or stale_preview
    return DescriptionSelection(
        dom_text if use_dom else structured_text,
        use_dom,
        structured_quality,
        dom_quality,
    )


def description_quality(text: str) -> float:
    if not text:
        return 0.0
    lower = text.lower()
    score = min(len(text) / 4_000, 0.42)
    evidence_terms = (
        "requirements",
        "qualifications",
        "responsibilities",
        "what you'll",
        "what you’ll",
        "what you will",
        "experience",
        "skills",
        "you will",
        "what you'll own",
    )
    score += min(sum(term in lower for term in evidence_terms) * 0.055, 0.33)
    list_lines = sum(
        bool(re.match(r"\s*(?:[-*•]|\d+[.)])\s+", line))
        for line in text.splitlines()
    )
    score += min(list_lines * 0.018, 0.16)
    if any(term in lower for term in ("apply for the role", "apply now", "join our talent community")):
        score -= 0.06
    if any(term in lower for term in ("access denied", "enable javascript", "page not found", "captcha")):
        score -= 0.4
    return round(max(0.0, min(score, 1.0)), 3)
