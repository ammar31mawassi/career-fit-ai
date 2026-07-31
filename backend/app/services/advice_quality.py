from __future__ import annotations

import re
from dataclasses import dataclass

from .job_research import JobRequirements
from .profile import CandidateSnapshot


OUTPUT_POLICY_VERSION = "resume-output-v1.0.0"
PROJECT_EVIDENCE_PROMPT = (
    "Add one or two verified projects with concrete implementation details and outcomes."
)


@dataclass(frozen=True)
class OutputQualityFinding:
    code: str
    severity: str
    message: str
    excerpt: str = ""

    def public_dict(self) -> dict[str, str]:
        # Excerpts can contain private profile text. Persist only the stable,
        # explainable code and message in workflow and match metadata.
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class OutputQualityReport:
    policy_version: str
    passed: bool
    repaired: bool
    evidence_count: int
    findings: tuple[OutputQualityFinding, ...]

    def public_dict(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "passed": self.passed,
            "repaired": self.repaired,
            "evidence_count": self.evidence_count,
            "hard_error_count": sum(item.severity == "error" for item in self.findings),
            "warning_codes": [item.code for item in self.findings if item.severity == "warning"],
            "findings": [item.public_dict() for item in self.findings],
        }


@dataclass(frozen=True)
class CheckedResumeAdvice:
    projects: list[str]
    skill_order: list[str]
    about_text: str
    evidence: list[str]
    report: OutputQualityReport


_VAGUE_CLAIMS: tuple[tuple[str, str], ...] = (
    ("production impact", "The summary makes a broad production-impact claim without a linked outcome."),
    ("responsible evaluation", "The summary names an evaluation quality that may not be supported by profile evidence."),
    ("end-to-end ownership", "The summary claims end-to-end ownership without a linked ownership fact."),
    ("measurable quality", "The summary claims measurable quality without a linked measure."),
    ("proven track record", "The summary uses a broad track-record claim instead of a specific fact."),
    ("world-class", "The summary uses an uncheckable superlative."),
    ("game-changing", "The summary uses an uncheckable impact claim."),
    ("cutting-edge", "The summary uses a vague novelty claim."),
)


def enforce_resume_advice(
    candidate: CandidateSnapshot,
    role: str,
    requirements: JobRequirements,
    *,
    projects: list[str],
    skill_order: list[str],
    about_text: str,
    evidence: list[str],
) -> CheckedResumeAdvice:
    """Validate and safely repair scorer-produced resume advice.

    This boundary is intentionally independent from fit scoring. It may remove
    or repair unsupported writing, but it never changes a match score, blocker,
    confidence value, or eligibility decision.
    """

    initial = assess_resume_advice(
        candidate,
        role,
        requirements,
        projects=projects,
        skill_order=skill_order,
        about_text=about_text,
        evidence=evidence,
    )
    initial_errors = [item for item in initial.findings if item.severity == "error"]
    if not initial_errors:
        return CheckedResumeAdvice(projects, skill_order, about_text, evidence, initial)

    repaired_projects = _supported_projects(candidate, projects)
    repaired_skills = _supported_skills(candidate, skill_order)
    repaired_evidence = _supported_evidence(candidate, evidence)
    structural_codes = {
        "empty_summary",
        "invalid_length",
        "unresolved_placeholder",
        "unexpected_markup",
        "control_character",
        "duplicate_word",
        "unsupported_number",
        "missing_evidence",
    }
    repaired_about = (
        _fallback_about(candidate, role, requirements)
        if any(item.code in structural_codes for item in initial_errors)
        else about_text
    )
    if not repaired_evidence:
        repaired_evidence = _allowed_evidence(candidate)[:5]

    final = assess_resume_advice(
        candidate,
        role,
        requirements,
        projects=repaired_projects,
        skill_order=repaired_skills,
        about_text=repaired_about,
        evidence=repaired_evidence,
    )
    final_errors = [item for item in final.findings if item.severity == "error"]
    if final_errors:
        # Candidate-controlled source text can itself contain malformed markup
        # or duplicated words. The last fallback uses only cleaned field values.
        repaired_about = _minimal_fallback(candidate, role)
        final = assess_resume_advice(
            candidate,
            role,
            requirements,
            projects=repaired_projects,
            skill_order=repaired_skills,
            about_text=repaired_about,
            evidence=repaired_evidence,
        )
        final_errors = [item for item in final.findings if item.severity == "error"]
    if final_errors:
        raise ValueError("Resume advice could not satisfy the evidence and clarity policy.")

    repair_findings = tuple(
        OutputQualityFinding(
            code=f"repaired_{item.code}",
            severity="warning",
            message=f"CareerFit repaired an output that failed the {item.code.replace('_', ' ')} check.",
        )
        for item in initial_errors
    )
    final_warnings = tuple(item for item in final.findings if item.severity == "warning")
    report = OutputQualityReport(
        policy_version=OUTPUT_POLICY_VERSION,
        passed=True,
        repaired=True,
        evidence_count=len(repaired_evidence),
        findings=(*repair_findings, *final_warnings),
    )
    return CheckedResumeAdvice(
        repaired_projects,
        repaired_skills,
        repaired_about,
        repaired_evidence,
        report,
    )


