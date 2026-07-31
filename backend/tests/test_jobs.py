from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import pytest
from app.models import (
    AgentRun,
    AgentStep,
    ExtractionMetric,
    Job,
    JobMatch,
    JobStatusEvent,
    Profile,
    ProfileFact,
    ProfileSource,
    ResumeAdvice,
    SharedJobCatalog,
)
from app.schemas import JobCreateIn, JobStatusPatchIn
from app.api.routes import workspace_bootstrap
from app.services import jobs as jobs_service
from app.services.job_research import ExtractedJob, classify_requirements
from app.services.jobs import create_or_analyze_job, list_job_summaries, list_jobs, update_job_status
from app.services.profile import analyze_profile


USER_ID = UUID("00000000-0000-0000-0000-000000000101")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _complete_job_description(details: str) -> str:
    return (
        f"{details} Responsibilities: build and maintain production software, review changes, "
        "document technical decisions, and collaborate with product and engineering partners. "
        "Qualifications include clear communication, reliable delivery, and practical problem solving."
    )


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
            description_text=_complete_job_description(
                "Student role. Requirements: Python, FastAPI, SQL, React."
            ),
        )
        first = create_or_analyze_job(session, USER_ID, payload)
        second = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                source_url="https://example.com/job/123",
                company="Other",
                role="Other",
                description_text=_complete_job_description(
                    "Different pasted fallback should not matter for URL dedupe."
                ),
            ),
        )
        jobs = session.exec(select(Job)).all()

    assert first.id == second.id
    assert len(jobs) == 1


def test_pasted_job_analysis_stays_private_and_out_of_shared_catalog():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Private Recruiter",
                role="Backend Developer",
                description_text=_complete_job_description(
                    "Confidential recruiter notes for this candidate. "
                    "Requirements: Python, FastAPI, and SQL."
                ),
            ),
        )
        metric = session.exec(
            select(ExtractionMetric).where(
                ExtractionMetric.workflow_type == "job_extraction",
                ExtractionMetric.subject_id == job.id,
            )
        ).one()
        catalogs = list(session.exec(select(SharedJobCatalog)).all())

    assert metric.strategy == "pasted"
    assert catalogs == []


def test_successfully_fetched_public_job_enters_shared_catalog(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    description = "Public posting. Requirements: Python, FastAPI, and SQL."
    requirements = classify_requirements(description, "Backend Developer")
    monkeypatch.setattr(
        jobs_service,
        "extract_job_from_input",
        lambda *_args: ExtractedJob(
            source_url="https://example.com/jobs/public-backend",
            company="Public Co",
            role="Backend Developer",
            location="Remote",
            description_text=description,
            source_title="Backend Developer at Public Co",
            source_confidence=0.9,
            application_link="https://example.com/jobs/public-backend/apply",
            reader_strategy="scoped_html",
            requirements=requirements,
        ),
    )

    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                source_url="https://example.com/jobs/public-backend",
                contribute_public_posting=True,
            ),
        )
        catalog = session.exec(select(SharedJobCatalog)).one()
        metric = session.exec(
            select(ExtractionMetric).where(
                ExtractionMetric.workflow_type == "job_extraction",
                ExtractionMetric.subject_id == job.id,
            )
        ).one()

    assert metric.strategy == "scoped_html"
    assert catalog.description_text == description
    assert catalog.first_seen_by == USER_ID


def test_successfully_fetched_public_job_stays_private_without_consent(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    description = "Public posting. Requirements: Python, FastAPI, and SQL."
    requirements = classify_requirements(description, "Backend Developer")
    monkeypatch.setattr(
        jobs_service,
        "extract_job_from_input",
        lambda *_args: ExtractedJob(
            source_url="https://example.com/jobs/private-by-default",
            company="Private By Default Co",
            role="Backend Developer",
            location="Remote",
            description_text=description,
            source_title="Backend Developer at Private By Default Co",
            source_confidence=0.9,
            application_link="https://example.com/jobs/private-by-default/apply",
            reader_strategy="scoped_html",
            requirements=requirements,
        ),
    )

    with Session(engine) as session:
        _ready_profile(session)
        create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(source_url="https://example.com/jobs/private-by-default"),
        )
        catalogs = list(session.exec(select(SharedJobCatalog)).all())

    assert catalogs == []


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
                description_text=_complete_job_description(
                    "Student role. Requirements: Python, FastAPI, SQL, React."
                ),
            ),
        )
        senior = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Senior Co",
                role="Senior Backend Engineer",
                description_text=_complete_job_description(
                    "Requirements: Python, FastAPI, SQL, React, and 5+ years of professional backend experience."
                ),
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
                description_text=_complete_job_description(
                    "Requirements: embedded firmware and Linux. Preferred: Python and React."
                ),
            ),
        )
        missing_preferred = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Backend Co",
                role="Backend Developer",
                description_text=_complete_job_description(
                    "Requirements: Python and SQL. Preferred: Kubernetes and AWS."
                ),
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
                description_text=_complete_job_description(
                    "Student role. Requirements: React, TypeScript, Python, SQL."
                ),
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
    assert updated.match.status_history[0].previous_status is None
    assert updated.match.status_history[0].source == "system"
    assert updated.match.status_history[1].previous_status == "Lead"
    assert updated.match.status_history[1].source == "user"
    assert [job.id for job in searched] == [job.id]


