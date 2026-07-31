from __future__ import annotations

import json
from uuid import UUID

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import AgentRun, Job, Profile, ProfileSource
from app.schemas import JobCreateIn
from app.services import job_research
from app.services.job_research import (
    JOB_READER_VERSION,
    classify_requirements,
    extract_job_from_input,
    validate_pasted_job_description,
)
from app.services.ontology import extract_skills
from app.services.jobs import create_or_analyze_job
from app.services.profile import analyze_profile


USER_ID = UUID("00000000-0000-0000-0000-000000000777")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _ready_profile(session: Session) -> None:
    profile = Profile(user_id=USER_ID, status="needs_analysis")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.add(
        ProfileSource(
            user_id=USER_ID,
            profile_id=profile.id or 0,
            source_type="cv",
            title="cv.pdf",
            content_text=(
                "B.Sc. Computer Science student with 2 semesters remaining and no professional "
                "experience. Built projects using Python, C++, JavaScript, data structures, Linux, "
                "FastAPI, PostgreSQL, and React."
            ),
        )
    )
    session.commit()
    analyze_profile(session, USER_ID)


def test_json_ld_url_only_extracts_job_identity(monkeypatch):
    description = (
        "Responsibilities: Build backend services and REST APIs. "
        "Requirements: 2 years of professional experience with Python and PostgreSQL. "
        "Preferred qualifications: Docker and AWS. " * 2
    )
    html = f"""
    <html><head><script type="application/ld+json">
    {json.dumps({
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Backend Engineer",
        "description": description,
        "hiringOrganization": {"name": "Example Labs"},
        "jobLocation": {
            "address": {
                "addressLocality": "Tel Aviv",
                "addressRegion": "Tel Aviv District,Israel",
                "addressCountry": {"@type": "Country", "name": "Israel"},
            }
        },
        "url": "https://example.com/jobs/123"
    })}
    </script></head><body></body></html>
    """
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: html)

    job = extract_job_from_input("https://example.com/jobs/123", "", "", "")

    assert job.company == "Example Labs"
    assert job.role == "Backend Engineer"
    assert job.location == "Tel Aviv, Tel Aviv District, Israel"
    assert job.requirements.min_years_experience == 2
    assert job.requirements.reader_version == JOB_READER_VERSION
    assert job.source_confidence >= 0.8


def test_workday_adapter_reads_public_cxs_payload(monkeypatch):
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: "<html></html>")
    monkeypatch.setattr(
        job_research,
        "_fetch_json",
        lambda _: {
            "jobPostingInfo": {
                "title": "Research Scientist Student",
                "location": "Migdal Ha'emek, Israel",
                    "jobDescription": (
                        "<p>Responsibilities: Develop computer vision algorithms.</p>"
                        "<p>Requirements: Computer Science student with Python and communication skills. "
                        "Work with researchers to design, validate, document, and improve production "
                        "algorithms for semiconductor inspection systems.</p>"
                    ),
                "externalUrl": "https://kla.wd1.myworkdayjobs.com/Search/job/example",
            }
        },
    )

    job = extract_job_from_input(
        "https://kla.wd1.myworkdayjobs.com/en-GB/Search/job/Israel/example",
        "",
        "",
        "",
    )

    assert job.company == "KLA"
    assert job.role == "Research Scientist Student"
    assert job.requirements.seniority == "student"
    assert "python" in job.requirements.all_skills


def test_metadata_recovers_identity_and_description_from_provider_error_page(monkeypatch):
    description = (
        "We are seeking a Senior Product Designer to own product discovery and delivery. "
        "Responsibilities include user research, prototyping, and collaboration with product "
        "and engineering. Requirements include five years of product design experience. " * 3
    )
    html = f"""
    <html><head>
      <title>Job opportunity: Senior Product Designer at Orca-AI | Comeet</title>
      <meta property="og:title" content="Job opportunity: Senior Product Designer at Orca-AI | Comeet">
      <meta property="og:description" content="{description}">
    </head><body><main>Something went wrong. Please try again later.</main></body></html>
    """
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: html)

    job = extract_job_from_input(
        "https://www.comeet.com/jobs/Orca-AI/example/senior-product-designer/123",
        "",
        "",
        "",
    )

    assert job.company == "Orca-AI"
    assert job.role == "Senior Product Designer"
    assert len(job.description_text) >= 500
    assert job.requirements.min_years_experience == 5


