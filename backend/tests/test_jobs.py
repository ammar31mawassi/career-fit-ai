from __future__ import annotations

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from uuid import UUID

from app.models import Job, Profile, ProfileFact, ProfileSource
from app.schemas import JobCreateIn
from app.services.jobs import create_or_analyze_job, list_jobs, update_job_status
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
    assert updated.match.model_version == "fit-v2.1.0"
    assert [event.status for event in updated.match.status_history] == ["Lead", "Applied"]
    assert [job.id for job in searched] == [job.id]