def assess_resume_advice(
    candidate: CandidateSnapshot,
    role: str,
    requirements: JobRequirements,
    *,
    projects: list[str],
    skill_order: list[str],
    about_text: str,
    evidence: list[str],
) -> OutputQualityReport:
    findings: list[OutputQualityFinding] = []
    stripped = about_text.strip()
    words = stripped.split()

    if not stripped:
        findings.append(_error("empty_summary", "The suggested summary is empty."))
    elif not 8 <= len(words) <= 120:
        findings.append(
            _error(
                "invalid_length",
                "The suggested summary must contain between 8 and 120 words.",
            )
        )
    placeholder = re.search(r"<[A-Z][A-Z0-9_]*>", stripped)
    if placeholder:
        findings.append(
            _error(
                "unresolved_placeholder",
                "The suggested summary contains an unresolved template field.",
                placeholder.group(0),
            )
        )
    markup = re.search(r"<\s*/?\s*[a-zA-Z][^>]*>", stripped)
    if markup:
        findings.append(
            _error(
                "unexpected_markup",
                "The suggested summary contains unexpected markup.",
                markup.group(0),
            )
        )
    control = re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", stripped)
    if control:
        findings.append(
            _error("control_character", "The suggested summary contains a control character.")
        )
    duplicate = re.search(r"\b([A-Za-z][A-Za-z0-9+.#'-]*)\s+\1\b", stripped, re.IGNORECASE)
    if duplicate:
        findings.append(
            _error(
                "duplicate_word",
                "The suggested summary repeats the same word consecutively.",
                duplicate.group(0),
            )
        )

    supported_projects = {_normalized(item) for item in candidate.projects}
    for project in projects:
        if project != PROJECT_EVIDENCE_PROMPT and _normalized(project) not in supported_projects:
            findings.append(
                _error(
                    "unsupported_project",
                    "A recommended project is not present in the verified profile.",
                    project,
                )
            )

    supported_skills = {_normalized(item) for item in candidate.skills}
    for skill in skill_order:
        if _normalized(skill) not in supported_skills:
            findings.append(
                _error(
                    "unsupported_skill",
                    "A recommended skill is not present in the verified profile.",
                    skill,
                )
            )

    allowed_evidence = {_normalized(item) for item in _allowed_evidence(candidate)}
    for item in evidence:
        if _normalized(item) not in allowed_evidence:
            findings.append(
                _error(
                    "unsupported_evidence",
                    "An evidence anchor is not present in the verified profile.",
                    item,
                )
            )
    if allowed_evidence and not evidence:
        findings.append(
            _error(
                "missing_evidence",
                "The suggested summary is not linked to any verified profile evidence.",
            )
        )

    authorized_text = " ".join(
        [
            role,
            requirements.domain,
            candidate.education,
            candidate.about_me,
            candidate.summary,
            f"{candidate.semesters_left}" if candidate.semesters_left is not None else "",
            f"{candidate.years_experience:g}",
            f"{candidate.internship_years:g}",
            *candidate.skills,
            *candidate.projects,
            *_allowed_evidence(candidate),
        ]
    )
    authorized_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", authorized_text))
    for number in re.findall(r"\b\d+(?:\.\d+)?%?\b", stripped):
        if number not in authorized_numbers:
            findings.append(
                _error(
                    "unsupported_number",
                    "The suggested summary introduces a number that is not present in an authorized source.",
                    number,
                )
            )

    lower = stripped.lower()
    for phrase, message in _VAGUE_CLAIMS:
        if phrase in lower:
            findings.append(_warning("vague_claim", message, phrase))
    if re.search(r"\bin today(?:'|\u2019)s\b.{0,45}\blandscape\b", lower):
        findings.append(
            _warning(
                "formulaic_intro",
                "The summary opens with generic market framing instead of candidate evidence.",
            )
        )
    if re.search(r"\bnot (?:just|only)\b.{0,80}\bbut (?:also )?\b", lower):
        findings.append(
            _warning(
                "formulaic_contrast",
                "The summary uses a formulaic contrast that can usually be stated more directly.",
            )
        )

    errors = [item for item in findings if item.severity == "error"]
    return OutputQualityReport(
        policy_version=OUTPUT_POLICY_VERSION,
        passed=not errors,
        repaired=False,
        evidence_count=len(evidence),
        findings=tuple(_dedupe_findings(findings)),
    )


