from __future__ import annotations

from dataclasses import dataclass

from .advice_quality import PROJECT_EVIDENCE_PROMPT
from .about_templates import AboutResult, build_about
from .job_research import JobRequirements, RequirementGroup
from .ontology import ONTOLOGY_VERSION, extract_skills, skill_match_strength
from .profile import CandidateSnapshot, SkillEvidence


MODEL_VERSION = "fit-v2.4.0"


@dataclass(frozen=True)
class SkillMatch:
    requirement: str
    candidate_skill: str
    transfer_strength: float
    evidence_strength: float
    combined_strength: float
    evidence_type: str
    evidence: str
    fact_id: int | None


@dataclass(frozen=True)
class MatchResult:
    score: float
    fit_level: str
    confidence: float
    matched_evidence: list[str]
    missing_blockers: list[str]
    gaps: list[str]
    projects: list[str]
    skill_order: list[str]
    about_text: str
    about_template_id: str
    about_evidence: list[str]
    model_version: str
    ontology_version: str
    component_scores: dict[str, float]
    applied_caps: list[str]
    feature_snapshot: dict[str, object]


def score_match(
    candidate: CandidateSnapshot,
    company: str,
    role: str,
    requirements: JobRequirements,
    source_confidence: float,
) -> MatchResult:
    del company  # Company identity is intentionally excluded from qualification scoring.
    must = _dedupe(requirements.must_have_skills)
    preferred = _dedupe(requirements.preferred_skills)
    nice = _dedupe(requirements.nice_to_have_skills)
    grouped_skills = [
        skill for group in requirements.skill_groups for skill in group.skills
    ]
    all_job_skills = _dedupe(
        [*must, *preferred, *nice, *grouped_skills, *requirements.all_skills]
    )

    skill_matches = {skill: _best_skill_match(candidate, skill) for skill in all_job_skills}
    must_groups = [group for group in requirements.skill_groups if group.priority == "must"]
    preferred_groups = [
        group for group in requirements.skill_groups if group.priority in {"preferred", "nice"}
    ]
    group_matches = {
        _group_key(group): _best_group_match(group, skill_matches)
        for group in requirements.skill_groups
    }
    core_skills = must or all_job_skills[:5]
    component_scores: dict[str, float] = {}
    component_weights: dict[str, float] = {}

    if core_skills or must_groups:
        must_values = [
            skill_matches[skill].combined_strength if skill_matches[skill] else 0.0
            for skill in must
        ]
        must_values.extend(
            match.combined_strength if match else 0.0
            for group in must_groups
            for match in [group_matches[_group_key(group)]]
        )
        if not must_values:
            must_values = [
                skill_matches[skill].combined_strength if skill_matches[skill] else 0.0
                for skill in core_skills
            ]
        component_scores["must_have_skills"] = _mean(
            must_values
        )
        component_weights["must_have_skills"] = 30.0

    component_scores["relevant_evidence"] = _relevant_evidence(candidate, all_job_skills, skill_matches)
    component_weights["relevant_evidence"] = 25.0

    if requirements.min_years_experience > 0 or requirements.seniority != "unspecified":
        component_scores["experience_seniority"] = _experience_score(candidate, requirements)
        component_weights["experience_seniority"] = 20.0

    if requirements.domain and requirements.domain != "software" or requirements.responsibilities:
        component_scores["responsibility_domain"] = _domain_score(candidate, requirements, skill_matches)
        component_weights["responsibility_domain"] = 10.0

    if preferred or nice or preferred_groups:
        preferred_values = [
            skill_matches[skill].combined_strength if skill_matches[skill] else 0.0 for skill in preferred
        ]
        nice_values = [skill_matches[skill].combined_strength if skill_matches[skill] else 0.0 for skill in nice]
        group_values = [
            match.combined_strength if match else 0.0
            for group in preferred_groups
            for match in [group_matches[_group_key(group)]]
        ]
        preferred_values.extend(group_values)
        component_scores["preferred_skills"] = (
            0.8 * _mean(preferred_values) + 0.2 * _mean(nice_values)
            if preferred_values
            else _mean(nice_values)
        )
        component_weights["preferred_skills"] = 5.0

    if requirements.education:
        component_scores["education_language"] = _education_language_score(candidate, requirements)
        component_weights["education_language"] = 5.0

    has_location_requirement = bool(
        requirements.location_requirement and requirements.location_requirement != "Not specified"
    )
    if any(
        (
            has_location_requirement,
            requirements.work_authorization,
            requirements.availability,
            requirements.work_mode,
        )
    ):
        component_scores["logistics"] = _logistics_score(candidate, requirements)
        component_weights["logistics"] = 5.0

    weighted_earned = sum(component_scores[name] * weight for name, weight in component_weights.items())
    applicable_weight = sum(component_weights.values()) or 1.0
    raw_score = round(100.0 * weighted_earned / applicable_weight, 1)

    blockers: list[str] = []
    gaps: list[str] = []
    matched: list[str] = []
    caps: list[tuple[float, str]] = []

    missing_must = [
        skill
        for skill in must
        if not skill_matches.get(skill)
        or skill_matches[skill].transfer_strength < 0.75
        or skill_matches[skill].combined_strength < 0.25
    ]
    weak_must = [
        skill
        for skill in must
        if skill not in missing_must
        and skill_matches.get(skill)
        and skill_matches[skill].combined_strength < 0.6
    ]
    missing_groups = [
        group
        for group in must_groups
        if not group_matches[_group_key(group)]
        or group_matches[_group_key(group)].transfer_strength < 0.75
        or group_matches[_group_key(group)].combined_strength < 0.25
    ]
    weak_groups = [
        group
        for group in must_groups
        if group not in missing_groups
        and group_matches[_group_key(group)]
        and group_matches[_group_key(group)].combined_strength < 0.6
    ]
    for skill in missing_must:
        evidence = requirements.evidence_by_requirement.get(skill, "Explicitly listed as required.")
        blockers.append(f"Missing must-have skill: {skill}. Job evidence: {evidence}")
    for skill in weak_must:
        match = skill_matches[skill]
        if match and match.evidence_type == "declared_skill":
            gaps.append(
                f"{skill} is listed in the profile but is not yet backed by project or work evidence."
            )
        else:
            gaps.append(f"Must-have evidence is weak or only transferable: {skill}.")
    for group in missing_groups:
        blockers.append(
            "Missing required alternative: one of "
            + ", ".join(group.skills)
            + f". Job evidence: {group.evidence}"
        )
    for group in weak_groups:
        selected = group_matches[_group_key(group)]
        assert selected is not None
        gaps.append(
            f"Required alternative has weak evidence: {selected.requirement} "
            f"(one of {', '.join(group.skills)})."
        )
    missing_requirement_count = len(missing_must) + len(missing_groups)
    if missing_requirement_count == 1:
        caps.append((65.0, "One critical must-have skill is missing (maximum 65)."))
    elif missing_requirement_count >= 2:
        caps.append((45.0, "Two or more critical must-have skills are missing (maximum 45)."))

    if requirements.min_years_experience > 0:
        required = requirements.min_years_experience
        if candidate.years_experience <= 0:
            blockers.append(
                f"Experience mismatch: job requires {required:g}+ professional years; profile has 0 confirmed professional years."
            )
            caps.append((45.0, "No confirmed professional experience for an experienced role (maximum 45)."))
        elif candidate.years_experience < required:
            deficit = required - candidate.years_experience
            blockers.append(
                f"Experience mismatch: job requires {required:g}+ years; profile has {candidate.years_experience:g}."
            )
            if deficit > 1:
                caps.append((55.0, "Professional experience is more than one year below the minimum (maximum 55)."))
            else:
                caps.append((60.0, "Professional experience is below the stated minimum (maximum 60)."))
        else:
            matched.append(
                f"Professional experience covers the requirement: {candidate.years_experience:g} vs {required:g}+ years."
            )

    senior_years = (
        max(4.0, requirements.min_years_experience)
        if requirements.experience_requirement_known
        else 5.0
    )
    if requirements.seniority == "senior" and candidate.years_experience < senior_years:
        blockers.append("Seniority mismatch: senior/lead role without senior-level professional evidence.")
        caps.append((35.0, "Senior/lead evidence is not present (maximum 35)."))
    elif requirements.seniority in {"student", "junior"} and candidate.career_stage in {
        "student",
        "new graduate",
        "junior",
    }:
        matched.append(f"Career stage aligns with the {requirements.seniority} role.")

    if requirements.education and not candidate.education:
        gaps.append(f"Required education is not confirmed: {requirements.education}.")
        caps.append((60.0, "Explicit education requirement is unconfirmed (maximum 60)."))

    if requirements.work_authorization and "requires work sponsorship" in candidate.work_authorization.lower():
        blockers.append("Work-authorization mismatch: candidate requires sponsorship and the posting excludes it.")
        caps.append((35.0, "Explicit work-authorization blocker (maximum 35)."))

    if _hard_location_mismatch(candidate.location, requirements.location_requirement, requirements.work_mode):
        blockers.append(
            f"Location/work-mode mismatch: profile says {candidate.location}; posting says {requirements.location_requirement}."
        )
        caps.append((45.0, "Hard location or work-mode mismatch (maximum 45)."))

    for skill, match in skill_matches.items():
        if match and match.combined_strength >= 0.5:
            label = "Exact" if match.transfer_strength >= 1 else "Transferable"
            matched.append(
                f"{label} skill evidence for {skill}: {match.candidate_skill} — {match.evidence}"
            )
        elif skill in preferred:
            gaps.append(f"Preferred skill has no strong evidence: {skill}.")

    for group in requirements.skill_groups:
        match = group_matches[_group_key(group)]
        if match and match.combined_strength >= 0.5:
            matched.append(
                f"Requirement group satisfied through {match.requirement}: {match.evidence}"
            )
        elif group.priority in {"preferred", "nice"}:
            gaps.append(
                "Preferred alternative has no strong evidence: one of "
                + ", ".join(group.skills)
                + "."
            )

    if source_confidence < 0.65:
        gaps.append("Job extraction confidence is limited; paste the full posting to improve the result.")

    applied_caps = [reason for _, reason in sorted(caps, key=lambda item: item[0])]
    score = min([raw_score, *[cap for cap, _ in caps]]) if caps else raw_score
    score = round(max(0.0, min(100.0, score)), 1)
    fit_level = "Strong" if score >= 75 else "Medium" if score >= 50 else "Weak"
    confidence = _confidence(candidate, requirements, source_confidence, skill_matches)
    projects = _recommended_projects(candidate, all_job_skills)
    skill_order = _skill_order(candidate, all_job_skills)
    about = _about(candidate, role, requirements)

    feature_snapshot: dict[str, object] = {
        "model_version": MODEL_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "raw_score": raw_score,
        "candidate_stage": candidate.career_stage,
        "candidate_years_experience": candidate.years_experience,
        "candidate_internship_years": candidate.internship_years,
        "job_min_years": requirements.min_years_experience,
        "job_seniority": requirements.seniority,
        "component_weights": component_weights,
        "component_scores": {name: round(value, 4) for name, value in component_scores.items()},
        "skill_matches": {
            skill: (
                {
                    "candidate_skill": match.candidate_skill,
                    "transfer_strength": match.transfer_strength,
                    "evidence_strength": match.evidence_strength,
                    "combined_strength": match.combined_strength,
                    "fact_id": match.fact_id,
                    "recency_factor": candidate.skill_evidence[match.candidate_skill].recency_factor,
                }
                if match
                else None
            )
            for skill, match in skill_matches.items()
        },
        "requirement_groups": [
            {
                "priority": group.priority,
                "mode": group.mode,
                "skills": group.skills,
                "selected_skill": (
                    group_matches[_group_key(group)].requirement
                    if group_matches[_group_key(group)]
                    else None
                ),
                "score": (
                    group_matches[_group_key(group)].combined_strength
                    if group_matches[_group_key(group)]
                    else 0.0
                ),
            }
            for group in requirements.skill_groups
        ],
        "applied_caps": applied_caps,
    }

    return MatchResult(
        score=score,
        fit_level=fit_level,
        confidence=confidence,
        matched_evidence=_dedupe(matched)[:10]
        or ["No strong evidence match was found in the current profile."],
        missing_blockers=_dedupe(blockers)[:10],
        gaps=_dedupe(gaps)[:10]
        or ["No major gap detected; verify the score against the complete posting."],
        projects=projects,
        skill_order=skill_order,
        about_text=about.text,
        about_template_id=about.template_id,
        about_evidence=about.evidence,
        model_version=MODEL_VERSION,
        ontology_version=ONTOLOGY_VERSION,
        component_scores={name: round(value * 100, 1) for name, value in component_scores.items()},
        applied_caps=applied_caps,
        feature_snapshot=feature_snapshot,
    )


