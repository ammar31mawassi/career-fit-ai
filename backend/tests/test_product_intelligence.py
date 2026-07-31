from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    AgentRun,
    EvaluationExample,
    Job,
    JobRequirementRevision,
    JobScan,
    Profile,
    ProfileFact,
    ProfileSource,
)
from app.schemas import JobCreateIn, JobRequirementsReviewIn
from app.services import job_scans as job_scan_service
from app.services.job_scans import (
    cancel_job_scan,
    create_job_scan,
    latest_active_scan,
    process_one_queued_scan,
    process_user_scan,
)
from app.services.jobs import create_or_analyze_job, list_job_summary_page, review_job_requirements
from app.services.label_coverage import build_label_coverage
from app.services.telemetry import evaluation_split


USER_ID = UUID("00000000-0000-0000-0000-000000000901")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _complete_job_description(details: str) -> str:
    return (
        f"{details} Responsibilities: deliver maintainable production software, review changes, "
        "document decisions, investigate failures, and collaborate with engineering partners. "
        "Qualifications include communication, dependable execution, and practical problem solving."
    )


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
    session.add(
        ProfileSource(
            user_id=USER_ID,
            profile_id=profile.id or 0,
            source_type="cv",
            title="cv.pdf",
            content_text=(
                "B.Sc. Computer Science graduate. Built production Python services with SQL, "
                "testing, monitoring, API design, documentation, and collaborative code review."
            ),
        )
    )
    session.commit()
    profile.last_analyzed_at = datetime.now(timezone.utc)
    session.add(profile)
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
                description_text=_complete_job_description(
                    "Student internship. Requirements: Python."
                ),
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


def test_invalid_pasted_scan_is_rejected_before_queue_persistence():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)

        with pytest.raises(ValueError, match="complete job description"):
            create_job_scan(
                session,
                USER_ID,
                JobCreateIn(
                    company="Noise Inc",
                    role="Developer",
                    description_text="Click here to apply.",
                ),
            )

        assert list(session.exec(select(JobScan)).all()) == []
        assert list(session.exec(select(AgentRun)).all()) == []


def test_queued_scan_can_be_cancelled_and_duplicate_active_input_is_reused():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(
        company="Example",
        role="Intern",
        description_text=_complete_job_description("Requirements: Python."),
    )
    with Session(engine) as session:
        _ready_profile(session)
        first = create_job_scan(session, USER_ID, payload)
        duplicate = create_job_scan(session, USER_ID, payload)
        cancelled = cancel_job_scan(session, USER_ID, first.id)

    assert duplicate.id == first.id
    assert cancelled.status == "cancelled"


@pytest.mark.parametrize(("first_consent", "second_consent"), [(True, False), (False, True)])
def test_active_scan_is_not_reused_when_public_contribution_consent_changes(
    first_consent: bool,
    second_consent: bool,
):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    base_payload = JobCreateIn(
        company="Consent Example",
        role="Intern",
        description_text=_complete_job_description("Requirements: Python."),
    )
    with Session(engine) as session:
        _ready_profile(session)
        first = create_job_scan(
            session,
            USER_ID,
            base_payload.model_copy(update={"contribute_public_posting": first_consent}),
        )
        second = create_job_scan(
            session,
            USER_ID,
            base_payload.model_copy(update={"contribute_public_posting": second_consent}),
        )
        scans = list(session.exec(select(JobScan).order_by(JobScan.id)))

    assert second.id != first.id
    assert [JobCreateIn.model_validate_json(scan.payload_json).contribute_public_posting for scan in scans] == [
        first_consent,
        second_consent,
    ]


def test_stale_running_scan_is_reclaimed():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(
        company="Lease Test",
        role="Intern",
        description_text=_complete_job_description("Requirements: Python."),
    )
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
    payload = JobCreateIn(
        company="Lease Test",
        role="Intern",
        description_text=_complete_job_description("Requirements: Python."),
    )
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