def _supported_projects(candidate: CandidateSnapshot, values: list[str]) -> list[str]:
    canonical = {_normalized(item): item for item in candidate.projects}
    output = [canonical[key] for value in values if (key := _normalized(value)) in canonical]
    output = _dedupe(output)
    if output:
        return output[:3]
    return candidate.projects[:3] or [PROJECT_EVIDENCE_PROMPT]


def _supported_skills(candidate: CandidateSnapshot, values: list[str]) -> list[str]:
    canonical = {_normalized(item): item for item in candidate.skills}
    output = [canonical[key] for value in values if (key := _normalized(value)) in canonical]
    remaining = sorted(
        (skill for skill in candidate.skills if _normalized(skill) not in {_normalized(item) for item in output}),
        key=lambda skill: (-candidate.skill_evidence[skill].strength, skill),
    )
    return _dedupe([*output, *remaining])[:12]


def _supported_evidence(candidate: CandidateSnapshot, values: list[str]) -> list[str]:
    canonical = {_normalized(item): item for item in _allowed_evidence(candidate)}
    return _dedupe(
        [canonical[key] for value in values if (key := _normalized(value)) in canonical]
    )[:8]


def _allowed_evidence(candidate: CandidateSnapshot) -> list[str]:
    return _dedupe(
        [
            *(item.evidence for item in candidate.skill_evidence.values()),
            *candidate.project_evidence.values(),
        ]
    )


def _fallback_about(
    candidate: CandidateSnapshot,
    role: str,
    requirements: JobRequirements,
) -> str:
    ordered_skills = sorted(
        candidate.skills,
        key=lambda skill: (-candidate.skill_evidence[skill].strength, skill),
    )
    skills = _human_join([_clean(item) for item in ordered_skills[:4]])
    stage = _clean(candidate.career_stage).capitalize() or "Candidate"
    target = _clean(role) or "this role"
    domain = _clean(requirements.domain)
    first = (
        f"{stage} candidate with verified profile evidence in {skills}."
        if skills
        else f"{stage} candidate with a reviewed CareerFit profile."
    )
    second = f"Targeting {target} opportunities"
    if domain and domain != "software":
        second += f" focused on {domain}"
    return _remove_duplicate_words(f"{first} {second}.")


def _minimal_fallback(candidate: CandidateSnapshot, role: str) -> str:
    ordered_skills = sorted(candidate.skills)[:4]
    skills = _human_join([_clean(item) for item in ordered_skills])
    target = _clean(role) or "the selected role"
    if skills:
        return _remove_duplicate_words(
            f"Candidate profile includes verified evidence for {skills}. Review those facts before using this summary for {target}."
        )
    return _remove_duplicate_words(
        f"CareerFit needs more verified profile evidence before suggesting a summary for {target}."
    )


def _clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"[\x00-\x1f\x7f]+|\s+", " ", value)
    return value.strip(" .,:;-")


def _remove_duplicate_words(value: str) -> str:
    previous = None
    while value != previous:
        previous = value
        value = re.sub(
            r"\b([A-Za-z][A-Za-z0-9+.#'-]*)\s+\1\b",
            r"\1",
            value,
            flags=re.IGNORECASE,
        )
    return value


def _human_join(values: list[str]) -> str:
    cleaned = [item for item in values if item]
    if len(cleaned) < 2:
        return cleaned[0] if cleaned else ""
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _error(code: str, message: str, excerpt: str = "") -> OutputQualityFinding:
    return OutputQualityFinding(code, "error", message, excerpt)


def _warning(code: str, message: str, excerpt: str = "") -> OutputQualityFinding:
    return OutputQualityFinding(code, "warning", message, excerpt)


def _normalized(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _normalized(value)
        if key and key not in seen:
            seen.add(key)
            output.append(value)
    return output


def _dedupe_findings(values: list[OutputQualityFinding]) -> list[OutputQualityFinding]:
    output: list[OutputQualityFinding] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        key = (value.code, value.excerpt.casefold())
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output
