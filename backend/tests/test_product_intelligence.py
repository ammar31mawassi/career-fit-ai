from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import EvaluationExample, Job, JobRequirementRevision, JobScan, Profile, ProfileFact
from app.schemas import JobCreateIn, JobRequirementsReviewIn
from app.services.job_scans import (
    cancel_job_scan,
    create_job_scan,
    process_one_queued_scan,
    process_user_scan,
)
from app.services.jobs import create_or_analyze_job, list_job_summary_page, review_job_requirements
from app.services.telemetry import evaluation_split


USER_ID = UUID("00000000-0000-0000-0000-000000000901")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _ready_profile(session: Session) -> Profile:
    profile = Profile(user_id=USER_ID, status="ready", onboarding_completed=True)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.add(
        ProfileFact(
            user_id=USER_ID,
            profile_id=profile.id or 0,
            fact_type="skill",
            value="python",
            evidence="Built a Python service.",
            confidence=.9,
            user_approved=True,
            review_status="approved",
        )
    )
    session.commit()
    return profile


def test_scan_is_persisted_before_processing_and_finishes_with_result():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        queued = create_job_scan(
            session,
            USER_ID,
            JobCreateIn(
                company="Durable Systems",
                role="Python Intern",
                description_text="Student internship. Requirements: Python.",
            ),
        )
        assert queued.status == "queued"
        assert session.get(JobScan, queued.id) is not None

        completed = process_user_scan(session, USER_ID, queued.id)

    assert completed.status == "succeeded"
    assert completed.progress == 100
    assert completed.current_step == "ready"
    assert completed.result_job is not None
    assert completed.result_job.role == "Python Intern"


def test_queued_scan_can_be_cancelled_and_duplicate_active_input_is_reused():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(company="Example", role="Intern", description_text="Requirements: Python.")
    with Session(engine) as session:
        _ready_profile(session)
        first = create_job_scan(session, USER_ID, payload)
        duplicate = create_job_scan(session, USER_ID, payload)
        cancelled = cancel_job_scan(session, USER_ID, first.id)

    assert duplicate.id == first.id
    assert cancelled.status == "cancelled"


def test_stale_running_scan_is_reclaimed():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(company="Lease Test", role="Intern", description_text="Requirements: Python.")
    with Session(engine) as session:
        _ready_profile(session)
        queued = create_job_scan(session, USER_ID, payload)
        scan = session.get(JobScan, queued.id)
        assert scan is not None
        scan.status = "running"
        scan.attempts = 1
        scan.updated_at = datetime.now(timezone.utc) - timedelta(minutes=9)
        session.add(scan)
        session.commit()

        recovered = process_one_queued_scan(session)

    assert recovered is not None
    assert recovered.status == "succeeded"


def test_stale_scan_retry_count_is_bounded():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(company="Lease Test", role="Intern", description_text="Requirements: Python.")
    with Session(engine) as session:
        _ready_profile(session)
        queued = create_job_scan(session, USER_ID, payload)
        scan = session.get(JobScan, queued.id)
        assert scan is not None
        scan.status = "running"
        scan.attempts = 3
        scan.updated_at = datetime.now(timezone.utc) - timedelta(minutes=9)
        session.add(scan)
        session.commit()

        exhausted = process_one_queued_scan(session)

    assert exhausted is not None
    assert exhausted.status == "failed"
    assert exhausted.error_code == "SCAN_LEASE_EXPIRED"


def test_requirement_review_persists_original_and_labeled_feature_snapshot():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Correction Labs",
                role="Software Intern",
                description_text="Intern position. Requirements: Python and Docker.",
            ),
        )
        updated = review_job_requirements(
            session,
            USER_ID,
            job.id,
            JobRequirementsReviewIn(
                must_have_skills=["python"],
                preferred_skills=["docker"],
                min_years_experience=0,
                experience_requirement_known=False,
                seniority="student",
                domain="software",
            ),
        )
        revision = session.exec(select(JobRequirementRevision)).one()
        example = session.exec(select(EvaluationExample)).one()

    assert updated.requirements.seniority == "student"
    assert updated.requirements.reader_version.endswith("+user-reviewed")
    assert "must_have_skills" in revision.changed_fields_json
    assert example.example_type == "job_requirement_review"
    assert example.label == "corrected"
    assert "description" not in example.features_json


def test_job_summary_cursor_has_no_duplicates_and_stable_user_split():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        now = datetime.now(timezone.utc)
        for index in range(35):
            session.add(
                Job(
                    user_id=USER_ID,
                    content_hash=f"job-{index}",
                    company="Paged Co",
                    role=f"Role {index}",
                    requirements_json="{}",
                    updated_at=now - timedelta(minutes=index),
                )
            )
        session.commit()
        first = list_job_summary_page(session, USER_ID, limit=20)
        second = list_job_summary_page(session, USER_ID, limit=20, cursor=first.next_cursor or "")

    assert len(first.items) == 20
    assert len(second.items) == 15
    assert {item.id for item in first.items}.isdisjoint({item.id for item in second.items})
    assert evaluation_split(USER_ID) == evaluation_split(USER_ID)
