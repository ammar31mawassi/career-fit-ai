from __future__ import annotations

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from uuid import UUID

import pytest
from app.models import AgentRun, AgentStep, Job, Profile, ProfileFact, ProfileSource
from app.schemas import JobCreateIn
from app.api.routes import workspace_bootstrap
from app.services import jobs as jobs_service
from app.services.jobs import create_or_analyze_job, list_job_summaries, list_jobs, update_job_status
from app.services.profile import analyze_profile


USER_ID = UUID("00000000-0000-0000-0000-000000000101")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _ready_profile(session: Session, user_id: UUID = USER_ID, text: str | None = None) -> Profile:
    profile = Profile(user_id=user_id, status="needs_analysis")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.add(
        ProfileSource(
            user_id=user_id,
            profile_id=profile.id or 0,
            source_type="cv",
            title="cv.pdf",
            content_text=text
            or (
                "B.Sc. in Computer Science. Built backend projects with Python, FastAPI, SQL, "
                "React, TypeScript, Linux, and C++. Created an AI job tracker project."
            ),
        )
    )
    session.commit()
    analyze_profile(session, user_id)
    session.refresh(profile)
    return profile


def test_job_matching_requires_cv():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        try:
            create_or_analyze_job(
                session,
                USER_ID,
                JobCreateIn(
                    company="Example",
                    role="Backend Developer",
                    description_text="Requirements: Python, SQL, and React.",
                ),
            )
        except ValueError as exc:
            assert "CV" in str(exc)
        else:
            raise AssertionError("Expected CV requirement error.")


def test_duplicate_job_url_reuses_saved_job(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        payload = JobCreateIn(
            source_url="https://example.com/job/123/",
            company="Example",
            role="Backend Student",
            description_text="Student role. Requirements: Python, FastAPI, SQL, React.",
        )
        first = create_or_analyze_job(session, USER_ID, payload)
        second = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                source_url="https://example.com/job/123",
                company="Other",
                role="Other",
                description_text="Different pasted fallback should not matter for URL dedupe.",
            ),
        )
        jobs = session.exec(select(Job)).all()

    assert first.id == second.id
    assert len(jobs) == 1


def test_experience_mismatch_heavily_lowers_score():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        junior = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Fit Co",
                role="Backend Student",
                description_text="Student role. Requirements: Python, FastAPI, SQL, React.",
            ),
        )
        senior = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Senior Co",
                role="Senior Backend Engineer",
                description_text="Requirements: Python, FastAPI, SQL, React, and 5+ years of professional backend experience.",
            ),
        )

    assert junior.match is not None
    assert senior.match is not None
    assert junior.match.score - senior.match.score >= 25
    assert senior.match.fit_level == "Weak"
    assert senior.match.missing_blockers


def test_aligned_internship_uses_project_evidence_instead_of_weak_skill_listings():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(
            session,
            text=(
                "B.Sc. Computer Science student, 2 semesters remaining.\n"
                "Skills\nPython, Docker, React, FastAPI\nProjects\n"
                "Built an evidence-based matching platform using Python, FastAPI, React and\nDocker."
            ),
        )
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Calibration Co",
                role="Cloud Platform Intern",
                description_text=(
                    "Student internship. Requirements: currently pursuing a B.Sc. in Computer Science "
                    "with at least 2 semesters remaining. Required skills: Python and Docker. "
                    "Preferred skills: React and FastAPI. No professional experience required."
                ),
            ),
        )

    assert job.match is not None
    assert job.match.score >= 70
    assert not any("python" in gap.lower() or "docker" in gap.lower() for gap in job.match.gaps)
    assert "built built" not in job.match.resume_advice.about_text.lower()


def test_missing_must_have_hurts_more_than_missing_preferred():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        missing_must = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Systems Co",
                role="Firmware Developer",
                description_text="Requirements: embedded firmware and Linux. Preferred: Python and React.",
            ),
        )
        missing_preferred = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Backend Co",
                role="Backend Developer",
                description_text="Requirements: Python and SQL. Preferred: Kubernetes and AWS.",
            ),
        )

    assert missing_must.match is not None
    assert missing_preferred.match is not None
    assert missing_preferred.match.score > missing_must.match.score
    assert any("must-have" in blocker.lower() for blocker in missing_must.match.missing_blockers)


