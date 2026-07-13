from __future__ import annotations

import re
from dataclasses import dataclass

from .job_research import JobRequirements
from .ontology import extract_skills
from .profile import CandidateSnapshot


TEMPLATE_VERSION = "about-v1.0.0"


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
        "<ABOUT_ME>. <EDUCATION_STATUS> with <SEMESTERS_LEFT> remaining and hands-on project experience in <SKILLS>. Built <PROJECT_HIGHLIGHT>, demonstrating <STRENGTHS>, and seeking a <ROLE_TITLE> opportunity focused on <DOMAIN>.",
        ("student",),
        required=("ABOUT_ME", "EDUCATION_STATUS", "SEMESTERS_LEFT", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T02",
        "<CAREER_STAGE> developer with evidence-backed knowledge of <SKILLS> and a focus on <DOMAIN>. Seeking a <ROLE_TITLE> position where practical engineering fundamentals and <STRENGTHS> can support reliable software delivery.",
    ),
    TemplateSpec(
        "T03",
        "<ABOUT_ME>, currently completing <EDUCATION_STATUS> with <SEMESTERS_LEFT> remaining. Available <AVAILABILITY> and experienced in building projects with <SKILLS>, including <PROJECT_HIGHLIGHT>. Interested in contributing these skills as a <ROLE_TITLE>.",
        ("student",),
        required=("ABOUT_ME", "EDUCATION_STATUS", "SEMESTERS_LEFT", "AVAILABILITY", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T04",
        "<EDUCATION_STATUS> candidate seeking a <ROLE_TITLE> internship, with applied experience in <SKILLS>. Through <PROJECT_HIGHLIGHT>, developed <STRENGTHS> and practical familiarity with <TOOLS>, with a focus on learning and contributing in <DOMAIN>.",
        ("student", "new graduate"),
        ("internship", "student"),
        ("EDUCATION_STATUS", "ROLE_TITLE", "SKILLS", "PROJECT_HIGHLIGHT", "TOOLS", "DOMAIN"),
    ),
    TemplateSpec(
        "T05",
        "New graduate in <EDUCATION_STATUS> with project-based experience in <SKILLS>. Delivered <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and developed strengths in <STRENGTHS>. Seeking a <ROLE_TITLE> role in <DOMAIN> where this foundation can translate into production impact.",
        ("new graduate",),
        required=("EDUCATION_STATUS", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T06",
        "Junior software developer with evidence-backed experience in <SKILLS> and a focus on <DOMAIN>. Built <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, demonstrating <STRENGTHS>. Looking to contribute as a <ROLE_TITLE> while continuing to deepen production engineering experience.",
        ("junior", "new graduate"),
        required=("SKILLS", "DOMAIN", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T07",
        "<ABOUT_ME> with strong project-based experience in <SKILLS>. Designed and implemented <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, providing practical evidence of <STRENGTHS>. Seeking a <ROLE_TITLE> role where demonstrated ability can grow into professional experience.",
        ("student", "new graduate", "candidate"),
        required=("ABOUT_ME", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T08",
        "Backend-focused <CAREER_STAGE> developer experienced with <SKILLS>. Built <PROJECT_HIGHLIGHT> using <TOOLS><PROJECT_IMPACT>, with emphasis on <STRENGTHS>. Targeting a <ROLE_TITLE> position involving reliable APIs, data systems, and <DOMAIN>.",
        roles=("backend",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "TOOLS", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T09",
        "Frontend-focused <CAREER_STAGE> developer working with <SKILLS>. Created <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, demonstrating <STRENGTHS> across interface implementation and application behavior. Seeking a <ROLE_TITLE> role building clear, reliable user experiences in <DOMAIN>.",
        roles=("frontend",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T10",
        "Full-stack <CAREER_STAGE> developer with practical experience across <SKILLS>. Delivered <PROJECT_HIGHLIGHT> using <TOOLS><PROJECT_IMPACT>, showing <STRENGTHS> from data and API design through user-facing implementation. Interested in a <ROLE_TITLE> role with end-to-end ownership.",
        roles=("full-stack", "software"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "TOOLS", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T11",
        "Embedded-software <CAREER_STAGE> developer with experience in <SKILLS>. Built <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, demonstrating <STRENGTHS> in low-level development, debugging, and system behavior. Seeking a <ROLE_TITLE> role focused on dependable <DOMAIN> products.",
        roles=("embedded", "embedded/systems", "systems"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T12",
        "Mobile-focused <CAREER_STAGE> developer experienced in <SKILLS>. Developed <PROJECT_HIGHLIGHT> with <TOOLS><PROJECT_IMPACT>, building strengths in <STRENGTHS>. Targeting a <ROLE_TITLE> position delivering stable, user-centered mobile applications.",
        roles=("mobile",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "TOOLS", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T13",
        "Data-focused <CAREER_STAGE> developer with hands-on experience in <SKILLS>. Implemented <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, demonstrating <STRENGTHS> in data processing, storage, and reliability. Seeking a <ROLE_TITLE> role supporting trustworthy data systems in <DOMAIN>.",
        roles=("data",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T14",
        "Machine-learning <CAREER_STAGE> candidate with applied experience in <SKILLS>. Developed <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, showing strengths in <STRENGTHS> and responsible evaluation. Interested in a <ROLE_TITLE> role applying ML methods to practical <DOMAIN> problems.",
        roles=("ml", "ai/data"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T15",
        "Cloud and automation-focused <CAREER_STAGE> engineer with evidence in <SKILLS>. Built <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, with attention to <STRENGTHS>. Seeking a <ROLE_TITLE> position improving delivery and reliability.",
        roles=("cloud", "devops"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T16",
        "Quality-focused <CAREER_STAGE> engineer with experience in <SKILLS>. Created <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, demonstrating <STRENGTHS> in test design, automation, and defect prevention. Targeting a <ROLE_TITLE> role that values reliable software and measurable quality.",
        roles=("qa", "testing"),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T17",
        "Security-focused <CAREER_STAGE> candidate experienced in <SKILLS>. Completed <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, providing evidence of <STRENGTHS> in secure implementation and technical investigation. Seeking a <ROLE_TITLE> role protecting systems in <DOMAIN>.",
        roles=("security",),
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T18",
        "<EDUCATION_STATUS> candidate focused on <DOMAIN>, with experience in <SKILLS>. Through <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, demonstrated <STRENGTHS> in analytical problem-solving, experimentation, and implementation. Interested in a <ROLE_TITLE> role connecting rigorous analysis with working software.",
        roles=("research", "engineering"),
        required=("EDUCATION_STATUS", "DOMAIN", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T19",
        "<CAREER_STAGE> developer with practical experience in <SKILLS> and public work through <OPEN_SOURCE_HIGHLIGHT>. Contributions demonstrate <STRENGTHS> and familiarity with collaborative engineering workflows. Seeking a <ROLE_TITLE> role in <DOMAIN>.",
        required=("CAREER_STAGE", "SKILLS", "OPEN_SOURCE_HIGHLIGHT", "ROLE_TITLE", "DOMAIN"),
    ),
    TemplateSpec(
        "T20",
        "Product-minded <CAREER_STAGE> engineer experienced in <SKILLS>. Delivered <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, balancing implementation with <STRENGTHS>. Seeking a <ROLE_TITLE> role where technical decisions connect directly to useful and reliable product outcomes.",
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T21",
        "Adaptable <CAREER_STAGE> engineer with hands-on experience across <SKILLS>. Took ownership of <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, demonstrating <STRENGTHS> from problem definition through delivery. Interested in a <ROLE_TITLE> role requiring broad contribution and fast iteration.",
        required=("CAREER_STAGE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE"),
    ),
    TemplateSpec(
        "T22",
        "Software engineer with <YEARS_EXPERIENCE> of confirmed experience in <SKILLS>. Contributed to <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, with strengths in <STRENGTHS>, maintainability, and dependable delivery. Targeting a <ROLE_TITLE> position supporting reliable systems in <INDUSTRY>.",
        ("mid-level", "experienced"),
        required=("YEARS_EXPERIENCE", "SKILLS", "PROJECT_HIGHLIGHT", "ROLE_TITLE", "INDUSTRY"),
    ),
    TemplateSpec(
        "T23",
        "<ROLE_TITLE> candidate with <YEARS_EXPERIENCE> of professional experience focused on <DOMAIN> and <SKILLS>. Delivered <PROJECT_HIGHLIGHT><PROJECT_IMPACT>, demonstrating <STRENGTHS>. Brings relevant <INDUSTRY> context and a record of evidence-backed technical contribution.",
        ("mid-level", "experienced"),
        required=("ROLE_TITLE", "YEARS_EXPERIENCE", "DOMAIN", "SKILLS", "PROJECT_HIGHLIGHT", "INDUSTRY"),
    ),
    TemplateSpec(
        "T24",
        "<ABOUT_ME> transitioning into <DOMAIN> with focused experience in <SKILLS>. Built <PROJECT_HIGHLIGHT><PROJECT_IMPACT> and developed <STRENGTHS> through practical work and <EDUCATION_STATUS>. Seeking a <ROLE_TITLE> opportunity where transferable experience and demonstrated technical ability are relevant.",
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
    eligible = [template for template in TEMPLATES if all(values.get(key) for key in template.required)]
    ranked = sorted(
        eligible or [TEMPLATES[1]],
        key=lambda template: (-_selection_score(template, candidate, requirements), template.template_id),
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


def _selection_score(template: TemplateSpec, candidate: CandidateSnapshot, requirements: JobRequirements) -> int:
    score = 0
    role = _normalize_domain(requirements.domain)
    if template.stages:
        score += 5 if candidate.career_stage in template.stages else -4
    if template.roles:
        score += 7 if role in template.roles else -5
    if "PROJECT_HIGHLIGHT" in template.required and candidate.projects:
        score += 2
    if template.template_id == "T02":
        score += 1
    return score


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
    domain = _normalize_domain(requirements.domain or candidate.domain)
    return {
        "embedded": "implementation, debugging, and systems thinking",
        "backend": "API implementation and data handling",
        "frontend": "interface implementation and application behavior",
        "data": "data processing and reliable pipelines",
        "ml": "experimentation, evaluation, and implementation",
        "cloud": "automation, deployment, and reliability",
        "qa": "test design and defect prevention",
        "security": "secure implementation and technical investigation",
        "mobile": "application implementation and user-focused delivery",
    }.get(domain, "implementation, testing, and problem-solving")


def _render(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"<{key}>", value)
    rendered = re.sub(r"\s+", " ", rendered)
    rendered = re.sub(r"\s+([,.;:])", r"\1", rendered)
    rendered = re.sub(r"([,;])\s*([,.;])", r"\2", rendered)
    rendered = rendered.replace("..", ".").strip(" ,;")
    return rendered


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
