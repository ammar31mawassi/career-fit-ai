from __future__ import annotations

import re
from dataclasses import replace

from .goozali import GoozaliJob
from .job_research import JobRequirements, classify_requirements


GOOZALI_READER_VERSION = "goozali-reader-v1.0.0"
_SUPPORTED_LANGUAGES = ("english", "hebrew", "arabic", "french", "german", "spanish", "russian")


def classify_goozali_job(job: GoozaliJob) -> JobRequirements:
    """Read a Goozali row with its structured columns as authoritative evidence."""
    return classify_goozali_text(
        job.description_text,
        job.role,
        minimum_experience=job.minimum_experience,
        employment_scope=job.employment_scope,
        location=job.location,
        language_requirements=job.language_requirements,
        education_requirements=job.education_requirements,
    )


def classify_goozali_text(
    text: str,
    role: str,
    *,
    minimum_experience: str = "",
    employment_scope: str = "",
    location: str = "",
    language_requirements: str = "",
    education_requirements: str = "",
) -> JobRequirements:
    """Read stored Goozali text, including labels emitted by the table adapter.

    This path also repairs catalog rows created before structured fields were
    retained separately, so a database backfill is not required for accuracy.
    """
    base = classify_requirements(text, role)
    structured_minimum = _minimum_years(
        minimum_experience or _labeled_value(text, "Minimum experience")
    )
    min_years = base.min_years_experience if structured_minimum is None else structured_minimum
    scope = employment_scope or _labeled_value(text, "Employment scope")
    exact_location = location or _labeled_value(text, "Location")
    language_text = language_requirements or _labeled_value(text, "Language requirements")
    education = education_requirements or _labeled_value(text, "Education requirements")
    languages = _languages(language_text) or base.languages
    availability = _availability(scope) or base.availability
    seniority = _seniority(role, min_years, base.seniority)
    structured_checks = (
        bool(base.all_skills or base.skill_groups),
        bool(base.responsibilities),
        structured_minimum is not None,
        bool(exact_location),
        bool(availability),
        bool(languages),
        bool(education),
    )
    completeness = max(base.extraction_completeness, sum(structured_checks) / len(structured_checks))
    return replace(
        base,
        min_years_experience=min_years,
        experience_requirement_known=(
            structured_minimum is not None or base.experience_requirement_known
        ),
        seniority=seniority,
        education=education or base.education,
        location_requirement=exact_location or base.location_requirement,
        availability=availability,
        languages=languages,
        reader_version=GOOZALI_READER_VERSION,
        extraction_completeness=round(completeness, 3),
    )


def _minimum_years(value: str) -> float | None:
    normalized = value.lower().replace(",", ".").strip()
    if not normalized:
        return None
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    return max(0.0, float(match.group())) if match else None


def _seniority(role: str, min_years: float, fallback: str) -> str:
    title = role.lower()
    if re.search(r"\b(?:senior|staff|principal|lead)\b|\bsr\b\.?", title):
        return "senior"
    if re.search(r"\b(?:student|intern|internship)\b", title):
        return "student"
    if re.search(r"\b(?:junior|entry[ -]level|new grad)\b", title):
        return "junior"
    if min_years >= 3:
        return "experienced"
    if min_years > 0:
        return "junior"
    return fallback


def _labeled_value(text: str, label: str) -> str:
    match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*([^\r\n]+)", text)
    return match.group(1).strip() if match else ""


def _languages(value: str) -> list[str]:
    lower = value.lower()
    return [language for language in _SUPPORTED_LANGUAGES if re.search(rf"\b{language}\b", lower)]


def _availability(value: str) -> str:
    lower = value.lower()
    if "full time" in lower or "full-time" in lower:
        return "full-time"
    if "part time" in lower or "part-time" in lower:
        return "part-time"
    return ""