def test_status_event_keeps_observed_time_note_and_is_idempotent():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    occurred_at = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Timeline Co",
                role="Backend Developer",
                description_text=_complete_job_description(
                    "Requirements: Python, FastAPI, SQL."
                ),
            ),
        )
        first = update_job_status(
            session,
            USER_ID,
            job.id,
            "Interview",
            occurred_at=occurred_at,
            note="  Recruiter screen completed.  ",
        )
        stored_match = session.get(JobMatch, first.match.id if first.match else 0)
        assert stored_match is not None
        unchanged_updated_at = stored_match.updated_at
        repeated = update_job_status(
            session,
            USER_ID,
            job.id,
            "Interview",
            occurred_at=datetime.now(timezone.utc) + timedelta(days=1),
            note="x" * 501,
        )
        session.expire_all()
        stored_match = session.get(JobMatch, first.match.id if first.match else 0)

    assert first.match is not None
    assert repeated.match is not None
    assert len(repeated.match.status_history) == 2
    event = repeated.match.status_history[-1]
    assert event.previous_status == "Lead"
    assert event.status == "Interview"
    stored_occurred_at = (
        event.occurred_at
        if event.occurred_at.tzinfo is not None
        else event.occurred_at.replace(tzinfo=timezone.utc)
    )
    stored_created_at = (
        event.created_at
        if event.created_at.tzinfo is not None
        else event.created_at.replace(tzinfo=timezone.utc)
    )
    assert stored_occurred_at == occurred_at
    assert stored_created_at >= stored_occurred_at
    assert event.source == "user"
    assert event.note == "Recruiter screen completed."
    assert stored_match is not None
    assert stored_match.updated_at == unchanged_updated_at


def test_status_event_rejects_future_business_time():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Future Co",
                role="Backend Developer",
                description_text=_complete_job_description("Requirements: Python, SQL."),
            ),
        )
        with pytest.raises(ValueError, match="cannot be in the future"):
            update_job_status(
                session,
                USER_ID,
                job.id,
                "Applied",
                occurred_at=datetime.now(timezone.utc) + timedelta(days=1),
            )


def test_status_event_rejects_ambiguous_naive_business_time():
    with pytest.raises(ValueError, match="must include a timezone"):
        JobStatusPatchIn(
            status="Applied",
            occurred_at=datetime(2026, 7, 20, 12),
        )

    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _ready_profile(session)
        job = create_or_analyze_job(
            session,
            USER_ID,
            JobCreateIn(
                company="Timezone Co",
                role="Backend Developer",
                description_text=_complete_job_description(
                    "Requirements: Python, SQL."
                ),
            ),
        )
        with pytest.raises(ValueError, match="must include a timezone"):
            update_job_status(
                session,
                USER_ID,
                job.id,
                "Applied",
                occurred_at=datetime(2026, 7, 20, 12),
            )


