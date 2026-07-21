from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .cv_sections import section_lines


EXPERIENCE_NORMALIZER_VERSION = "experience-v1.0.0"

_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH_TOKEN = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_TOKEN = rf"(?:{_MONTH_TOKEN})\.?\s+(?:19|20)\d{{2}}|(?:0?[1-9]|1[0-2])[/.](?:19|20)\d{{2}}|(?:19|20)\d{{2}}"
_RANGE = re.compile(
    rf"(?P<start>{_DATE_TOKEN})\s*(?:-|\u2013|\u2014|\bto\b|\buntil\b)\s*"
    rf"(?P<end>present|current|now|{_DATE_TOKEN})",
    flags=re.IGNORECASE,
)
_ROLE_HINT = re.compile(
    r"\b(?:engineer|developer|manager|analyst|consultant|designer|specialist|administrator|"
    r"coordinator|assistant|intern|researcher|scientist|director|officer|lead|teacher|tutor|"
    r"recruiter|accountant|sales|support|technician)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ExperienceEstimate:
    years: float
    source: str
    intervals: int = 0


def professional_experience(text: str, reference_date: date | None = None) -> ExperienceEstimate:
    """Normalize explicit claims and non-overlapping employment date ranges."""
    explicit = _explicit_years(text)
    intervals = employment_intervals(text, reference_date=reference_date)
    timeline = _union_years(intervals)
    if explicit >= timeline and explicit > 0:
        return ExperienceEstimate(round(explicit, 1), "explicit", len(intervals))
    if timeline > 0:
        return ExperienceEstimate(round(timeline, 1), "timeline", len(intervals))
    return ExperienceEstimate(0.0, "unknown", 0)


def employment_intervals(text: str, reference_date: date | None = None) -> list[tuple[int, int]]:
    reference = reference_date or date.today()
    lines = section_lines(text)
    has_experience_heading = any(line.is_heading and line.section == "experience" for line in lines)
    intervals: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        if line.is_heading:
            continue
        if line.section in {"education", "projects", "certifications", "awards", "personal"}:
            continue
        nearby = " ".join(item.text for item in lines[max(0, index - 1) : index + 2] if not item.is_heading)
        eligible = line.section == "experience" or (
            not has_experience_heading and bool(_ROLE_HINT.search(nearby))
        )
        if not eligible:
            continue
        for match in _RANGE.finditer(line.text):
            start = _month_index(match.group("start"), reference, is_end=False)
            end = _month_index(match.group("end"), reference, is_end=True)
            if start is None or end is None or start > end:
                continue
            if start == end and re.fullmatch(r"(?:19|20)\d{2}", match.group("start").strip()):
                end = start + 12
            # CVs occasionally repeat the same date line through layout
            # extraction; deduplication and interval union handle both cases.
            intervals.append((start, max(start + 1, end)))
    return sorted(set(intervals))


def _explicit_years(text: str) -> float:
    normalized = text.lower()
    normalized = re.sub(
        r"\b(?:" + "|".join(_NUMBER_WORDS) + r")\b",
        lambda match: _NUMBER_WORDS[match.group(0)],
        normalized,
    )
    year_patterns = (
        r"\b(?:over|more than|at least|minimum(?: of)?)?\s*(\d+(?:\.\d+)?)\+?\s*"
        r"(?:years|yrs)(?:\s+of|['\u2019]s)?\s+(?:professional|commercial|industry|software|"
        r"engineering|relevant|work|hands-on|development)?\s*experience\b",
        r"\b(?:professional|commercial|industry|software|engineering|work)\s+experience\s*"
        r"[:\-]?\s*(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\b",
        r"\bexperience\s*[:\-]\s*(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\b",
    )
    years = [float(value) for pattern in year_patterns for value in re.findall(pattern, normalized)]
    month_patterns = (
        r"\b(\d+(?:\.\d+)?)\+?\s*months?\s+of\s+(?:professional|commercial|industry|"
        r"software|engineering|relevant|work)\s+experience\b",
        r"\b(?:professional|commercial|industry|software|engineering|work)\s+experience\s*"
        r"[:\-]?\s*(\d+(?:\.\d+)?)\+?\s*months?\b",
    )
    months = [float(value) for pattern in month_patterns for value in re.findall(pattern, normalized)]
    values = [*years, *[value / 12 for value in months]]
    return max(values, default=0.0)


def _month_index(value: str, reference: date, is_end: bool) -> int | None:
    normalized = re.sub(r"\s+", " ", value.lower().replace(".", "")).strip()
    if normalized in {"present", "current", "now"}:
        return reference.year * 12 + reference.month
    numeric = re.fullmatch(r"(0?[1-9]|1[0-2])/(19\d{2}|20\d{2})", normalized)
    if numeric:
        month, year = int(numeric.group(1)), int(numeric.group(2))
        return year * 12 + month - 1 + int(is_end)
    named = re.fullmatch(rf"({_MONTH_TOKEN})\s+(19\d{{2}}|20\d{{2}})", normalized)
    if named:
        month, year = _MONTHS[named.group(1)], int(named.group(2))
        return year * 12 + month - 1 + int(is_end)
    if re.fullmatch(r"(?:19|20)\d{2}", normalized):
        year = int(normalized)
        # A year-only range is ambiguous. Treat the end as the start of the
        # stated end year (conservative), while still granting one year for a
        # same-year entry.
        return year * 12
    return None


def _union_years(intervals: list[tuple[int, int]]) -> float:
    if not intervals:
        return 0.0
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    months = sum(max(0, end - start) for start, end in merged)
    return months / 12