def test_comeet_generic_title_uses_role_part(monkeypatch):
    description = (
        "Cyber R&D Python Developer. Responsibilities: Design production-grade services. "
        "The Dream Skill Set: 5+ years of experience with Python. "
        "Understand and troubleshoot networking and routing. " * 3
    )
    html = f"""
    <html><head>
      <title>Join Our Team | Python Developer</title>
      <meta property="og:title" content="Join Our Team | Python Developer">
    </head><body><main>{description}</main></body></html>
    """
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: html)

    job = extract_job_from_input(
        "https://dreamgroup.com/comeet-positions/python-developer-7296b",
        "",
        "",
        "",
    )

    assert job.role == "Python Developer"
    assert job.requirements.min_years_experience == 5
    assert "python" in job.requirements.must_have_skills


def test_greenhouse_company_can_come_from_document_title(monkeypatch):
    description = (
        "Responsibilities: Run office operations and support employees. "
        "Requirements: two years of office management experience and strong communication. " * 3
    )
    html = f"""
    <html><head>
      <title>Job Application for Office Manager at Eon</title>
      <meta property="og:title" content="Office Manager">
    </head><body><main>{description}</main></body></html>
    """
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: html)

    job = extract_job_from_input(
        "https://job-boards.eu.greenhouse.io/eonio/jobs/123",
        "",
        "",
        "",
    )

    assert job.company == "Eon"
    assert job.role == "Office Manager"


def test_linkedin_recommendations_do_not_become_job_requirements(monkeypatch):
    core = """
    Responsibilities
    Perform manual testing and document defects.
    Requirements
    Background in Artillery systems - Must
    Experience with JIRA - Advantage
    Collaborate with the software team throughout integration and record clear test results.
    """ * 3
    description = core + """
    Similar jobs
    Test Automation Engineer
    AWS Firmware QA Engineer
    """
    html = f"""
    <html><head>
      <title>Junior QA Tester | LinkedIn</title>
      <meta property="og:title" content="Qualitest hiring Junior QA Tester in Israel | LinkedIn">
    </head><body><main>{description}</main></body></html>
    """
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: html)

    job = extract_job_from_input(
        "https://www.linkedin.com/jobs/view/123",
        "",
        "",
        "",
    )

    assert job.company == "Qualitest"
    assert job.role == "Junior QA Tester"
    assert "artillery systems" in job.requirements.must_have_skills
    assert "test automation" not in job.requirements.all_skills
    assert "aws" not in job.requirements.all_skills
    assert "firmware" not in job.requirements.all_skills


def test_alternative_languages_and_experience_are_typed():
    requirements = classify_requirements(
        "Minimum qualifications: 1 year of experience with software development in one or "
        "more programming languages such as Python, C, C++, Java, or JavaScript. "
        "1 year of experience with data structures and algorithms. "
        "1 year of experience with iOS application development.",
        "Software Engineer II, Notifications iOS",
    )

    assert requirements.min_years_experience == 1
    assert requirements.experience_requirement_known is True
    assert requirements.seniority == "junior"
    assert requirements.must_have_skills == ["software development", "data structures", "ios"]
    assert len(requirements.skill_groups) == 1
    assert requirements.skill_groups[0].mode == "one_of"
    assert requirements.skill_groups[0].skills == ["python", "c", "c++", "java", "javascript"]


def test_internship_graduation_remaining_is_not_professional_experience():
    requirements = classify_requirements(
        """
        General Summary:
        Design and develop tools for embedded systems validation.
        Key Responsibilities:
        Implement tools and scripts (primarily in Python) to improve test efficiency.
        Minimum Qualifications
        · Student pursuing a B.Sc. in Computer Science, Software Engineering, or Electrical Engineering
        · At least 2 year remaining until graduation | Minimum 3 days a week at office
        · Strong programming skills (Python preferred)
        Preferred Qualifications
        · Experience or coursework in AI / Machine Learning / Data Analysis
        · Experience with Git or other version control systems
        """,
        "Intern FY27 - System Integration and Testing Intern - Haifa",
    )

    assert requirements.min_years_experience == 0
    assert requirements.experience_requirement_known is True
    assert requirements.seniority == "student"
    assert requirements.availability == "2 years remaining until graduation, minimum 3 days/week onsite"
    assert requirements.education == "B.Sc. student in Computer Science / Software Engineering / Electrical Engineering"
    assert "python" not in requirements.must_have_skills
    assert "python" in requirements.preferred_skills
    assert "git" in requirements.preferred_skills


