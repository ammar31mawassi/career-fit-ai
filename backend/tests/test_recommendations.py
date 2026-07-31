from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.services import recommendations as recommendation_service
from app.models import (
    ExtractionMetric,
    Job,
    JobDiscoveryBetaMember,
    JobMatch,
    JobRecommendation,
    Profile,
    ProfileInterest,
    RecommendationEvent,
    RecommendationFieldCalibration,
    RecommendationRun,
    SharedJobCatalog,
)
from app.services.jobs import update_job_status
from app.services.job_research import classify_requirements
from app.services.job_routing import route_job_fields
from app.services.matcher import MODEL_VERSION
from app.services.recommendations import (
    catalog_and_enqueue_job,
    generate_shadow_recommendations,
    list_recommendations,
    process_one_queued_recommendation,
    record_recommendation_view,
    refresh_field_calibration,
    refresh_user_recommendations,
    update_recommendation,
)


SCANNER = UUID("00000000-0000-0000-0000-000000000201")
RELEVANT = UUID("00000000-0000-0000-0000-000000000202")
UNRELATED = UUID("00000000-0000-0000-0000-000000000203")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _profile(session: Session, user_id: UUID, interest: str) -> Profile:
    profile = Profile(
        user_id=user_id,
        status="ready",
        onboarding_completed=True,
        recommendations_enabled=True,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.add(ProfileInterest(user_id=user_id, profile_id=profile.id or 0, interest=interest))
    session.commit()
    return profile


def _record_public_job_provenance(session: Session, job: Job) -> None:
    if job.id is None:
        session.flush()
    job.source_url = job.source_url or f"https://example.com/jobs/{job.content_hash}"
    session.add(job)
    session.add(
        ExtractionMetric(
            user_id=job.user_id,
            workflow_type="job_extraction",
            subject_type="job",
            subject_id=job.id,
            strategy="scoped_html",
            status="succeeded",
        )
    )
    session.commit()


class _StrongScorer:
    def score(self, *_args, **_kwargs):
        return SimpleNamespace(
            score=88.0,
            fit_level="Strong",
            confidence=0.82,
            matched_evidence=["Python backed by CV evidence"],
            missing_blockers=[],
            gaps=["AWS is preferred"],
            projects=["CareerFit"],
            skill_order=["Python", "FastAPI", "SQL"],
            about_text="Backend developer with evidence-backed Python experience.",
            model_version=MODEL_VERSION,
            component_scores={"skills": 91.0},
        )


class _ObservationScorer(_StrongScorer):
    def score(self, *_args, **_kwargs):
        result = super().score()
        result.score = 68.0
        result.fit_level = "Medium"
        return result


class _BelowThresholdScorer(_ObservationScorer):
    def score(self, *_args, **_kwargs):
        result = super().score()
        result.score = 39.0
        result.fit_level = "Weak"
        return result


class _PossibleScorer(_ObservationScorer):
    def score(self, *_args, **_kwargs):
        result = super().score()
        result.score = 40.0
        result.fit_level = "Weak"
        return result


class _RoleAwareScorer(_StrongScorer):
    def score(self, *_args, **_kwargs):
        result = super().score()
        role = str(_args[2])
        if role.startswith("Weak"):
            result.score = 30.0
            result.fit_level = "Weak"
        return result


def test_catalog_rejects_pasted_and_missing_provenance():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        pasted = Job(
            user_id=SCANNER,
            content_hash="pasted-private-job",
            source_url="https://example.com/jobs/private-fallback",
            company="Private Co",
            role="Backend Developer",
            description_text="Confidential recruiter notes. Requirements: Python and SQL.",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        unverified = Job(
            user_id=SCANNER,
            content_hash="unverified-job",
            source_url="https://example.com/jobs/unverified",
            company="Unknown Co",
            role="Backend Developer",
            description_text="Requirements: Python and SQL.",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(pasted)
        session.add(unverified)
        session.commit()
        session.add(
            ExtractionMetric(
                user_id=SCANNER,
                workflow_type="job_extraction",
                subject_type="job",
                subject_id=pasted.id,
                strategy="pasted",
                status="succeeded",
            )
        )
        session.commit()

        assert catalog_and_enqueue_job(session, SCANNER, pasted) is None
        assert catalog_and_enqueue_job(session, SCANNER, unverified) is None
        assert list(session.exec(select(SharedJobCatalog)).all()) == []


def test_later_pasted_rescan_cannot_overwrite_public_catalog():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        job = Job(
            user_id=SCANNER,
            content_hash="public-then-private",
            source_url="https://example.com/jobs/public-then-private",
            company="Public Co",
            role="Backend Developer",
            description_text="Public posting. Requirements: Python and SQL.",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(job)
        session.commit()
        _record_public_job_provenance(session, job)
        catalog = catalog_and_enqueue_job(session, SCANNER, job)
        assert catalog is not None

        job.description_text = "Private recruiter notes that must not be redistributed."
        session.add(job)
        session.add(
            ExtractionMetric(
                user_id=SCANNER,
                workflow_type="job_extraction",
                subject_type="job",
                subject_id=job.id,
                strategy="pasted",
                status="succeeded",
            )
        )
        session.commit()

        assert catalog_and_enqueue_job(session, SCANNER, job) is None
        persisted = session.exec(select(SharedJobCatalog)).one()

    assert persisted.description_text == "Public posting. Requirements: Python and SQL."


def test_job_routing_uses_domain_and_role_hints():
    backend = classify_requirements("Requirements: Python, FastAPI and SQL.", "Backend Developer")
    hardware = classify_requirements("Requirements: Verilog and FPGA.", "FPGA Verification Engineer")

    assert route_job_fields("Backend Developer", backend)[0] == "Software Engineering"
    assert "Hardware Engineering" in route_job_fields("FPGA Verification Engineer", hardware)


def test_explicit_product_role_does_not_inherit_technical_domain_fields():
    requirements = classify_requirements(
        "Own an API security roadmap and work with engineering and cloud teams.",
        "API Security Sr. Product Manager",
    )

    assert route_job_fields(
        "API Security Sr. Product Manager",
        requirements,
        "Product Management",
    ) == ["Product Management"]


def test_shadow_recommendations_prefilter_candidates_and_hide_scanner(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        _profile(session, UNRELATED, "Marketing")
        requirements = classify_requirements(
            "Student position. Requirements: Python, FastAPI and SQL.",
            "Backend Student",
        )
        job = Job(
            user_id=SCANNER,
            content_hash="canonical-job-hash",
            source_url="https://example.com/jobs/42",
            company="Example",
            role="Backend Student",
            description_text="Student position. Requirements: Python, FastAPI and SQL.",
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
            status="analyzed",
        )
        session.add(job)
        session.commit()
        _record_public_job_provenance(session, job)

        catalog = catalog_and_enqueue_job(session, SCANNER, job)
        assert catalog is not None and catalog.id is not None
        run = generate_shadow_recommendations(session, catalog.id, SCANNER)
        recommendations = list(session.exec(select(JobRecommendation)).all())

    assert run.candidate_count == 1
    assert run.scored_count == 1
    assert run.strong_count == 1
    assert [item.user_id for item in recommendations] == [RELEVANT]
    assert str(SCANNER) not in recommendations[0].reasons_json
    assert recommendations[0].status == "available"


def test_candidate_who_already_saved_job_is_not_rescored(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        source_job = Job(
            user_id=SCANNER,
            content_hash="same-job",
            role="Backend Developer",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(source_job)
        session.add(Job(user_id=RELEVANT, content_hash="same-job", role="Backend Developer", status="analyzed"))
        session.commit()
        _record_public_job_provenance(session, source_job)

        catalog = catalog_and_enqueue_job(session, SCANNER, source_job)
        assert catalog is not None and catalog.id is not None
        run = generate_shadow_recommendations(session, catalog.id, SCANNER)

    assert run.candidate_count == 1
    assert run.scored_count == 0
    assert run.strong_count == 0


def test_non_eligible_scores_are_kept_for_shadow_calibration(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _BelowThresholdScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        job = Job(
            user_id=SCANNER,
            content_hash="observation-job",
            role="Backend Developer",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(job)
        session.commit()
        _record_public_job_provenance(session, job)
        catalog = catalog_and_enqueue_job(session, SCANNER, job)
        assert catalog is not None and catalog.id is not None
        run = generate_shadow_recommendations(session, catalog.id, SCANNER)
        recommendation = session.exec(select(JobRecommendation)).one()

    assert run.scored_count == 1
    assert run.strong_count == 0
    assert recommendation.status == "shadow_observation"


def test_candidate_without_discovery_consent_is_never_shortlisted(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        profile = _profile(session, RELEVANT, "Software Engineering")
        profile.recommendations_enabled = False
        session.add(profile)
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        job = Job(
            user_id=SCANNER,
            content_hash="consent-job",
            role="Backend Developer",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(job)
        session.commit()
        _record_public_job_provenance(session, job)
        catalog = catalog_and_enqueue_job(session, SCANNER, job)
        assert catalog is not None and catalog.id is not None
        run = generate_shadow_recommendations(session, catalog.id, SCANNER)

    assert run.candidate_count == 0
    assert run.scored_count == 0


def test_deleted_source_account_does_not_break_recommendation_run(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog_job = Job(
            user_id=SCANNER,
            content_hash="deleted-source-job",
            role="Backend Developer",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add(catalog_job)
        session.commit()
        _record_public_job_provenance(session, catalog_job)
        catalog = catalog_and_enqueue_job(session, SCANNER, catalog_job)
        assert catalog is not None and catalog.id is not None

        run = generate_shadow_recommendations(session, catalog.id, SCANNER)
        persisted = session.exec(select(RecommendationRun)).one()

    assert run.status == "completed"
    assert persisted.source_user_id is None
    assert run.candidate_count == 1


def test_goozali_suggestions_use_discovery_floor_and_explicit_beta_membership(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _ObservationScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        _profile(session, UNRELATED, "Software Engineering")
        session.add(JobDiscoveryBetaMember(user_id=RELEVANT, market_code="IL", active=True))
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog = SharedJobCatalog(
            content_hash="goozali-beta-job",
            source_name="goozali",
            external_id="rec-goozali",
            role="Backend Developer",
            location="Remote",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)

        run = generate_shadow_recommendations(session, catalog.id or 0, None)
        recommendations = list(session.exec(select(JobRecommendation)).all())

    assert run.candidate_count == 1
    assert run.scored_count == 1
    assert recommendations[0].user_id == RELEVANT
    assert recommendations[0].score == 68
    assert recommendations[0].status == "available"


def test_community_suggestions_include_the_40_discovery_floor(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _PossibleScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Intern")
        catalog = SharedJobCatalog(
            content_hash="community-unified-threshold",
            source_name="community",
            role="Backend Intern",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)

        run = generate_shadow_recommendations(session, catalog.id or 0, None)
        recommendation = session.exec(select(JobRecommendation)).one()

    assert run.strong_count == 1
    assert recommendation.score == 40
    assert recommendation.status == "available"


def test_field_calibration_threshold_is_applied_during_scoring(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _PossibleScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        session.add(
            RecommendationFieldCalibration(
                career_field="Software Engineering",
                minimum_score=50,
                sample_size=20,
                positive_count=10,
                negative_count=10,
            )
        )
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Intern")
        catalog = SharedJobCatalog(
            content_hash="field-calibrated-threshold",
            role="Backend Intern",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)

        run = generate_shadow_recommendations(session, catalog.id or 0, None)
        recommendation = session.exec(select(JobRecommendation)).one()

    assert run.scored_count == 1
    assert run.strong_count == 0
    assert recommendation.score == 40
    assert recommendation.status == "shadow_observation"


def test_goozali_primary_field_is_a_hard_user_filter(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        session.add(JobDiscoveryBetaMember(user_id=RELEVANT, market_code="IL", active=True))
        old_requirements = classify_requirements(
            "Work with API security, cloud, data, and engineering teams.",
            "API Security Sr. Product Manager",
        )
        catalog = SharedJobCatalog(
            content_hash="product-manager-field-regression",
            source_name="goozali",
            external_id="product-manager-field-regression",
            role="API Security Sr. Product Manager",
            description_text=(
                "Own internal tools and vendor processes.\n\n"
                "Requirements:\nWork with API security and engineering teams.\n\n"
                "Employment scope: Full Time\nLocation: Israel\nMinimum experience: 5 years"
            ),
            career_fields_json='["Product Management", "Software Engineering"]',
            requirements_json=old_requirements.to_json(),
            source_confidence=0.92,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)

        run = generate_shadow_recommendations(session, catalog.id or 0, None)

    assert run.candidate_count == 0
    assert run.scored_count == 0


def test_goozali_structured_experience_is_a_hard_suggestion_gate(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        session.add(JobDiscoveryBetaMember(user_id=RELEVANT, market_code="IL", active=True))
        old_requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        session.add(
            SharedJobCatalog(
                content_hash="goozali-experience-regression",
                source_name="goozali",
                external_id="goozali-experience-regression",
                role="Backend Developer",
                location="Israel",
                description_text=(
                    "Build production backend services with Python and SQL.\n\n"
                    "Requirements:\nPython and SQL are required.\n\n"
                    "Employment scope: Full Time\nLocation: Israel\nMinimum experience: 4 years"
                ),
                career_fields_json='["Software Engineering"]',
                requirements_json=old_requirements.to_json(),
                source_confidence=0.92,
            )
        )
        session.commit()

        recommendations = refresh_user_recommendations(session, RELEVANT)

    assert recommendations == []


def test_old_model_recommendations_are_not_listed():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog = SharedJobCatalog(
            content_hash="stale-model-job",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)
        session.add(
            JobRecommendation(
                user_id=RELEVANT,
                catalog_job_id=catalog.id or 0,
                model_version="fit-v2.3.0",
                score=92,
                fit_level="Strong",
                confidence=0.9,
                status="available",
                career_fields_json='["Software Engineering"]',
            )
        )
        session.commit()

        recommendations = list_recommendations(session, RELEVANT)

    assert recommendations == []


def test_discovery_refresh_unifies_community_and_goozali_matches(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        session.add(JobDiscoveryBetaMember(user_id=RELEVANT, market_code="IL", active=True))
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        for source_name in ("community", "goozali"):
            session.add(
                SharedJobCatalog(
                    content_hash=f"{source_name}-refresh-job",
                    source_name=source_name,
                    external_id=f"{source_name}-refresh" if source_name == "goozali" else "",
                    company="Example",
                    role=f"{source_name.title()} Backend Developer",
                    career_fields_json='["Software Engineering"]',
                    requirements_json=requirements.to_json(),
                    source_confidence=0.9,
                )
            )
        session.commit()

        recommendations = refresh_user_recommendations(session, RELEVANT)

    assert {item.source_name for item in recommendations} == {"community", "goozali"}


def test_discovery_refresh_pages_past_newer_secondary_field_jobs(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())
    now = datetime(2026, 7, 25, tzinfo=timezone.utc)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Intern")
        session.add(
            SharedJobCatalog(
                content_hash="older-eligible-job",
                company="Relevant",
                role="Backend Intern",
                career_fields_json='["Software Engineering"]',
                requirements_json=requirements.to_json(),
                source_confidence=0.9,
                updated_at=now - timedelta(days=1),
            )
        )
        session.add_all(
            [
                SharedJobCatalog(
                    content_hash=f"newer-irrelevant-job-{index}",
                    company="Irrelevant",
                    role=f"Product Manager {index}",
                    career_fields_json='["Product Management", "Software Engineering"]',
                    requirements_json=requirements.to_json(),
                    source_confidence=0.9,
                    updated_at=now,
                )
                for index in range(260)
            ]
        )
        session.commit()

        recommendations = refresh_user_recommendations(session, RELEVANT)

    assert [item.role for item in recommendations] == ["Backend Intern"]


def test_discovery_refresh_continues_past_weak_scores_to_find_strong_match(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _RoleAwareScorer())
    now = datetime(2026, 7, 25, tzinfo=timezone.utc)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Intern")
        session.add(
            SharedJobCatalog(
                content_hash="older-strong-job",
                company="Relevant",
                role="Backend Intern",
                career_fields_json='["Software Engineering"]',
                requirements_json=requirements.to_json(),
                source_confidence=0.9,
                updated_at=now - timedelta(days=1),
            )
        )
        session.add_all(
            [
                SharedJobCatalog(
                    content_hash=f"newer-weak-job-{index}",
                    company="Irrelevant",
                    role=f"Weak Backend Role {index}",
                    career_fields_json='["Software Engineering"]',
                    requirements_json=requirements.to_json(),
                    source_confidence=0.9,
                    updated_at=now,
                )
                for index in range(40)
            ]
        )
        session.commit()

        recommendations = refresh_user_recommendations(session, RELEVANT)

    assert [item.role for item in recommendations] == ["Backend Intern"]


def test_discovery_refresh_keeps_goozali_limited_to_beta_members(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        session.add(
            SharedJobCatalog(
                content_hash="goozali-non-beta-refresh",
                source_name="goozali",
                external_id="goozali-non-beta-refresh",
                role="Backend Developer",
                career_fields_json='["Software Engineering"]',
                requirements_json=requirements.to_json(),
                source_confidence=0.9,
            )
        )
        session.commit()

        recommendations = refresh_user_recommendations(session, RELEVANT)

    assert recommendations == []


def test_discovery_refresh_does_not_resurface_a_dismissed_role(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        session.add(
            SharedJobCatalog(
                content_hash="dismissed-refresh-job",
                role="Backend Developer",
                career_fields_json='["Software Engineering"]',
                requirements_json=requirements.to_json(),
                source_confidence=0.9,
            )
        )
        session.commit()
        first = refresh_user_recommendations(session, RELEVANT)
        update_recommendation(
            session,
            RELEVANT,
            first[0].id,
            "dismissed",
            dismiss_reason="not_interested",
        )

        second = refresh_user_recommendations(session, RELEVANT)
        persisted = session.exec(select(JobRecommendation)).one()

    assert second == []
    assert persisted.status == "dismissed"


def test_recommendation_events_are_idempotent_and_snapshot_dismiss_reason():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog = SharedJobCatalog(
            content_hash="feedback-event-job",
            source_name="goozali",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=RELEVANT,
            catalog_job_id=catalog.id or 0,
            model_version=MODEL_VERSION,
            score=47,
            fit_level="Weak",
            confidence=0.7,
            status="available",
            career_fields_json='["Software Engineering"]',
        )
        session.add(recommendation)
        session.commit()
        session.refresh(recommendation)

        record_recommendation_view(session, RELEVANT, recommendation.id or 0)
        record_recommendation_view(session, RELEVANT, recommendation.id or 0)
        update_recommendation(
            session,
            RELEVANT,
            recommendation.id or 0,
            "dismissed",
            dismiss_reason="wrong_field",
        )
        events = list(
            session.exec(
                select(RecommendationEvent).order_by(RecommendationEvent.event_type)
            ).all()
        )

    assert [event.event_type for event in events] == ["dismissed", "viewed"]
    dismissed = events[0]
    assert dismissed.dismiss_reason == "wrong_field"
    assert dismissed.score_band == "possible"
    assert dismissed.career_field == "Software Engineering"
    assert dismissed.source_name == "goozali"


def test_applied_job_status_records_recommendation_application_once():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog = SharedJobCatalog(
            content_hash="application-event-job",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        job = Job(
            user_id=RELEVANT,
            content_hash="application-event-job",
            role="Backend Developer",
            requirements_json=requirements.to_json(),
            status="analyzed",
        )
        session.add_all([catalog, job])
        session.commit()
        session.refresh(catalog)
        session.refresh(job)
        match = JobMatch(user_id=RELEVANT, job_id=job.id or 0, status="Lead")
        recommendation = JobRecommendation(
            user_id=RELEVANT,
            catalog_job_id=catalog.id or 0,
            materialized_job_id=job.id,
            model_version=MODEL_VERSION,
            score=72,
            fit_level="Medium",
            confidence=0.8,
            status="saved",
            career_fields_json='["Software Engineering"]',
        )
        session.add_all([match, recommendation])
        session.commit()

        update_job_status(session, RELEVANT, job.id or 0, "Applied")
        update_job_status(session, RELEVANT, job.id or 0, "Applied")
        events = list(
            session.exec(
                select(RecommendationEvent).where(
                    RecommendationEvent.event_type == "applied"
                )
            ).all()
        )

    assert len(events) == 1
    assert events[0].materialized_job_id == job.id
    assert events[0].score_band == "medium"


def test_field_calibration_raises_only_the_noisy_field_threshold():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Product Management")
        for index in range(20):
            catalog = SharedJobCatalog(
                content_hash=f"calibration-job-{index}",
                role=f"Product role {index}",
                career_fields_json='["Product Management"]',
            )
            session.add(catalog)
            session.flush()
            possible = index < 8
            recommendation = JobRecommendation(
                user_id=RELEVANT,
                catalog_job_id=catalog.id or 0,
                model_version=f"{MODEL_VERSION}-calibration-{index}",
                score=45 if possible else 82,
                fit_level="Weak" if possible else "Strong",
                confidence=0.8,
                status="dismissed" if possible else "saved",
                career_fields_json='["Product Management"]',
            )
            session.add(recommendation)
            session.flush()
            session.add(
                RecommendationEvent(
                    user_id=RELEVANT,
                    recommendation_id=recommendation.id or 0,
                    catalog_job_id=catalog.id or 0,
                    event_type="dismissed" if possible else "saved",
                    dismiss_reason="wrong_field" if possible else "",
                    score=recommendation.score,
                    score_band="possible" if possible else "strong",
                    career_field="Product Management",
                    model_version=recommendation.model_version,
                )
            )
        session.commit()

        calibration = refresh_field_calibration(session, "Product Management")
        session.commit()
        session.refresh(calibration)
        untouched = session.get(RecommendationFieldCalibration, "Software Engineering")
        calibration_values = (
            calibration.minimum_score,
            calibration.sample_size,
            calibration.possible_sample_size,
            calibration.possible_positive_count,
        )

    assert calibration_values == (50, 20, 8, 0)
    assert untouched is None


def test_failed_recommendation_run_rolls_back_before_recording_failure(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog = SharedJobCatalog(
            content_hash="rollback-before-failure-record",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)

        operations: list[str] = []
        original_commit = session.commit
        original_rollback = session.rollback

        def tracked_commit():
            operations.append("commit")
            return original_commit()

        def tracked_rollback():
            operations.append("rollback")
            return original_rollback()

        monkeypatch.setattr(session, "commit", tracked_commit)
        monkeypatch.setattr(session, "rollback", tracked_rollback)
        monkeypatch.setattr(
            recommendation_service,
            "_score_catalog_for_profile",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("score failed")),
        )

        with pytest.raises(RuntimeError, match="score failed"):
            generate_shadow_recommendations(session, catalog.id or 0, None)

        session.expire_all()
        persisted = session.exec(select(RecommendationRun)).one()

    assert operations == ["commit", "rollback", "commit"]
    assert persisted.status == "failed"
    assert persisted.error == "score failed"
    assert persisted.completed_at is not None


def test_competing_terminal_action_cannot_overwrite_committed_dismissal():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")

    with Session(engine) as setup:
        catalog = SharedJobCatalog(
            content_hash="terminal-action-race",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        setup.add(catalog)
        setup.commit()
        setup.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=RELEVANT,
            catalog_job_id=catalog.id or 0,
            model_version=MODEL_VERSION,
            score=80,
            fit_level="Strong",
            confidence=0.8,
            status="available",
            career_fields_json='["Software Engineering"]',
        )
        setup.add(recommendation)
        setup.commit()
        recommendation_id = recommendation.id or 0

    with Session(engine, expire_on_commit=False) as stale_session:
        assert stale_session.get(JobRecommendation, recommendation_id).status == "available"
        stale_session.commit()
        with Session(engine) as winning_session:
            update_recommendation(
                winning_session,
                RELEVANT,
                recommendation_id,
                "dismissed",
                dismiss_reason="wrong_field",
            )

        with pytest.raises(ValueError, match="already handled"):
            update_recommendation(
                stale_session,
                RELEVANT,
                recommendation_id,
                "saved",
            )

    with Session(engine) as verification:
        persisted = verification.get(JobRecommendation, recommendation_id)
        events = list(verification.exec(select(RecommendationEvent)).all())
        jobs = list(verification.exec(select(Job).where(Job.user_id == RELEVANT)).all())

    assert persisted is not None and persisted.status == "dismissed"
    assert [item.event_type for item in events] == ["dismissed"]
    assert jobs == []


def test_failed_save_rolls_back_action_and_materialized_job(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog = SharedJobCatalog(
            content_hash="failed-save-rolls-back",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=RELEVANT,
            catalog_job_id=catalog.id or 0,
            model_version=MODEL_VERSION,
            score=80,
            fit_level="Strong",
            confidence=0.8,
            status="available",
            career_fields_json='["Software Engineering"]',
        )
        session.add(recommendation)
        session.commit()
        recommendation_id = recommendation.id or 0

        monkeypatch.setattr(
            "app.services.jobs.save_match",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("match failed")),
        )
        with pytest.raises(RuntimeError, match="match failed"):
            update_recommendation(session, RELEVANT, recommendation_id, "saved")

        session.expire_all()
        persisted = session.get(JobRecommendation, recommendation_id)
        jobs = list(session.exec(select(Job).where(Job.user_id == RELEVANT)).all())
        events = list(session.exec(select(RecommendationEvent)).all())

    assert persisted is not None and persisted.status == "available"
    assert persisted.materialized_job_id is None
    assert jobs == []
    assert events == []


def test_save_transition_materializes_job_match_and_feedback_atomically():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog = SharedJobCatalog(
            content_hash="successful-atomic-save",
            company="Example",
            role="Backend Developer",
            description_text="Requirements: Python and SQL.",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=RELEVANT,
            catalog_job_id=catalog.id or 0,
            model_version=MODEL_VERSION,
            score=80,
            fit_level="Strong",
            confidence=0.8,
            status="available",
            career_fields_json='["Software Engineering"]',
        )
        session.add(recommendation)
        session.commit()

        result, job = update_recommendation(
            session,
            RELEVANT,
            recommendation.id or 0,
            "saved",
        )
        session.expire_all()
        persisted = session.get(JobRecommendation, recommendation.id or 0)
        matches = list(session.exec(select(JobMatch)).all())
        events = list(session.exec(select(RecommendationEvent)).all())

    assert result.status == "saved"
    assert job is not None and job.role == "Backend Developer"
    assert persisted is not None and persisted.materialized_job_id == job.id
    assert len(matches) == 1 and matches[0].job_id == job.id
    assert [item.event_type for item in events] == ["saved"]


def test_scoring_recovers_from_a_stale_unique_insert_view():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        profile = _profile(session, RELEVANT, "Software Engineering")
        requirements = classify_requirements("Requirements: Python and SQL.", "Backend Developer")
        catalog = SharedJobCatalog(
            content_hash="unique-recommendation-race",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
            requirements_json=requirements.to_json(),
            source_confidence=0.9,
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)
        session.add(
            JobRecommendation(
                user_id=RELEVANT,
                catalog_job_id=catalog.id or 0,
                model_version=MODEL_VERSION,
                score=1,
                fit_level="Weak",
                confidence=0.1,
                status="available",
                career_fields_json='["Software Engineering"]',
            )
        )
        session.commit()

        scored, available = recommendation_service._score_catalog_for_profile(
            session,
            catalog,
            profile,
            recommendation_service.candidate_snapshot(session, profile),
            requirements,
            ["Software Engineering"],
            _StrongScorer(),
            queue_email=False,
            minimum_score=40,
            already_saved=False,
            # Simulate a bulk-read snapshot taken just before another worker's
            # unique insert committed.
            recommendations_by_key={},
        )
        session.commit()
        persisted = list(session.exec(select(JobRecommendation)).all())

    assert scored is True
    assert available is True
    assert len(persisted) == 1
    assert persisted[0].score == 88
    assert persisted[0].status == "available"


def test_generation_bulk_loads_existing_jobs_and_recommendations_once(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _StrongScorer())

    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with Session(engine) as session:
            users = [
                UUID("10000000-0000-0000-0000-000000000001"),
                UUID("50000000-0000-0000-0000-000000000002"),
                UUID("90000000-0000-0000-0000-000000000003"),
            ]
            for user_id in users:
                _profile(session, user_id, "Software Engineering")
            requirements = classify_requirements(
                "Requirements: Python and SQL.",
                "Backend Developer",
            )
            catalog = SharedJobCatalog(
                content_hash="bulk-candidate-state",
                role="Backend Developer",
                career_fields_json='["Software Engineering"]',
                requirements_json=requirements.to_json(),
                source_confidence=0.9,
            )
            session.add(catalog)
            session.add(
                Job(
                    user_id=users[0],
                    content_hash="bulk-candidate-state",
                    role="Backend Developer",
                    requirements_json=requirements.to_json(),
                    status="analyzed",
                )
            )
            session.commit()
            session.refresh(catalog)
            statements.clear()

            run = generate_shadow_recommendations(session, catalog.id or 0, None)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    existing_job_reads = [
        statement
        for statement in statements
        if statement.lstrip().startswith("select")
        and " from jobs " in statement.replace("\n", " ")
        and "content_hash" in statement
    ]
    recommendation_reads = [
        statement
        for statement in statements
        if statement.lstrip().startswith("select")
        and " from job_recommendations " in statement.replace("\n", " ")
    ]
    assert run.candidate_count == 3
    assert run.scored_count == 2
    assert len(existing_job_reads) == 1
    assert len(recommendation_reads) == 1


def test_candidate_limit_uses_a_stable_per_job_rotation(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(recommendation_service, "MAX_CANDIDATES_PER_JOB", 2)
    user_ids = [
        UUID("10000000-0000-0000-0000-000000000000"),
        UUID("50000000-0000-0000-0000-000000000000"),
        UUID("90000000-0000-0000-0000-000000000000"),
        UUID("d0000000-0000-0000-0000-000000000000"),
    ]

    def expected_for(catalog: SharedJobCatalog) -> list[UUID]:
        digest = hashlib.sha256(
            f"{catalog.id or 0}:{catalog.content_hash}".encode("utf-8")
        ).digest()
        pivot = UUID(bytes=digest[:16])
        circular = sorted(value for value in user_ids if value >= pivot)
        circular.extend(sorted(value for value in user_ids if value < pivot))
        return circular[:2]

    with Session(engine) as session:
        for user_id in user_ids:
            session.add(Profile(user_id=user_id))
        session.commit()
        first_catalog = SharedJobCatalog(id=101, content_hash="rotation-first")
        first_expected = expected_for(first_catalog)
        first = recommendation_service._rotated_candidate_profiles(
            session,
            select(Profile),
            first_catalog,
        )
        for index in range(100):
            second_catalog = SharedJobCatalog(
                id=202,
                content_hash=f"rotation-second-{index}",
            )
            second_expected = expected_for(second_catalog)
            if second_expected != first_expected:
                break
        second = recommendation_service._rotated_candidate_profiles(
            session,
            select(Profile),
            second_catalog,
        )

    assert [profile.user_id for profile in first] == first_expected
    assert [profile.user_id for profile in second] == second_expected
    assert first_expected != second_expected


class _QueueResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _QueueSession:
    def __init__(self, row):
        self.row = row
        self.statements: list[str] = []
        self.commits = 0
        self.rollbacks = 0

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def exec(self, statement):
        rendered = str(statement)
        self.statements.append(rendered)
        if "pgmq.read" in rendered:
            return _QueueResult(self.row)
        return _QueueResult(None)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_malformed_queue_message_is_archived_without_entering_scoring():
    session = _QueueSession((17, 1, "{not-json"))

    assert process_one_queued_recommendation(session) is None

    assert sum("pgmq.archive" in statement for statement in session.statements) == 1
    assert session.commits == 1
    assert session.rollbacks == 0


def test_successful_queue_message_commits_lease_then_archives(monkeypatch):
    session = _QueueSession(
        (
            19,
            1,
            {"catalog_job_id": 7, "source_user_id": str(SCANNER)},
        )
    )
    run = RecommendationRun(id=23, catalog_job_id=7, status="completed")
    monkeypatch.setattr(
        recommendation_service,
        "generate_shadow_recommendations",
        lambda *_args, **_kwargs: run,
    )

    assert process_one_queued_recommendation(session) is run

    assert sum("pgmq.archive" in statement for statement in session.statements) == 1
    assert session.commits == 2
    assert session.rollbacks == 0


@pytest.mark.parametrize(
    ("read_count", "expected_archives", "expected_commits"),
    [(1, 0, 1), (3, 1, 2)],
)
def test_failed_queue_message_retries_then_archives_at_attempt_ceiling(
    monkeypatch,
    read_count,
    expected_archives,
    expected_commits,
):
    session = _QueueSession(
        (
            18,
            read_count,
            {"catalog_job_id": 7, "source_user_id": str(SCANNER)},
        )
    )
    monkeypatch.setattr(
        recommendation_service,
        "generate_shadow_recommendations",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("worker failed")),
    )

    assert process_one_queued_recommendation(session) is None

    assert sum("pgmq.archive" in statement for statement in session.statements) == expected_archives
    assert session.commits == expected_commits
    assert session.rollbacks == 1


def test_logistics_dismissals_do_not_become_global_negative_labels():
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        catalog = SharedJobCatalog(
            content_hash="reason-aware-calibration",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)
        for index, reason in enumerate(("wrong_field", "wrong_location")):
            recommendation = JobRecommendation(
                user_id=RELEVANT,
                catalog_job_id=catalog.id or 0,
                model_version=f"{MODEL_VERSION}-reason-{index}",
                score=45,
                fit_level="Weak",
                confidence=0.7,
                status="dismissed",
                career_fields_json='["Software Engineering"]',
            )
            session.add(recommendation)
            session.flush()
            session.add(
                RecommendationEvent(
                    user_id=RELEVANT,
                    recommendation_id=recommendation.id or 0,
                    catalog_job_id=catalog.id or 0,
                    event_type="dismissed",
                    dismiss_reason=reason,
                    score=45,
                    score_band="possible",
                    career_field="Software Engineering",
                    model_version=recommendation.model_version,
                )
            )
        session.commit()

        calibration = refresh_field_calibration(session, "Software Engineering")
        session.commit()
        session.refresh(calibration)

    assert calibration.sample_size == 1
    assert calibration.negative_count == 1
    assert calibration.possible_sample_size == 1


def test_user_action_defers_global_calibration_refresh(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        catalog = SharedJobCatalog(
            content_hash="deferred-calibration",
            role="Backend Developer",
            career_fields_json='["Software Engineering"]',
        )
        session.add(catalog)
        session.commit()
        session.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=RELEVANT,
            catalog_job_id=catalog.id or 0,
            model_version=MODEL_VERSION,
            score=45,
            fit_level="Weak",
            confidence=0.7,
            status="available",
            career_fields_json='["Software Engineering"]',
        )
        session.add(recommendation)
        session.commit()
        recommendation_id = recommendation.id or 0
        monkeypatch.setattr(
            recommendation_service,
            "refresh_field_calibration",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("calibration must be deferred")
            ),
        )

        result, _job = update_recommendation(
            session,
            RELEVANT,
            recommendation_id,
            "dismissed",
            dismiss_reason="wrong_field",
        )

    assert result.status == "dismissed"