def _best_skill_match(candidate: CandidateSnapshot, requirement: str) -> SkillMatch | None:
    best: SkillMatch | None = None
    for skill, evidence in candidate.skill_evidence.items():
        transfer = skill_match_strength(skill, requirement)
        combined = round(transfer * evidence.strength, 4)
        match = SkillMatch(
            requirement=requirement,
            candidate_skill=skill,
            transfer_strength=transfer,
            evidence_strength=evidence.strength,
            combined_strength=combined,
            evidence_type=evidence.evidence_type,
            evidence=evidence.evidence,
            fact_id=evidence.fact_id,
        )
        if best is None or (match.combined_strength, match.candidate_skill) > (
            best.combined_strength,
            best.candidate_skill,
        ):
            best = match
    return best if best and best.combined_strength > 0 else None


def _group_key(group: RequirementGroup) -> str:
    return "|".join([group.priority, group.mode, *group.skills, group.evidence])


def _best_group_match(
    group: RequirementGroup,
    matches: dict[str, SkillMatch | None],
) -> SkillMatch | None:
    candidates = [matches.get(skill) for skill in group.skills]
    valid = [match for match in candidates if match is not None]
    if not valid:
        return None
    return max(
        valid,
        key=lambda match: (
            match.combined_strength,
            match.transfer_strength,
            match.requirement,
        ),
    )


