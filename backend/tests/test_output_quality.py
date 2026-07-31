from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.about_templates import TEMPLATES, build_about
from app.services.advice_quality import (
    OUTPUT_POLICY_VERSION,
    PROJECT_EVIDENCE_PROMPT,
    assess_resume_advice,
    enforce_resume_advice,
)
from app.services.job_research import JobRequirements
from app.services.profile import CandidateSnapshot, SkillEvidence, _career_stage


def _candidate(
    *,
    skills: list[str] | None = None,
    domain: str = "backend",
    stage: str = "student",
    years: float = 0,
    semesters: int | None = 2,
    education: str = "B.Sc. in Computer Science",
    availability: str = "Available full-time",
    about_me: str = "Evidence-focused software developer",
    project_title: str = "CareerFit: a profile-aware job matching application",
    project_evidence: str | None = "Built and tested CareerFit with Python, FastAPI, SQL, and React.",
) -> CandidateSnapshot:
    skills = skills or ["python", "fastapi", "sql", "react"]
    evidence = {
        skill: SkillEvidence(
            skill=skill,
            strength=0.82,
            evidence_type="project",
            evidence=f"The reviewed profile contains verified {skill} work.",
            fact_id=index + 1,
            source_id=1,
        )
        for index, skill in enumerate(skills)
    }
    projects = [project_title] if project_evidence is not None else []
    project_evidence_by_title = (
        {project_title: project_evidence} if project_evidence is not None else {}
    )
    return CandidateSnapshot(
        skills=set(skills),
        skill_evidence=evidence,
        projects=projects,
        project_evidence=project_evidence_by_title,
        years_experience=years,
        internship_years=0,
        education=education,
        semesters_left=semesters,
        location="Israel",
        work_authorization="Authorized to work in Israel",
        availability=availability,
        languages=["english"],
        domain=domain,
        career_stage=stage,
        about_me=about_me,
        summary="Evidence-focused software developer with reviewed project work.",
        evidence_by_skill={skill: item.evidence for skill, item in evidence.items()},
    )


def _requirements(
    *,
    domain: str = "backend",
    availability: str = "",
    skills: list[str] | None = None,
    seniority: str = "junior",
) -> JobRequirements:
    skills = skills or ["python", "fastapi", "sql", "react"]
    return JobRequirements(
        must_have_skills=skills[:2],
        preferred_skills=skills[2:3],
        nice_to_have_skills=skills[3:],
        all_skills=skills,
        min_years_experience=0,
        seniority=seniority,
        education="",
        work_mode="hybrid",
        domain=domain,
        summary="Backend role",
        languages=[],
        location_requirement="Israel",
        work_authorization="",
        availability=availability,
        responsibilities=["Build APIs"],
        evidence_by_requirement={skill: f"Requirements: {skill}." for skill in skills},
    )


@dataclass(frozen=True)
class TemplateReachabilityCase:
    template_id: str
    role: str
    job_domain: str
    candidate_domain: str
    skills: tuple[str, ...]
    stage: str
    years: float = 0
    semesters: int | None = None
    education: str = "B.Sc. in Computer Science"
    seniority: str = "junior"
    job_availability: str = ""
    candidate_availability: str = "Available full-time"
    with_project: bool = True
    open_source: bool = False


