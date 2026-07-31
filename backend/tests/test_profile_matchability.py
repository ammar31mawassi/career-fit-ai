from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import AgentRun, Job, JobScan, Profile, ProfileSource
from app.schemas import JobCreateIn
from app.services.job_scans import create_job_scan
from app.services.jobs import create_or_analyze_job, rematch_job
from app.services.profile import (
    MATCHABLE_PROFILE_REQUIRED,
    get_or_create_profile,
    profile_is_matchable,
)


USER_ID = UUID("00000000-0000-0000-0000-000000000805")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _readable_cv(profile: Profile, *, updated_at: datetime) -> ProfileSource:
    return ProfileSource(
        user_id=profile.user_id,
        profile_id=profile.id or 0,
        source_type="cv",
        title="cv.pdf",
        content_text=(
            "B.Sc. Computer Science graduate with hands-on Python, SQL, API design, testing, "
            "monitoring, deployment, technical documentation, and collaborative code review."
        ),
        updated_at=updated_at,
    )


def _complete_job_description() -> str:
    return (
        "Requirements: Python, SQL, testing, and API design. Responsibilities include building "
        "and maintaining production services, reviewing changes, documenting decisions, "
        "investigating failures, and collaborating with product and engineering partners."
    )


def test_get_or_create_profile_recovers_from_concurrent_unique_insert(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        winner = Profile(user_id=USER_ID)
        session.add(winner)
        session.commit()
        session.refresh(winner)
        real_exec = session.exec
        first_read = True

        class EmptyResult:
            @staticmethod
            def first():
                return None

        def stale_then_current(statement, *args, **kwargs):
            nonlocal first_read
            if first_read:
                first_read = False
                return EmptyResult()
            return real_exec(statement, *args, **kwargs)

        monkeypatch.setattr(session, "exec", stale_then_current)

        result = get_or_create_profile(session, USER_ID)
        persisted = list(real_exec(select(Profile).where(Profile.user_id == USER_ID)).all())

    assert result.id == winner.id
    assert len(persisted) == 1


def test_profile_matchability_requires_ready_readable_and_current_sources():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    analyzed_at = datetime.now(timezone.utc)

    with Session(engine) as session:
        profile = Profile(
            user_id=USER_ID,
            status="ready",
            last_analyzed_at=analyzed_at,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        cv = _readable_cv(profile, updated_at=analyzed_at - timedelta(seconds=1))
        session.add(cv)
        session.commit()

        assert profile_is_matchable(session, profile) is True

        cv.content_text = "too short"
        session.add(cv)
        session.commit()
        assert profile_is_matchable(session, profile) is False

        cv.content_text = _readable_cv(profile, updated_at=analyzed_at).content_text
        cv.updated_at = analyzed_at + timedelta(seconds=1)
        session.add(cv)
        session.commit()
        assert profile_is_matchable(session, profile) is False

        cv.updated_at = analyzed_at - timedelta(seconds=1)
        profile.last_analyzed_at = None
        session.add(cv)
        session.add(profile)
        session.commit()
        assert profile_is_matchable(session, profile) is False

        profile.last_analyzed_at = analyzed_at
        profile.status = "needs_analysis"
        session.add(profile)
        session.commit()
        assert profile_is_matchable(session, profile) is False


def test_all_job_matching_entry_points_reject_the_same_stale_profile():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    analyzed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = JobCreateIn(
        company="Invariant Co",
        role="Backend Developer",
        description_text=_complete_job_description(),
    )

    with Session(engine) as session:
        profile = Profile(
            user_id=USER_ID,
            status="ready",
            last_analyzed_at=analyzed_at,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(_readable_cv(profile, updated_at=analyzed_at + timedelta(minutes=1)))
        job = Job(
            user_id=USER_ID,
            content_hash="stale-profile-job",
            company="Invariant Co",
            role="Backend Developer",
            status="analyzed",
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        for operation in (
            lambda: create_or_analyze_job(session, USER_ID, payload),
            lambda: create_job_scan(session, USER_ID, payload),
            lambda: rematch_job(session, USER_ID, job.id or 0),
        ):
            with pytest.raises(ValueError, match="readable, current CV") as raised:
                operation()
            assert str(raised.value) == MATCHABLE_PROFILE_REQUIRED

        assert list(session.exec(select(JobScan)).all()) == []
        assert list(session.exec(select(AgentRun)).all()) == []