def _relevant_evidence(
    candidate: CandidateSnapshot,
    job_skills: list[str],
    matches: dict[str, SkillMatch | None],
) -> float:
    skill_strength = _mean([match.combined_strength if match else 0.0 for match in matches.values()])
    if not job_skills:
        skill_strength = _mean([evidence.strength for evidence in candidate.skill_evidence.values()])
    best_project_overlap = 0.0
    if job_skills and candidate.projects:
        best_project_overlap = max(
            len(set(extract_skills(project)) & set(job_skills)) / max(1, min(4, len(job_skills)))
            for project in candidate.projects
        )
    elif candidate.projects:
        best_project_overlap = 0.6
    return min(1.0, 0.7 * skill_strength + 0.3 * min(1.0, best_project_overlap))


def _experience_score(candidate: CandidateSnapshot, requirements: JobRequirements) -> float:
    if requirements.min_years_experience > 0:
        return min(1.0, candidate.years_experience / requirements.min_years_experience)
    if requirements.seniority == "senior":
        return min(1.0, candidate.years_experience / 5)
    if requirements.seniority == "experienced":
        return min(1.0, candidate.years_experience / 3)
    if requirements.seniority in {"student", "junior"}:
        return 1.0 if candidate.career_stage in {"student", "new graduate", "junior"} else 0.8
    return 0.7