TEMPLATE_REACHABILITY_CASES: tuple[TemplateReachabilityCase, ...] = (
    TemplateReachabilityCase("T01", "Software Developer", "general", "general", ("python", "sql"), "student", semesters=2, seniority="student"),
    TemplateReachabilityCase("T02", "Backend Developer", "backend", "backend", ("python", "fastapi"), "candidate", education="", with_project=False),
    TemplateReachabilityCase("T03", "Software Developer", "general", "general", ("python", "sql"), "student", semesters=2, seniority="student", job_availability="full-time"),
    TemplateReachabilityCase("T04", "Cloud Intern", "cloud", "cloud", ("python", "docker", "kubernetes"), "student", semesters=2, seniority="student"),
    TemplateReachabilityCase("T05", "Graduate Hardware Engineer", "hardware", "hardware", ("c++", "linux"), "new graduate"),
    TemplateReachabilityCase("T06", "Junior Hardware Developer", "hardware", "hardware", ("c++", "linux"), "junior", years=1),
    TemplateReachabilityCase("T07", "Operations Developer", "operations", "operations", ("python", "sql"), "candidate", education=""),
    TemplateReachabilityCase("T08", "Backend Developer", "backend", "backend", ("python", "fastapi", "postgresql"), "junior", years=1),
    TemplateReachabilityCase("T09", "Frontend Developer", "frontend", "frontend", ("react", "typescript", "css"), "junior", years=1),
    TemplateReachabilityCase("T10", "Full-stack Developer", "full-stack", "full-stack", ("react", "typescript", "python", "fastapi"), "junior", years=1),
    TemplateReachabilityCase("T11", "Embedded Developer", "embedded/systems", "embedded/systems", ("c++", "firmware", "linux"), "junior", years=1),
    TemplateReachabilityCase("T12", "Android Developer", "mobile", "mobile", ("kotlin", "android", "java"), "junior", years=1),
    TemplateReachabilityCase("T13", "Data Engineer", "data", "data", ("python", "sql", "spark"), "junior", years=1),
    TemplateReachabilityCase("T14", "Machine Learning Engineer", "ai/data", "ai/data", ("python", "pytorch", "machine learning"), "junior", years=1),
    TemplateReachabilityCase("T15", "Cloud Engineer", "cloud", "cloud", ("docker", "kubernetes", "aws"), "junior", years=1),
    TemplateReachabilityCase("T16", "QA Automation Engineer", "qa", "qa", ("playwright", "test automation", "python"), "junior", years=1),
    TemplateReachabilityCase("T17", "Security Engineer", "security", "security", ("python", "cybersecurity", "linux"), "junior", years=1),
    TemplateReachabilityCase("T18", "Research Engineer", "research", "research", ("python", "data analysis", "machine learning"), "new graduate"),
    TemplateReachabilityCase("T19", "Software Developer", "software", "software", ("python", "fastapi", "sql"), "junior", years=1, open_source=True),
    TemplateReachabilityCase("T20", "Product Platform Engineer", "product", "product", ("python", "react", "sql"), "junior", years=1),
    TemplateReachabilityCase("T21", "Generalist Engineer", "generalist", "generalist", ("python", "fastapi", "sql", "react", "typescript", "docker", "linux"), "junior", years=1),
    TemplateReachabilityCase("T22", "Systems Engineer", "hardware", "hardware", ("c++", "linux", "python"), "mid-level", years=3, seniority="experienced"),
    TemplateReachabilityCase("T23", "Backend Engineer", "backend", "backend", ("python", "fastapi", "postgresql"), "experienced", years=6, seniority="experienced"),
    TemplateReachabilityCase("T24", "Data Engineer", "data", "frontend", ("python", "sql", "data analysis"), "career changer", years=4, seniority="experienced"),
)


def _reachability_inputs(
    case: TemplateReachabilityCase,
) -> tuple[CandidateSnapshot, JobRequirements]:
    project_title = f"{case.candidate_domain.title()} portfolio project"
    project_evidence = None
    if case.with_project:
        prefix = "Published a public GitHub repository and " if case.open_source else ""
        project_evidence = (
            prefix
            + "built reviewed project work using "
            + ", ".join(case.skills)
            + "."
        )
    candidate = _candidate(
        skills=list(case.skills),
        domain=case.candidate_domain,
        stage=case.stage,
        years=case.years,
        semesters=case.semesters,
        education=case.education,
        availability=case.candidate_availability,
        project_title=project_title,
        project_evidence=project_evidence,
    )
    requirements = _requirements(
        domain=case.job_domain,
        availability=case.job_availability,
        skills=list(case.skills),
        seniority=case.seniority,
    )
    return candidate, requirements


def test_evidence_backed_template_passes_quality_boundary():
    candidate = _candidate()
    requirements = _requirements()
    about = build_about(candidate, "Backend Developer", requirements)

    report = assess_resume_advice(
        candidate,
        "Backend Developer",
        requirements,
        projects=candidate.projects,
        skill_order=["python", "fastapi", "sql"],
        about_text=about.text,
        evidence=about.evidence,
    )

    assert report.policy_version == OUTPUT_POLICY_VERSION
    assert report.passed
    assert not [item for item in report.findings if item.severity == "error"]


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("Candidate with <UNRESOLVED_FIELD> and verified project evidence for this role.", "unresolved_placeholder"),
        ("Candidate with <script>alert(1)</script> and verified project evidence for this role.", "unexpected_markup"),
        ("Candidate with verified verified project evidence for Python and FastAPI in this role.", "duplicate_word"),
        ("Candidate delivered 99% growth with verified Python and FastAPI project evidence.", "unsupported_number"),
    ],
)
def test_hard_quality_rules_are_named_and_explainable(text: str, expected_code: str):
    candidate = _candidate()
    report = assess_resume_advice(
        candidate,
        "Backend Developer",
        _requirements(),
        projects=candidate.projects,
        skill_order=["python"],
        about_text=text,
        evidence=list(candidate.project_evidence.values()),
    )

    assert not report.passed
    assert expected_code in {item.code for item in report.findings}


def test_quality_boundary_repairs_unsupported_scorer_output_without_changing_sources():
    candidate = _candidate()
    checked = enforce_resume_advice(
        candidate,
        "Backend Developer",
        _requirements(),
        projects=["Invented quantum platform"],
        skill_order=["python", "telepathy"],
        about_text="Candidate delivered 500% growth growth with <CLIENT_NAME>.",
        evidence=["Unverified award"],
    )

    assert checked.report.passed
    assert checked.report.repaired
    assert checked.projects == candidate.projects
    assert set(checked.skill_order).issubset(candidate.skills)
    assert set(checked.evidence).issubset(
        {
            *(item.evidence for item in candidate.skill_evidence.values()),
            *candidate.project_evidence.values(),
        }
    )
    assert "500" not in checked.about_text
    assert "<" not in checked.about_text
    assert {item.code for item in checked.report.findings} >= {
        "repaired_unsupported_project",
        "repaired_unsupported_skill",
        "repaired_unsupported_evidence",
    }