def test_teamme_uses_richer_dom_without_turning_tech_context_into_must_haves(monkeypatch):
    html = """
    <html><head>
      <title>Backend Tech Lead - Quantum Machines | Teamme.link</title>
      <meta property="og:title" content="Backend Tech Lead - Quantum Machines">
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Backend Tech Lead",
        "hiringOrganization": {"@type": "Organization", "name": "Quantum Machines"},
        "jobLocation": {"@type": "Place", "address": {"addressLocality": "Tel Aviv-Yafo", "addressCountry": "IL"}},
        "description": "Backend Tech Lead at Quantum Machines. We are a global leader in quantum control systems. Apply for the Backend Tech Lead role.",
        "url": "https://qm.teamme.link/jobs/13.05B"
      }
      </script>
    </head><body><main>
      <h1>Backend Tech Lead</h1>
      <p>Quantum Machines</p><p>Israel, Tel Aviv Office</p><p>Hybrid</p>
      <h2>Requirements</h2>
      <p>We are looking for a hands-on Tech Lead to drive the technical direction of the core backend layer over the company's flagship product and lead the engineers building it.</p>
      <p>The systems handle bursty, high-throughput workloads with strict latency requirements, distributed coordination, and hard concurrency problems.</p>
      <h2>What Makes This Role Different</h2>
      <p>Our backend team is the orchestration layer between hardware control systems (C++), a client SDK (Python), reporting systems (Go), and business logic (Java, Kotlin and Spring).</p>
      <h2>What You'll Own</h2>
      <ul>
        <li>Technical direction: architecture, concurrency models, resource pooling, distributed coordination and API boundaries.</li>
        <li>Design quality: lead design reviews and raise the engineering bar.</li>
        <li>Team growth: mentor engineers through design conversations and code reviews.</li>
        <li>Cross-team alignment across C++, Python and Go teams.</li>
        <li>Production ownership and root-cause analysis.</li>
      </ul>
    </main></body></html>
    """
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: html)

    job = extract_job_from_input("https://qm.teamme.link/jobs/13.05B", "", "", "")

    assert job.company == "Quantum Machines"
    assert job.role == "Backend Tech Lead"
    assert len(job.description_text) > 900
    assert "What You'll Own" in job.description_text
    assert job.requirements.seniority == "senior"
    assert job.requirements.min_years_experience == 0
    assert job.requirements.experience_requirement_known is False
    assert not {"c++", "python", "go", "java", "kotlin", "spring"}.intersection(
        job.requirements.must_have_skills
    )
    assert job.requirements.responsibilities


def test_go_and_rest_common_words_are_not_skills():
    assert extract_skills("Ready to go through support issues for Gong customers.") == []
    assert extract_skills("Rest assured that the hiring process is accessible.") == []
    assert extract_skills("Experience with Go and REST API services.") == ["go", "rest api"]


def test_written_and_ranged_experience_use_the_required_minimum():
    written = classify_requirements(
        "Requirements: five years of product design experience.",
        "Product Designer",
    )
    ranged = classify_requirements(
        "Requirements: 3-5 years of professional backend experience.",
        "Backend Engineer",
    )

    assert written.min_years_experience == 5
    assert ranged.min_years_experience == 3


def test_abbreviated_sr_title_is_classified_as_senior():
    requirements = classify_requirements(
        "Own the product roadmap and partner with engineering, design, and customers.",
        "API Security Sr. Product Manager",
    )

    assert requirements.seniority == "senior"


def test_json_ld_separate_job_fields_are_merged_into_the_posting(monkeypatch):
    html = """
    <html><head><title>Platform Engineer | ExampleCo</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {"@type": "JobPosting", "title": "Old teaser", "description": "Apply now."},
        {
          "@type": ["Thing", "JobPosting"],
          "title": "Platform Engineer",
          "hiringOrganization": [{"@type": "Organization", "name": "ExampleCo"}],
          "description": "Build and operate reliable services for our product platform and collaborate with engineering teams.",
          "responsibilities": ["Design production services", "Improve observability and incident response"],
          "qualifications": "Strong Linux and networking knowledge with clear communication.",
          "skills": ["Python", "Docker", "Kubernetes"],
          "experienceRequirements": "At least 18 months of professional software experience.",
          "educationRequirements": "Relevant technical degree or equivalent practical experience.",
          "employmentType": "FULL_TIME",
          "jobLocationType": "TELECOMMUTE",
          "applicantLocationRequirements": {"@type": "Country", "name": "Israel"},
          "url": "https://jobs.example.com/platform-engineer"
        }
      ]
    }
    </script></head><body><main><h1>Platform Engineer</h1></main></body></html>
    """
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: html)

    job = extract_job_from_input("https://jobs.example.com/platform-engineer", "", "", "")

    assert job.company == "ExampleCo"
    assert job.role == "Platform Engineer"
    assert job.reader_strategy == "json_ld"
    assert {"python", "docker", "kubernetes", "linux", "networking"} <= set(job.requirements.all_skills)
    assert job.requirements.min_years_experience == 1.5
    assert job.requirements.work_mode == "remote, full-time"
    assert job.location == "Israel, Remote"