def _domain_score(
    candidate: CandidateSnapshot,
    requirements: JobRequirements,
    matches: dict[str, SkillMatch | None],
) -> float:
    candidate_domain = _normalize_domain(candidate.domain)
    job_domain = _normalize_domain(requirements.domain)
    if candidate_domain == job_domain:
        return 1.0
    overlap = _mean([match.combined_strength if match else 0.0 for match in matches.values()])
    return min(0.75, overlap)


def _education_language_score(candidate: CandidateSnapshot, requirements: JobRequirements) -> float:
    education_score = 1.0 if candidate.education else 0.0
    if not requirements.languages:
        return education_score
    language_hits = len(set(candidate.languages) & set(requirements.languages)) / len(requirements.languages)
    return 0.7 * education_score + 0.3 * language_hits


def _logistics_score(candidate: CandidateSnapshot, requirements: JobRequirements) -> float:
    checks: list[float] = []
    if requirements.location_requirement and requirements.location_requirement != "Not specified":
        if candidate.location:
            checks.append(
                0.0
                if _hard_location_mismatch(candidate.location, requirements.location_requirement, requirements.work_mode)
                else 1.0
            )
        else:
            checks.append(0.5)
    if requirements.work_authorization:
        checks.append(0.0 if "requires work sponsorship" in candidate.work_authorization.lower() else 0.5)
    if requirements.availability:
        checks.append(1.0 if requirements.availability in candidate.availability.lower() else 0.5)
    if requirements.work_mode and not checks:
        checks.append(0.7)
    return _mean(checks) if checks else 0.7