def test_resume_advice_and_status_are_saved():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Advice Co",
                role="Full Stack Student",
                description_text="Student role. Requirements: React, TypeScript, Python, SQL.",
            ),
        )
        updated = update_job_status(session, USER_ID, job.id, "Applied")
        searched = list_jobs(session, USER_ID, query="Advice")

    assert updated.match is not None
    assert updated.match.status == "Applied"
    assert updated.match.resume_advice.projects
    assert updated.match.resume_advice.skill_order
    assert updated.match.resume_advice.template_id
    assert "<" not in updated.match.resume_advice.about_text
    assert updated.match.model_version == "fit-v2.4.0"
    assert [event.status for event in updated.match.status_history] == ["Lead", "Applied"]
    assert [job.id for job in searched] == [job.id]


def test_job_summaries_omit_heavy_detail_but_keep_match_signal():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Summary Co",
                role="Backend Developer",
                description_text="Requirements: Python, FastAPI, SQL. Preferred: React and Docker.",
            ),
        )
        summaries = list_job_summaries(session, USER_ID, query="Summary")
        skill_summaries = list_job_summaries(session, USER_ID, query="FastAPI")

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.id == job.id
    assert summary.match is not None
    assert summary.match.score == job.match.score
    assert summary.top_skills
    assert summary.requirement_summary
    assert not hasattr(summary, "description_text")
    assert not hasattr(summary.match, "resume_advice")
    assert [item.id for item in skill_summaries] == [job.id]


def test_job_lists_never_recalculate_matches(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Read Only Co",
                role="Backend Developer",
                description_text="Requirements: Python and SQL.",
            ),
        )
        monkeypatch.setattr(
            jobs_service,
            "save_match",
            lambda *_: pytest.fail("list endpoint attempted to mutate a match"),
        )

        summaries = list_job_summaries(session, USER_ID)
        full_jobs = list_jobs(session, USER_ID)

    assert [item.id for item in summaries] == [job.id]
    assert [item.id for item in full_jobs] == [job.id]


def test_workspace_bootstrap_returns_profile_and_lightweight_jobs():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Bootstrap Co",
                role="Backend Developer",
                description_text="Requirements: Python and SQL.",
            ),
        )

        result = workspace_bootstrap(50, USER_ID, session)

    assert result.user_id == str(USER_ID)
    assert result.profile.status == "ready"
    assert [item.id for item in result.jobs] == [job.id]


def test_job_scan_records_agent_workflow_trace():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Agent Co",
                role="Backend Developer",
                description_text="Requirements: Python, FastAPI, SQL. Preferred: React.",
            ),
        )
        runs = session.exec(select(AgentRun)).all()
        steps = session.exec(select(AgentStep).order_by(AgentStep.id)).all()

    assert len(runs) == 1
    assert runs[0].workflow_type == "job_reader"
    assert runs[0].subject_id == job.id
    assert runs[0].status == "completed"
    assert job.agent_run is not None
    assert job.agent_run.status == "completed"
    assert [step.step_key for step in steps] == [
        "validate_profile",
        "dedupe_lookup",
        "extract_job",
        "classify_requirements",
        "match_profile_evidence",
        "validate_resume_advice",
    ]
    assert all(step.status == "completed" for step in steps)


def test_duplicate_job_records_reused_agent_run():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        payload = JobCreateIn(
            source_url="https://example.com/job/agent",
            company="Agent Co",
            role="Backend Developer",
            description_text="Requirements: Python, FastAPI, SQL.",
        )
        first = create_or_analyze_job(session, USER_ID, payload)
        second = create_or_analyze_job(session, USER_ID, payload)
        runs = session.exec(select(AgentRun).order_by(AgentRun.id)).all()

    assert first.id == second.id
    assert len(runs) == 2
    assert runs[-1].status == "reused"
    assert second.agent_run is not None
    assert second.agent_run.status == "reused"
