from __future__ import annotations

import re
from dataclasses import dataclass

from .job_research import JobRequirements
from .ontology import extract_skills
from .profile import CandidateSnapshot


TEMPLATE_VERSION = "about-v1.1.0"


@dataclass(frozen=True)
class TemplateSpec:
    template_id: str
    text: str
    stages: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    required: tuple[str, ...] = ("CAREER_STAGE", "ROLE_TITLE", "SKILLS")


@dataclass(frozen=True)
class AboutResult:
    text: str
    template_id: str
    evidence: list[str]


TEMPLATES: tuple[TemplateSpec, ...] = (
    TemplateSpec(
        "T01",
        "<ABOUT_ME>. Currently completing <EDUCATION_STATUS> with <SEMESTERS_LEFT> remaining. Verified profile evidence covers <SKILLS> and includes <PROJECT_HIGHLIGHT>. Seeking a <ROLE_TITLE> opportunity focused on <DOMAIN>.",
        ("student",),
        required=("ABOUT_ME", "EDUCATION_STATUS", "SEMESTERS_LEFT", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T02",
        "<CAREER_STAGE> developer with verified profile evidence in <SKILLS> and a focus on <DOMAIN>. Seeking a <ROLE_TITLE> position where these documented skills align with the requirements listed in the posting.",
    ),
    TemplateSpec(
        "T03",
        "<ABOUT_ME>, currently completing <EDUCATION_STATUS> with <SEMESTERS_LEFT> remaining. Verified project evidence covers <SKILLS> and includes <PROJECT_HIGHLIGHT>. Availability: <AVAILABILITY>. Interested in contributing these skills as a <ROLE_TITLE>.",
        ("student",),
        required=("ABOUT_ME", "EDUCATION_STATUS", "SEMESTERS_LEFT", "AVAILABILITY", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T04",
        "<EDUCATION_STATUS> candidate targeting <ROLE_TITLE> opportunities. Verified profile evidence includes <SKILLS>, <PROJECT_HIGHLIGHT>, and practical use of <TOOLS>. Interested in learning and contributing in <DOMAIN>.",
        ("student", "new graduate"),
        ("internship", "student"),
        ("EDUCATION_STATUS", "ROLE_TITLE", "SKILLS", "PROJECT_HIGHLIGHT", "TOOLS", "DOMAIN"),
    ),
    TemplateSpec(
        "T05",
        "New graduate in <EDUCATION_STATUS> with verified project evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> role in <DOMAIN> that lists these skills.",
        ("new graduate",),
        required=("EDUCATION_STATUS", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T06",
        "Junior software developer with verified evidence in <SKILLS> and a focus on <DOMAIN>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Looking to contribute as a <ROLE_TITLE> while continuing to learn.",
        ("junior", "new graduate"),
        required=("SKILLS", "DOMAIN", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T07",
        "<ABOUT_ME> with verified project evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> role where this project work is relevant.",
        ("student", "new graduate", "candidate"),
        required=("ABOUT_ME", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T08",
        "<CAREER_STAGE> developer targeting backend work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT>, practical use of <TOOLS><PROJECT_IMPACT>, and evidence for <STRENGTHS>. Targeting a <ROLE_TITLE> position involving APIs, data systems, and <DOMAIN>.",
        roles=("backend",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "TOOLS", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T09",
        "<CAREER_STAGE> developer targeting frontend work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> role focused on user-facing work in <DOMAIN>.",
        roles=("frontend",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T10",
        "<CAREER_STAGE> developer targeting full-stack work, with verified evidence across <SKILLS>. The profile includes <PROJECT_HIGHLIGHT>, practical use of <TOOLS><PROJECT_IMPACT>, and evidence for <STRENGTHS>. Interested in a <ROLE_TITLE> role spanning data, APIs, and user-facing implementation.",
        roles=("full-stack", "software"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "TOOLS", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T11",
        "<CAREER_STAGE> developer targeting embedded software, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> role focused on <DOMAIN> products.",
        roles=("embedded", "embedded/systems", "systems"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T12",
        "<CAREER_STAGE> developer targeting mobile work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT>, practical use of <TOOLS><PROJECT_IMPACT>, and evidence for <STRENGTHS>. Targeting a <ROLE_TITLE> position focused on mobile applications.",
        roles=("mobile",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "TOOLS", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T13",
        "<CAREER_STAGE> developer targeting data work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> role focused on data systems in <DOMAIN>.",
        roles=("data",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T14",
        "<CAREER_STAGE> candidate targeting machine-learning work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Interested in a <ROLE_TITLE> role applying ML methods to <DOMAIN> problems.",
        roles=("ml", "ai/data"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T15",
        "<CAREER_STAGE> engineer targeting cloud and automation work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> position focused on delivery and operations.",
        roles=("cloud", "devops"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T16",
        "<CAREER_STAGE> engineer targeting quality work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Targeting a <ROLE_TITLE> role focused on test design and automation.",
        roles=("qa", "testing"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T17",
        "<CAREER_STAGE> candidate targeting security work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> role focused on systems in <DOMAIN>.",
        roles=("security",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T18",
        "<EDUCATION_STATUS> candidate targeting <DOMAIN> work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Interested in a <ROLE_TITLE> role connecting analysis with software implementation.",
        roles=("research", "engineering"),
        required=("EDUCATION_STATUS", "DOMAIN", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T19",
        "<CAREER_STAGE> developer with verified evidence in <SKILLS> and a public project reference for <OPEN_SOURCE_HIGHLIGHT>. The profile also contains supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> role in <DOMAIN>.",
        required=("CAREER_STAGE", "SKILLS", "OPEN_SOURCE_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T20",
        "<CAREER_STAGE> engineer targeting product or platform work, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> role where these skills support product outcomes.",
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T21",
        "<CAREER_STAGE> engineer with verified profile evidence across <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Interested in a <ROLE_TITLE> role where this combination of skills is relevant.",
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T22",
        "Software engineer with <YEARS_EXPERIENCE> of recorded experience and verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>. Targeting a <ROLE_TITLE> position working on systems in <INDUSTRY>.",
        ("mid-level", "experienced"),
        required=("YEARS_EXPERIENCE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "INDUSTRY"),
    ),
    TemplateSpec(
        "T23",
        "<ROLE_TITLE> candidate with <YEARS_EXPERIENCE> of recorded professional experience and verified evidence in <DOMAIN> and <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and supporting evidence for <STRENGTHS>.",
        ("mid-level", "experienced"),
        required=("ROLE_TITLE", "YEARS_EXPERIENCE", "DOMAIN", "SKILLS", "PROJECT_HIGHLIGHT", "INDUSTRY"),
    ),
    TemplateSpec(
        "T24",
        "<ABOUT_ME> transitioning into <DOMAIN>, with verified evidence in <SKILLS>. The profile includes <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, <EDUCATION_STATUS>, and supporting evidence for <STRENGTHS>. Seeking a <ROLE_TITLE> opportunity where these documented skills are relevant.",
        ("career changer",),
        required=("ABOUT_ME", "DOMAIN", "SKILLS", "PROJECT_HIGHLIGHT", "EDUCATION_STATUS", "ROLE_TITLE"),
    ),
)


def build_about(
    candidate: CandidateSnapshot,
    role_title: str,
    requirements: JobRequirements,
) -> AboutResult:
    ordered_skills = _ordered_skills(candidate, requirements)
    project = _best_project(candidate, requirements)
    values = _values(candidate, role_title, requirements, ordered_skills, project)
    eligible = [
        template
        for template in TEMPLATES
        if all(values.get(key) for key in template.required)
        and _template_applicable(template, candidate, requirements, role_title, values)
    ]
    ranked = sorted(
        eligible or [TEMPLATES[1]],
        key=lambda template: (
            -_selection_score(template, candidate, requirements, role_title, values),
            template.template_id,
        ),
    )
    for template in ranked:
        rendered = _render(template.text, values)
        if rendered and not re.search(r"<[A-Z_]+>", rendered) and 30 <= len(rendered.split()) <= 90:
            evidence = [
                item.evidence
                for skill in ordered_skills[:5]
                if (item := candidate.skill_evidence.get(skill)) is not None
            ]
            if project:
                evidence.append(candidate.project_evidence.get(project, project))
            return AboutResult(rendered, template.template_id, _dedupe(evidence)[:8])
    raise ValueError("No About template could be rendered from the available evidence.")


def _values(
    candidate: CandidateSnapshot,
    role_title: str,
    requirements: JobRequirements,
    skills: list[str],
    project: str,
) -> dict[str, str]:
    top_skills = skills[:5]
    tools = skills[3:7] or top_skills[:3]
    domain = _normalize_domain(requirements.domain or candidate.domain)
    return {
        "ABOUT_ME": _clean(candidate.about_me),
        "ROLE_TITLE": _clean(role_title or "software developer"),
        "CAREER_STAGE": _clean(candidate.career_stage),
        "SKILLS": _join(top_skills),
        "TOOLS": _join(tools),
        "DOMAIN": domain,
        "EDUCATION_STATUS": _clean(candidate.education),
        "SEMESTERS_LEFT": (
            f"{candidate.semesters_left} semesters" if candidate.semesters_left is not None else ""
        ),
        "YEARS_EXPERIENCE": (
            f"{candidate.years_experience:g}+ years" if candidate.years_experience > 0 else ""
        ),
        "PROJECT_HIGHLIGHT": _project_highlight(project),
        "PROJECT_IMPACT": "",
        "STRENGTHS": _strengths(candidate, requirements),
        "OPEN_SOURCE_HIGHLIGHT": _clean(project) if "github" in candidate.project_evidence.get(project, "").lower() else "",
        "INDUSTRY": _clean(requirements.domain or candidate.domain),
        "CAREER_GOAL": _clean(role_title),
        "AVAILABILITY": _clean(candidate.availability),
        "LANGUAGES": _join(candidate.languages),
    }


def _selection_score(
    template: TemplateSpec,
    candidate: CandidateSnapshot,
    requirements: JobRequirements,
    role_title: str,
    values: dict[str, str],
) -> int:
    score = 0
    role = _normalize_domain(requirements.domain)
    role_lower = role_title.casefold()
    internship_role = re.search(r"\b(?:intern(?:ship)?|student)\b", role_lower) is not None
    if template.stages:
        score += 5 if candidate.career_stage in template.stages else -4
    if template.roles:
        role_matches = role in template.roles
        if template.template_id == "T04":
            # Internship is a seniority signal in the title, not a technical
            # domain. A Backend Intern should not need a fake `internship`
            # domain for the student-specific template to be reachable.
            role_matches = role_matches or internship_role
        score += 7 if role_matches else -5
    if "PROJECT_HIGHLIGHT" in template.required and candidate.projects:
        score += 2
    if template.template_id == "T02":
        score += 1
    if template.template_id == "T03" and candidate.availability and requirements.availability:
        score += 8
    if template.template_id == "T19" and values.get("OPEN_SOURCE_HIGHLIGHT"):
        score += 10
    if template.template_id == "T20" and re.search(r"\b(?:product|platform)\b", role_lower):
        score += 9
    if (
        template.template_id == "T21"
        and len(candidate.skills) >= 7
        and any(term in role_lower for term in ("generalist", "versatile", "multidisciplinary"))
    ):
        score += 8
    if (
        template.template_id == "T23"
        and candidate.years_experience >= 5
        and _normalize_domain(candidate.domain) == _normalize_domain(requirements.domain)
    ):
        score += 3
    if (
        template.template_id == "T24"
        and candidate.career_stage == "career changer"
        and candidate.domain
        and requirements.domain
        and _normalize_domain(candidate.domain) != _normalize_domain(requirements.domain)
    ):
        score += 10
    return score


def _template_applicable(
    template: TemplateSpec,
    candidate: CandidateSnapshot,
    requirements: JobRequirements,
    role_title: str,
    values: dict[str, str],
) -> bool:
    """Keep claim-bearing specialty templates behind their evidence signals."""

    role_lower = role_title.casefold()
    if template.template_id == "T03":
        return bool(candidate.availability and requirements.availability)
    if template.template_id == "T19":
        return bool(values.get("OPEN_SOURCE_HIGHLIGHT"))
    if template.template_id == "T20":
        return re.search(r"\b(?:product|platform)\b", role_lower) is not None
    if template.template_id == "T21":
        return len(candidate.skills) >= 7 and any(
            term in role_lower for term in ("generalist", "versatile", "multidisciplinary")
        )
    if template.template_id == "T23":
        return bool(
            candidate.years_experience >= 5
            and candidate.domain
            and requirements.domain
            and _normalize_domain(candidate.domain) == _normalize_domain(requirements.domain)
        )
    if template.template_id == "T24":
        return bool(
            candidate.career_stage == "career changer"
            and candidate.domain
            and requirements.domain
            and _normalize_domain(candidate.domain) != _normalize_domain(requirements.domain)
        )
    return True


def _ordered_skills(candidate: CandidateSnapshot, requirements: JobRequirements) -> list[str]:
    job_order = _dedupe(
        [
            *requirements.must_have_skills,
            *requirements.preferred_skills,
            *requirements.nice_to_have_skills,
            *requirements.all_skills,
        ]
    )
    matched = [skill for skill in job_order if skill in candidate.skills]
    remaining = sorted(
        (skill for skill in candidate.skills if skill not in matched),
        key=lambda skill: (-candidate.skill_evidence[skill].strength, skill),
    )
    return [*matched, *remaining]


def _best_project(candidate: CandidateSnapshot, requirements: JobRequirements) -> str:
    job_skills = set(requirements.all_skills)
    ranked: list[tuple[int, int, str]] = []
    for project in candidate.projects:
        overlap = len(set(extract_skills(project)) & job_skills)
        ranked.append((overlap, len(extract_skills(project)), project))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2].lower()))
    return ranked[0][2] if ranked else ""


def _strengths(candidate: CandidateSnapshot, requirements: JobRequirements) -> str:
    ordered = _ordered_skills(candidate, requirements)
    # Strength statements must be backed by approved skill evidence. Do not
    # infer traits such as ownership, reliability, or leadership from a domain.
    evidenced = [skill for skill in ordered if skill in candidate.skill_evidence]
    return _join(evidenced[:4]) or "reviewed project work"


def _render(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"<{key}>", value)
    rendered = re.sub(r"\s+", " ", rendered)
    rendered = re.sub(r"\s+([,.;:])", r"\1", rendered)
    rendered = re.sub(r"([,;])\s*([,.;])", r"\2", rendered)
    rendered = rendered.replace("..", ".").strip(" ,;")
    return rendered[:1].upper() + rendered[1:] if rendered else ""


def _normalize_domain(value: str) -> str:
    lower = value.lower().strip()
    if lower in {"embedded/systems", "systems"}:
        return "embedded"
    if lower in {"ai/data", "machine learning"}:
        return "ml"
    return lower or "software"


def _join(values: list[str]) -> str:
    cleaned = [_clean(value) for value in values if _clean(value)]
    if len(cleaned) < 2:
        return cleaned[0] if cleaned else ""
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _clean(value: str) -> str:
    return re.sub(r"[\x00-\x1f<>]+|\s+", " ", value or "").strip(" .,:;-")


def _project_highlight(value: str) -> str:
    cleaned = _clean(value)
    if ":" in cleaned:
        title, _ = cleaned.split(":", 1)
        if 2 <= len(title.strip()) <= 80:
            return title.strip()
    return re.sub(
        r"^(?:built|developed|implemented|created|designed|engineered|delivered)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return output
