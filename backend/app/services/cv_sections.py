from __future__ import annotations

import re
from dataclasses import dataclass


SECTION_MODEL_VERSION = "cv-sections-v1.0.0"

# The first five groups are backed by the Apache-2.0 resume-seven-class
# corpus. Less common groups are conservative aliases used by the existing
# reader and by common CV conventions.
SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "summary": (
        "summary",
        "professional summary",
        "profile",
        "professional profile",
        "profile summary",
        "career summary",
        "executive summary",
        "about me",
    ),
    "objective": ("objective", "career objective", "professional objective"),
    "experience": (
        "experience",
        "professional experience",
        "work experience",
        "work history",
        "employment history",
        "employment experience",
        "career history",
        "relevant experience",
        "industry experience",
        "research experience",
        "responsibilities",
        "roles and responsibilities",
        "roles responsibilities",
        "key responsibilities",
        "job responsibilities",
        "job profile",
    ),
    "education": (
        "education",
        "educational qualification",
        "educational qualifications",
        "education qualification",
        "education qualifications",
        "academic qualification",
        "academic qualifications",
        "academic profile",
        "academic background",
        "qualifications",
    ),
    "skills": (
        "skills",
        "technical skills",
        "key skills",
        "core skills",
        "skill set",
        "skills summary",
        "computer skills",
        "computer proficiency",
        "computer knowledge",
        "it skills",
        "technical competencies",
        "core competencies",
        "tools",
        "tools and technologies",
        "technology stack",
    ),
    "certifications": (
        "certification",
        "certifications",
        "professional certifications",
        "licenses and certifications",
        "certificates",
    ),
    "projects": (
        "projects",
        "project",
        "selected projects",
        "selected engineering projects",
        "project experience",
        "project details",
        "project description",
        "academic projects",
        "personal projects",
        "hackathons",
    ),
    "languages": ("languages", "language skills", "languages known"),
    "awards": ("awards", "achievements", "awards and achievements", "honors", "honours"),
    "volunteering": ("volunteering", "volunteer experience", "community involvement"),
    "publications": ("publications", "research publications"),
    "interests": ("interests", "hobbies", "interests and activities"),
    "personal": ("personal details", "personal information", "contact", "contact information"),
}


@dataclass(frozen=True)
class SectionedLine:
    text: str
    section: str | None
    is_heading: bool = False


_ALIASES = sorted(
    ((alias, section) for section, aliases in SECTION_ALIASES.items() for alias in aliases),
    key=lambda item: len(item[0]),
    reverse=True,
)


def section_heading(line: str) -> tuple[str | None, str]:
    """Return a canonical section and any content placed after its heading."""
    stripped = re.sub(r"^\s*(?:[\u2022\u25aa\u25e6*#]+|\d{1,2}[.)])\s*", "", line).strip()
    normalized = _normalize_heading(stripped)
    if not normalized:
        return None, ""

    for alias, section in _ALIASES:
        normalized_alias = _normalize_heading(alias)
        if normalized == normalized_alias:
            return section, ""

        # Inline headings need a visible separator. This prevents prose such
        # as "professional experience with Python" from changing sections.
        match = re.match(
            rf"^\s*{_flexible_phrase(alias)}\s*[:|\-\u2013\u2014]\s*(.+)$",
            stripped,
            flags=re.IGNORECASE,
        )
        if match:
            return section, match.group(1).strip()

        # Layout extraction sometimes removes a separator from all-caps
        # headings ("LANGUAGES English - Fluent"). Keep this narrow.
        prefix = re.match(rf"^\s*({_flexible_phrase(alias)})\s+(.+)$", stripped, flags=re.IGNORECASE)
        if prefix and _mostly_upper(prefix.group(1)):
            return section, prefix.group(2).strip()

    return None, stripped


def section_lines(text: str) -> list[SectionedLine]:
    current: str | None = None
    output: list[SectionedLine] = []
    for raw in text.splitlines():
        cleaned = re.sub(r"\s+", " ", raw).strip(" \t\u2022\u25aa\u25e6")
        if not cleaned:
            continue
        section, content = section_heading(cleaned)
        if section:
            current = section
            output.append(SectionedLine(cleaned, section, True))
            if content:
                output.append(SectionedLine(content, section, False))
            continue
        output.append(SectionedLine(cleaned, current, False))
    return output


def _normalize_heading(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z ]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _flexible_phrase(value: str) -> str:
    words = re.findall(r"[a-z]+", value.lower().replace("&", " and "))
    return r"\s+".join(re.escape(word) for word in words)


def _mostly_upper(value: str) -> bool:
    letters = [character for character in value if character.isalpha()]
    return bool(letters) and sum(character.isupper() for character in letters) / len(letters) >= 0.8
