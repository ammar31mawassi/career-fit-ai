from __future__ import annotations

import pytest

from app.services.about_templates import TEMPLATES, build_about
from app.services.job_research import JobRequirements
from app.services.matcher import score_match
from app.services.ontology import ONTOLOGY_VERSION, infer_domain
from app.services.profile import CandidateSnapshot, SkillEvidence


ROLE_CASES = [
    ("backend", "Backend Developer", ["python", "postgresql"]),
    ("frontend", "Frontend Developer", ["react", "typescript"]),
    ("embedded/systems", "Embedded Developer", ["c++", "firmware"]),
    ("mobile", "Android Developer", ["kotlin", "android"]),
    ("data", "Data Engineer", ["python", "sql"]),
    ("ai/data", "Machine Learning Engineer", ["python", "pytorch"]),
    ("cloud", "Cloud Engineer", ["docker", "kubernetes"]),
    ("qa", "QA Automation Engineer", ["playwright", "test automation"]),
    ("security", "Security Engineer", ["python", "cybersecurity"]),
    ("systems", "Systems Developer", ["c++", "linux"]),
]


def _candidate(
    skills: list[str],
    domain: str,
    strength: float = 0.82,
    years: float = 0,
    evidence_type: str = "project",
) -> CandidateSnapshot:
    evidence = {
        skill: SkillEvidence(
            skill=skill,
            strength=strength,
            evidence_type=evidence_type,
            evidence=f"Built a project using {skill}.",
            fact_id=index + 1,
            source_id=1,
        )
        for index, skill in enumerate(skills)
    }
    project = "Built and tested a project using " + ", ".join(skills) + "."
    return CandidateSnapshot(
        skills=set(skills),
        skill_evidence=evidence,
        projects=[project],
        project_evidence={project: project},
        years_experience=years,
        internship_years=0,
        education="B.Sc. in Computer Science",
        semesters_left=2 if years == 0 else None,
        location="Israel",
        work_authorization="Authorized to work in Israel",
        availability="Available full-time",
        languages=["english"],
        domain=infer_domain(skills) if domain == "software" else domain,
        career_stage="student" if years == 0 else "junior",
        about_me="Evidence-focused software developer",
        summary="Evidence-focused software developer.",
        evidence_by_skill={skill: item.evidence for skill, item in evidence.items()},
    )


def _requirements(domain: str, skills: list[str], years: float = 0) -> JobRequirements:
    return JobRequirements(
        must_have_skills=skills,
        preferred_skills=[],
        nice_to_have_skills=[],
        all_skills=skills,
        min_years_experience=years,
        seniority="experienced" if years else "student",
        education="",
        work_mode="",
        domain=domain,
        summary="",
        languages=[],
        location_requirement="Not specified",
        work_authorization="",
        availability="",
        responsibilities=[],
        evidence_by_requirement={skill: f"Requirements: {skill}." for skill in skills},
        ontology_version=ONTOLOGY_VERSION,
    )


CALIBRATION_CASES = []
for domain, role, skills in ROLE_CASES:
    CALIBRATION_CASES.extend(
        [
            (f"{domain}-aligned", _candidate(skills, domain), _requirements(domain, skills), 65, 100),
            (f"{domain}-weak-evidence", _candidate(skills, domain, strength=0.35), _requirements(domain, skills), 20, 80),
            (f"{domain}-missing-must", _candidate(skills[:1], domain), _requirements(domain, skills), 0, 65),
            (f"{domain}-experience-blocker", _candidate(skills, domain), _requirements(domain, skills, years=3), 0, 45),
        ]
    )


@pytest.mark.parametrize("case_id,candidate,requirements,minimum,maximum", CALIBRATION_CASES, ids=[case[0] for case in CALIBRATION_CASES])
def test_reviewed_calibration_ranges(case_id, candidate, requirements, minimum, maximum):
    result = score_match(candidate, "Ignored Company", case_id, requirements, 1.0)
    assert minimum <= result.score <= maximum
    assert result.model_version == "fit-v2.3.0"
    assert result.feature_snapshot["component_scores"]


def test_template_catalog_is_complete_and_never_leaks_tokens():
    assert len(TEMPLATES) == 24
    candidate = _candidate(["c++", "firmware", "linux"], "embedded/systems")
    result = build_about(candidate, "Embedded Developer", _requirements("embedded/systems", ["c++", "firmware"]))
    assert result.template_id == "T11"
    assert "<" not in result.text and ">" not in result.text
    assert "built built" not in result.text.lower()
    assert 30 <= len(result.text.split()) <= 90

    cloud = build_about(
        _candidate(["python", "docker", "fastapi"], "cloud"),
        "Cloud Intern",
        _requirements("cloud", ["python", "docker"]),
    )
    assert cloud.template_id == "T15"
    assert "built built" not in cloud.text.lower()
    assert "using fastapi" not in cloud.text.lower()


def test_protected_text_cannot_change_score_because_it_is_not_a_feature():
    candidate = _candidate(["python", "postgresql"], "backend")
    requirements = _requirements("backend", ["python", "postgresql"])
    first = score_match(candidate, "Company", "Backend Developer", requirements, 1.0)
    second = score_match(candidate, "Different Company", "Backend Developer", requirements, 1.0)
    assert first.score == second.score
    assert first.feature_snapshot == second.feature_snapshot


def test_declared_skill_is_recognized_without_claiming_demonstrated_evidence():
    requirements = _requirements("cloud", ["docker"])
    declared = score_match(
        _candidate(["docker"], "cloud", strength=0.54, evidence_type="declared_skill"),
        "Company",
        "Cloud Developer",
        requirements,
        1.0,
    )
    confirmed = score_match(
        _candidate(["docker"], "cloud", strength=0.64, evidence_type="declared_skill"),
        "Company",
        "Cloud Developer",
        requirements,
        1.0,
    )

    assert not declared.missing_blockers
    assert any("listed in the profile" in gap for gap in declared.gaps)
    assert confirmed.score > declared.score
    assert not any(
        "listed in the profile" in gap or "weak" in gap.lower()
        for gap in confirmed.gaps
    )