def _hard_location_mismatch(candidate_location: str, job_location: str, work_mode: str) -> bool:
    if not candidate_location or not job_location or job_location == "Not specified":
        return False
    if "remote" in job_location.lower() or "remote" in work_mode.lower():
        return False
    candidate_tokens = set(_location_tokens(candidate_location))
    job_tokens = set(_location_tokens(job_location))
    if "israel" in candidate_tokens and job_tokens & {
        "jerusalem",
        "tel aviv",
        "haifa",
        "yokneam",
        "herzliya",
        "ramat gan",
    }:
        return False
    return bool(candidate_tokens and job_tokens and not candidate_tokens.intersection(job_tokens))


def _location_tokens(value: str) -> list[str]:
    lower = value.lower()
    terms = ("israel", "jerusalem", "tel aviv", "haifa", "yokneam", "herzliya", "ramat gan")
    return [term for term in terms if term in lower]


def _confidence(
    candidate: CandidateSnapshot,
    requirements: JobRequirements,
    source_confidence: float,
    matches: dict[str, SkillMatch | None],
) -> float:
    profile_parts = [
        1.0 if candidate.skills else 0.0,
        1.0 if candidate.projects else 0.0,
        1.0 if candidate.education else 0.0,
        1.0 if candidate.location else 0.0,
        1.0 if candidate.availability else 0.0,
    ]
    evidence_quality = _mean([evidence.strength for evidence in candidate.skill_evidence.values()])
    requirement_evidence = (
        len(requirements.evidence_by_requirement) / max(1, len(requirements.all_skills))
        if requirements.all_skills
        else 0.5
    )
    match_coverage = sum(1 for match in matches.values() if match) / max(1, len(matches))
    value = (
        0.25 * _mean(profile_parts)
        + 0.2 * evidence_quality
        + 0.15 * max(0.0, min(1.0, source_confidence))
        + 0.15 * max(0.0, min(1.0, requirements.extraction_completeness))
        + 0.15 * min(1.0, requirement_evidence)
        + 0.1 * match_coverage
    )
    return round(max(0.2, min(0.98, value)), 2)


def _recommended_projects(candidate: CandidateSnapshot, job_skills: list[str]) -> list[str]:
    if not candidate.projects:
        return [PROJECT_EVIDENCE_PROMPT]
    scored: list[tuple[int, int, str]] = []
    for project in candidate.projects:
        project_skills = set(extract_skills(project))
        overlap = len(project_skills & set(job_skills))
        scored.append((overlap, len(project_skills), project))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2].lower()))
    return [project for _, _, project in scored[:3]]


def _skill_order(candidate: CandidateSnapshot, job_skills: list[str]) -> list[str]:
    matched = [skill for skill in job_skills if skill in candidate.skills]
    remaining = sorted(
        (skill for skill in candidate.skills if skill not in matched),
        key=lambda skill: (-candidate.skill_evidence[skill].strength, skill),
    )
    return [*matched, *remaining][:12]


def _about(candidate: CandidateSnapshot, role: str, requirements: JobRequirements) -> AboutResult:
    try:
        return build_about(candidate, role, requirements)
    except ValueError:
        evidence = [item.evidence for item in candidate.skill_evidence.values()][:5]
        return AboutResult(candidate.summary or "Profile needs more evidence before generating an About section.", "PROFILE_SUMMARY", evidence)


def _normalize_domain(value: str) -> str:
    lower = value.lower().strip()
    if lower in {"embedded/systems", "systems"}:
        return "embedded"
    if lower in {"ai/data", "machine learning"}:
        return "ml"
    return lower or "software"


def _mean(values) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            output.append(cleaned)
            seen.add(key)
    return output