def test_one_language_satisfies_group_but_real_blockers_remain():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Google",
                role="Software Engineer II, Notifications iOS",
                description_text=(
                    "Minimum qualifications: 1 year of experience with software development in one "
                    "or more programming languages such as Python, C, C++, Java, or JavaScript. "
                    "1 year of experience with data structures and algorithms. "
                    "1 year of experience with iOS application development."
                ),
            ),
        )

    assert job.match is not None
    blockers = " ".join(job.match.missing_blockers).lower()
    assert "required alternative" not in blockers
    assert "missing must-have skill: ios" in blockers
    assert "requires 1+ professional years" in blockers
    assert "missing must-have skill: c." not in blockers
    assert "missing must-have skill: java." not in blockers
    assert job.match.score <= 45


def test_failed_url_can_be_upgraded_with_pasted_description(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    real_extract = extract_job_from_input
    calls = 0

    def fail_once(source_url, company, role, description):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("blocked")
        return real_extract(source_url, company, role, description)

    monkeypatch.setattr("app.services.jobs.extract_job_from_input", fail_once)
    with Session(engine) as session:
        _ready_profile(session)
        failed = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(source_url="https://example.com/jobs/upgrade"),
        )
        upgraded = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                source_url="https://example.com/jobs/upgrade",
                company="Example",
                role="Backend Developer",
                description_text=(
                    "Requirements: Python and PostgreSQL. Responsibilities: Build backend APIs "
                    "and maintain production services. Review changes, investigate failures, "
                    "document technical decisions, and collaborate with product and engineering "
                    "partners to deliver reliable customer-facing software."
                ),
            ),
        )

    assert failed.id == upgraded.id
    assert failed.status == "failed"
    assert upgraded.status == "analyzed"
    assert upgraded.company == "Example"
    assert upgraded.requirements.reader_version == JOB_READER_VERSION


@pytest.mark.parametrize(
    "description",
    [
        "Click here to apply.",
        "This is an exciting opportunity with a great team and excellent culture. " * 5,
        "<div>Requirements</div><script>" + ("x" * 500) + "</script>",
    ],
)
def test_pasted_job_description_rejects_short_or_non_job_noise(description):
    with pytest.raises(ValueError, match="complete job description"):
        validate_pasted_job_description(description)


def test_pasted_job_description_accepts_complete_readable_content():
    validate_pasted_job_description(
        "Requirements: Python, PostgreSQL, testing, and API design. Responsibilities include "
        "building reliable services, reviewing changes, documenting technical decisions, "
        "investigating production failures, and collaborating with product and engineering."
    )


def test_invalid_structured_application_link_falls_back_to_safe_source_url(monkeypatch):
    description = (
        "Requirements: Python and SQL experience. Responsibilities include building reliable "
        "backend services, reviewing changes, documenting decisions, investigating failures, "
        "and collaborating with product and engineering partners."
    )
    html = f"""
    <html><head><script type="application/ld+json">
    {json.dumps({
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Backend Engineer",
        "description": description,
        "hiringOrganization": {"name": "Safe Jobs"},
        "url": "javascript:alert(1)",
    })}
    </script></head><body></body></html>
    """
    monkeypatch.setattr(job_research, "validate_public_job_url", lambda _: None)
    monkeypatch.setattr(job_research, "_fetch", lambda _: html)

    job = extract_job_from_input("https://jobs.example/openings/7#details", "", "", "")

    assert job.application_link == "https://jobs.example/openings/7"


def test_rejected_pasted_job_is_not_persisted_or_started():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)

        with pytest.raises(ValueError, match="complete job description"):
            create_or_analyze_job(
                session,
                USER_ID,
                JobCreateIn(
                    company="Noise Inc",
                    role="Developer",
                    description_text="Click here to learn more about our amazing company.",
                ),
            )

        assert list(session.exec(select(Job)).all()) == []
        assert list(session.exec(select(AgentRun)).all()) == []