def test_save_match_recovers_when_a_concurrent_match_wins_the_unique_race(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = _ready_profile(session)
        requirements = classify_requirements(
            "Requirements: Python, FastAPI, and SQL.",
            "Backend Developer",
        )
        job = Job(
            user_id=USER_ID,
            content_hash="concurrent-match-winner",
            company="Race Co",
            role="Backend Developer",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        jobs_service.save_match(session, USER_ID, profile, job)
        update_job_status(session, USER_ID, job.id or 0, "Applied")

        original_exec = session.exec
        hid_match_once = False

        class MissingMatch:
            @staticmethod
            def first():
                return None

        def stale_match_read(statement, *args, **kwargs):
            nonlocal hid_match_once
            rendered = str(statement).lower()
            if not hid_match_once and "from job_matches" in rendered:
                hid_match_once = True
                return MissingMatch()
            return original_exec(statement, *args, **kwargs)

        monkeypatch.setattr(session, "exec", stale_match_read)
        recovered = jobs_service.save_match(session, USER_ID, profile, job)
        session.expire_all()
        matches = list(session.exec(select(JobMatch)).all())
        advice = list(session.exec(select(ResumeAdvice)).all())
        history = list(
            session.exec(
                select(JobStatusEvent).order_by(JobStatusEvent.created_at, JobStatusEvent.id)
            ).all()
        )

    assert hid_match_once is True
    assert recovered.id == matches[0].id
    assert len(matches) == 1
    assert matches[0].status == "Applied"
    assert len(advice) == 1
    assert [event.status for event in history] == ["Lead", "Applied"]


def test_save_match_recovers_when_concurrent_advice_wins_the_unique_race(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = _ready_profile(session)
        requirements = classify_requirements(
            "Requirements: React, TypeScript, Python, and SQL.",
            "Full Stack Developer",
        )
        job = Job(
            user_id=USER_ID,
            content_hash="concurrent-advice-winner",
            company="Advice Race Co",
            role="Full Stack Developer",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        original_match = jobs_service.save_match(session, USER_ID, profile, job)

        original_exec = session.exec
        hid_advice_once = False

        class MissingAdvice:
            @staticmethod
            def first():
                return None

        def stale_advice_read(statement, *args, **kwargs):
            nonlocal hid_advice_once
            rendered = str(statement).lower()
            if not hid_advice_once and "from resume_advice" in rendered:
                hid_advice_once = True
                return MissingAdvice()
            return original_exec(statement, *args, **kwargs)

        monkeypatch.setattr(session, "exec", stale_advice_read)
        recovered = jobs_service.save_match(session, USER_ID, profile, job)
        session.expire_all()
        matches = list(session.exec(select(JobMatch)).all())
        advice = list(session.exec(select(ResumeAdvice)).all())
        history = list(session.exec(select(JobStatusEvent)).all())

    assert hid_advice_once is True
    assert recovered.id == original_match.id
    assert len(matches) == 1
    assert len(advice) == 1
    assert advice[0].match_id == recovered.id
    assert [event.status for event in history] == ["Lead"]


def test_save_match_failure_rolls_back_the_entire_caller_owned_unit(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = _ready_profile(session)
        requirements = classify_requirements(
            "Requirements: Python and SQL.",
            "Backend Developer",
        )
        job = Job(
            user_id=USER_ID,
            content_hash="atomic-match-failure",
            company="Atomic Co",
            role="Original Role",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id or 0
        job.role = "Uncommitted Role"
        session.add(job)

        original_add = session.add

        def fail_advice_add(instance, *args, **kwargs):
            if isinstance(instance, ResumeAdvice):
                raise RuntimeError("advice persistence failed")
            return original_add(instance, *args, **kwargs)

        monkeypatch.setattr(session, "add", fail_advice_add)
        with pytest.raises(RuntimeError, match="advice persistence failed"):
            jobs_service.save_match(
                session,
                USER_ID,
                profile,
                job,
                commit=False,
            )

        assert session.in_transaction() is False
        persisted_job = session.get(Job, job_id)
        matches = list(session.exec(select(JobMatch)).all())
        advice = list(session.exec(select(ResumeAdvice)).all())
        history = list(session.exec(select(JobStatusEvent)).all())

    assert persisted_job is not None and persisted_job.role == "Original Role"
    assert matches == []
    assert advice == []
    assert history == []


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
                description_text=_complete_job_description(
                    "Requirements: Python, FastAPI, SQL. Preferred: React and Docker."
                ),
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
                description_text=_complete_job_description("Requirements: Python and SQL."),
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
                description_text=_complete_job_description("Requirements: Python and SQL."),
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
                description_text=_complete_job_description(
                    "Requirements: Python, FastAPI, SQL. Preferred: React."
                ),
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
            description_text=_complete_job_description("Requirements: Python, FastAPI, SQL."),
        )
        first = create_or_analyze_job(session, USER_ID, payload)
        second = create_or_analyze_job(session, USER_ID, payload)
        runs = session.exec(select(AgentRun).order_by(AgentRun.id)).all()

    assert first.id == second.id
    assert len(runs) == 2
    assert runs[-1].status == "reused"
    assert second.agent_run is not None
    assert second.agent_run.status == "reused"
    first_extraction = next(
        step for step in first.agent_run.steps if step.step_key == "extract_job"
    ) if first.agent_run is not None else None
    reused_extraction = next(
        step for step in second.agent_run.steps if step.step_key == "extract_job"
    )
    assert first_extraction is not None
    assert reused_extraction.output == {
        "reader_strategy": first_extraction.output["reader_strategy"],
        "reader_version": first_extraction.output["reader_version"],
    }


def test_failed_rescan_reuses_only_stored_extraction_provenance(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    payload = JobCreateIn(
        source_url="https://example.com/job/fallback-provenance",
        company="Fallback Co",
        role="Backend Developer",
        description_text=_complete_job_description(
            "Requirements: Python, FastAPI, SQL."
        ),
    )
    with Session(engine) as session:
        _ready_profile(session)
        first = create_or_analyze_job(session, USER_ID, payload)
        monkeypatch.setattr(jobs_service, "OUTPUT_POLICY_VERSION", "future-policy")

        def fail_extraction(*_args):
            raise RuntimeError("simulated extraction failure")

        monkeypatch.setattr(jobs_service, "extract_job_from_input", fail_extraction)
        fallback = create_or_analyze_job(session, USER_ID, payload)

    assert first.agent_run is not None
    assert fallback.agent_run is not None
    assert fallback.agent_run.status == "reused"
    original = next(
        step for step in first.agent_run.steps if step.step_key == "extract_job"
    )
    failed = next(
        step for step in fallback.agent_run.steps if step.step_key == "extract_job"
    )
    assert failed.status == "failed"
    assert failed.output == {
        "has_source_url": True,
        "provenance_origin": "stored_fallback",
        "reader_strategy": original.output["reader_strategy"],
        "reader_version": original.output["reader_version"],
    }