def test_missing_project_prompt_is_advice_not_a_fabricated_project():
    candidate = _candidate(project_evidence=None, stage="candidate", education="")
    requirements = _requirements()
    about = build_about(candidate, "Backend Developer", requirements)

    checked = enforce_resume_advice(
        candidate,
        "Backend Developer",
        requirements,
        projects=[PROJECT_EVIDENCE_PROMPT],
        skill_order=sorted(candidate.skills),
        about_text=about.text,
        evidence=about.evidence,
    )

    assert checked.projects == [PROJECT_EVIDENCE_PROMPT]
    assert checked.report.passed
    assert not checked.report.repaired


def test_technical_word_robust_and_resume_punctuation_are_not_false_positives():
    candidate = _candidate(
        project_evidence="Built a robust parser: Python input → normalized SQL records."
    )
    text = (
        "Backend candidate with verified Python and FastAPI project evidence. "
        "Built a robust parser: Python input → normalized SQL records."
    )
    report = assess_resume_advice(
        candidate,
        "Backend Developer",
        _requirements(),
        projects=candidate.projects,
        skill_order=["python", "fastapi"],
        about_text=text,
        evidence=list(candidate.project_evidence.values()),
    )

    assert report.passed
    assert not report.findings


def test_reachability_matrix_covers_each_catalog_template_once():
    catalog_ids = {template.template_id for template in TEMPLATES}
    case_ids = [case.template_id for case in TEMPLATE_REACHABILITY_CASES]

    assert len(case_ids) == len(set(case_ids))
    assert set(case_ids) == catalog_ids


@pytest.mark.parametrize(
    "case",
    TEMPLATE_REACHABILITY_CASES,
    ids=lambda case: case.template_id,
)
def test_every_template_is_reachable_and_passes_output_policy(
    case: TemplateReachabilityCase,
):
    candidate, requirements = _reachability_inputs(case)

    first = build_about(candidate, case.role, requirements)
    second = build_about(candidate, case.role, requirements)
    report = assess_resume_advice(
        candidate,
        case.role,
        requirements,
        projects=candidate.projects,
        skill_order=sorted(candidate.skills),
        about_text=first.text,
        evidence=first.evidence,
    )

    assert first == second
    assert first.template_id == case.template_id
    assert report.passed, report.findings
    assert not report.findings
    assert first.evidence


def test_career_change_template_requires_explicit_profile_language():
    assert (
        _career_stage(
            4,
            0,
            None,
            "B.Sc. in Computer Science",
            "Frontend engineer planning a career transition into data engineering.",
            transition_text="Frontend engineer planning a career transition into data engineering.",
        )
        == "career changer"
    )
    assert (
        _career_stage(
            4,
            0,
            None,
            "B.Sc. in Computer Science",
            "Frontend engineer with data engineering skills.",
        )
        == "mid-level"
    )
    assert (
        _career_stage(
            6,
            0,
            None,
            "B.Sc. in Computer Science",
            "Built a career transition dashboard for university students.",
            transition_text="Built a career transition dashboard for university students.",
        )
        == "experienced"
    )
    for negated in (
        "I am not a career changer.",
        "I am not planning a career transition into data engineering.",
    ):
        assert (
            _career_stage(
                6,
                0,
                None,
                "B.Sc. in Computer Science",
                negated,
                transition_text=negated,
            )
            == "experienced"
        )


def test_specialized_template_signals_do_not_overreach():
    student = _candidate(
        skills=["python", "fastapi", "sql"],
        domain="backend",
        stage="student",
        semesters=2,
    )
    backend = _requirements(
        domain="backend",
        skills=["python", "fastapi", "sql"],
        seniority="student",
    )
    domain_switcher = _candidate(
        skills=["python", "sql", "data analysis"],
        domain="frontend",
        stage="mid-level",
        years=4,
        semesters=None,
    )
    same_domain_changer = _candidate(
        skills=["python", "sql", "data analysis"],
        domain="data",
        stage="career changer",
        years=4,
        semesters=None,
    )
    data_role = _requirements(
        domain="data",
        skills=["python", "sql", "data analysis"],
        seniority="experienced",
    )

    assert build_about(student, "Internal Tools Developer", backend).template_id == "T08"
    assert build_about(domain_switcher, "Data Engineer", data_role).template_id != "T24"
    assert build_about(same_domain_changer, "Data Engineer", data_role).template_id != "T24"
    assert build_about(student, "Production Engineer", backend).template_id != "T20"