def test_active_input_database_invariant_blocks_duplicate_writers():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            JobScan(
                user_id=USER_ID,
                input_hash="same-active-input",
                status="queued",
            )
        )
        session.commit()
        session.add(
            JobScan(
                user_id=USER_ID,
                input_hash="same-active-input",
                status="running",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        first = session.exec(
            select(JobScan).where(JobScan.input_hash == "same-active-input")
        ).one()
        first.status = "cancelled"
        session.add(first)
        session.commit()
        session.add(
            JobScan(
                user_id=USER_ID,
                input_hash="same-active-input",
                status="queued",
            )
        )
        session.commit()

        scans = list(
            session.exec(
                select(JobScan).where(JobScan.input_hash == "same-active-input")
            ).all()
        )

    assert {scan.status for scan in scans} == {"cancelled", "queued"}


def test_latest_active_scan_is_user_scoped_and_ignores_terminal_scans():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    other_user_id = UUID("00000000-0000-0000-0000-000000000902")
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(
            JobScan(
                user_id=USER_ID,
                input_hash="terminal",
                status="succeeded",
                created_at=now + timedelta(minutes=2),
            )
        )
        expected = JobScan(
            user_id=USER_ID,
            input_hash="active",
            status="running",
            created_at=now + timedelta(minutes=1),
        )
        session.add(expected)
        session.add(
            JobScan(
                user_id=other_user_id,
                input_hash="other-user",
                status="queued",
                created_at=now + timedelta(minutes=3),
            )
        )
        session.commit()
        session.refresh(expected)

        active = latest_active_scan(session, USER_ID)

    assert active is not None
    assert active.id == expected.id
    assert active.status == "running"


def test_latest_active_scan_returns_none_when_no_active_scan_exists():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            JobScan(
                user_id=USER_ID,
                input_hash="terminal",
                status="cancelled",
            )
        )
        session.commit()

        active = latest_active_scan(session, USER_ID)

    assert active is None


def test_only_one_worker_can_compare_and_set_claim_a_queued_scan():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(
        company="CAS Labs",
        role="Intern",
        description_text=_complete_job_description("Requirements: Python."),
    )
    with Session(engine) as setup:
        _ready_profile(setup)
        queued = create_job_scan(setup, USER_ID, payload)

    with Session(engine) as first_worker, Session(engine) as second_worker:
        first_seen = first_worker.get(JobScan, queued.id)
        second_seen = second_worker.get(JobScan, queued.id)
        assert first_seen is not None and first_seen.status == "queued"
        assert second_seen is not None and second_seen.status == "queued"

        first_claim = job_scan_service._claim_queued_scan(
            first_worker,
            USER_ID,
            queued.id,
        )
        second_claim = job_scan_service._claim_queued_scan(
            second_worker,
            USER_ID,
            queued.id,
        )

    assert first_claim is not None
    assert second_claim is None
    with Session(engine) as verify:
        claimed = verify.get(JobScan, queued.id)
        assert claimed is not None
        assert claimed.status == "running"
        assert claimed.attempts == 1
        assert claimed.lease_token == first_claim[1]


def test_cancel_wins_without_being_overwritten_by_the_worker_lease():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(
        company="Cancellation Labs",
        role="Intern",
        description_text=_complete_job_description("Requirements: Python."),
    )
    with Session(engine) as setup:
        _ready_profile(setup)
        queued = create_job_scan(setup, USER_ID, payload)

    with Session(engine) as worker:
        claim = job_scan_service._claim_queued_scan(worker, USER_ID, queued.id)
        assert claim is not None
        lease_token = claim[1]

    with Session(engine) as user_session:
        requested = cancel_job_scan(user_session, USER_ID, queued.id)
        assert requested.status == "cancel_requested"

    with Session(engine) as worker:
        assert not job_scan_service._heartbeat_claim(
            worker,
            queued.id,
            lease_token,
            "fetch_job",
            20,
        )
        assert job_scan_service._finalize_cancel_requested(
            worker,
            queued.id,
            lease_token,
        )

    with Session(engine) as verify:
        cancelled = verify.get(JobScan, queued.id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.lease_token == ""


def test_stale_worker_token_cannot_touch_the_reclaimed_attempt():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(
        company="Lease Rotation",
        role="Intern",
        description_text=_complete_job_description("Requirements: Python."),
    )
    with Session(engine) as setup:
        _ready_profile(setup)
        queued = create_job_scan(setup, USER_ID, payload)
        scan = setup.get(JobScan, queued.id)
        assert scan is not None
        scan.status = "running"
        scan.attempts = 1
        scan.lease_token = "expired-worker-token"
        scan.updated_at = datetime.now(timezone.utc) - timedelta(minutes=9)
        setup.add(scan)
        setup.commit()

    with Session(engine) as recovery:
        stale = recovery.get(JobScan, queued.id)
        assert stale is not None
        assert job_scan_service._release_stale_claim(recovery, stale)
        replacement = job_scan_service._claim_queued_scan(
            recovery,
            USER_ID,
            queued.id,
        )
        assert replacement is not None
        replacement_token = replacement[1]
        assert replacement_token != "expired-worker-token"
        assert not job_scan_service._heartbeat_claim(
            recovery,
            queued.id,
            "expired-worker-token",
            "stale-write",
            90,
        )

    with Session(engine) as verify:
        current = verify.get(JobScan, queued.id)
        assert current is not None
        assert current.status == "running"
        assert current.attempts == 2
        assert current.lease_token == replacement_token
        assert current.current_step != "stale-write"


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
                description_text=_complete_job_description(
                    "Intern position. Requirements: Python and Docker."
                ),
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
        second = list_job_summary_page(
            session,
            USER_ID,
            limit=20,
            cursor=first.next_cursor or "",
            watermark=first.watermark,
        )

    assert len(first.items) == 20
    assert len(second.items) == 15
    assert {item.id for item in first.items}.isdisjoint({item.id for item in second.items})
    assert evaluation_split(USER_ID) == evaluation_split(USER_ID)


def test_job_summary_cursor_keeps_the_initial_page_watermark():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        now = datetime.now(timezone.utc)
        for index in range(3):
            session.add(
                Job(
                    user_id=USER_ID,
                    content_hash=f"snapshot-job-{index}",
                    company="Snapshot Co",
                    role=f"Role {index}",
                    requirements_json="{}",
                    updated_at=now - timedelta(minutes=index),
                )
            )
        session.commit()
        first = list_job_summary_page(session, USER_ID, limit=1)
        session.add(
            Job(
                user_id=USER_ID,
                content_hash="snapshot-job-new",
                company="Newer Co",
                role="New role",
                requirements_json="{}",
                updated_at=now + timedelta(minutes=1),
            )
        )
        session.commit()
        second = list_job_summary_page(
            session,
            USER_ID,
            limit=1,
            cursor=first.next_cursor or "",
            watermark=first.watermark,
        )

    assert first.watermark is not None
    assert second.watermark == first.watermark
    assert all(item.company != "Newer Co" for item in second.items)


def test_label_coverage_reports_sparse_splits_and_safe_segments():
    rows = [
        EvaluationExample(
            user_id=USER_ID,
            example_type="profile_fact_review",
            split="train",
            label="approved",
            model_version="extractor-v1",
            features_json='{"fact_type":"skill","evidence_type":"project"}',
        ),
        EvaluationExample(
            user_id=USER_ID,
            example_type="job_requirement_review",
            split="validation",
            label="corrected",
            model_version="reader-v1",
            features_json='{"changed_fields":["seniority","must_have_skills"]}',
        ),
    ]

    report = build_label_coverage(rows, {"train": 2, "validation": 1, "test": 1})

    assert report["training_gate_passed"] is False
    assert report["by_split"] == {"train": 1, "validation": 1}
    assert report["segments"] == {
        "fact_type": {"skill": 1},
        "evidence_type": {"project": 1},
        "corrected_requirement_field": {"must_have_skills": 1, "seniority": 1},
    }
    assert all("user" not in warning.lower() for warning in report["warnings"])


def test_label_coverage_gate_passes_with_broad_minimums_met():
    rows = [
        EvaluationExample(
            user_id=USER_ID,
            example_type=example_type,
            split=split,
            label="approved",
            features_json="{}",
        )
        for split, example_type in [
            ("train", "profile_fact_review"),
            ("validation", "job_requirement_review"),
            ("test", "profile_fact_review"),
        ]
    ]

    report = build_label_coverage(rows, {"train": 1, "validation": 1, "test": 1})

    assert report["training_gate_passed"] is True
    assert report["warnings"] == []
