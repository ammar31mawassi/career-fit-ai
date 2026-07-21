from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Job,
    JobDiscoveryBetaMember,
    JobRecommendation,
    Profile,
    ProfileInterest,
    RecommendationRun,
    SharedJobCatalog,
)
from app.services.job_research import classify_requirements
from app.services.job_routing import route_job_fields
from app.services.recommendations import catalog_and_enqueue_job, generate_shadow_recommendations


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
            model_version="fit-test-v1",
            component_scores={"skills": 91.0},
        )


class _ObservationScorer(_StrongScorer):
    def score(self, *_args, **_kwargs):
        result = super().score()
        result.score = 68.0
        result.fit_level = "Medium"
        return result


def test_job_routing_uses_domain_and_role_hints():
    backend = classify_requirements("Requirements: Python, FastAPI and SQL.", "Backend Developer")
    hardware = classify_requirements("Requirements: Verilog and FPGA.", "FPGA Verification Engineer")

    assert route_job_fields("Backend Developer", backend)[0] == "Software Engineering"
    assert "Hardware Engineering" in route_job_fields("FPGA Verification Engineer", hardware)


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

        catalog = catalog_and_enqueue_job(session, SCANNER, source_job)
        assert catalog is not None and catalog.id is not None
        run = generate_shadow_recommendations(session, catalog.id, SCANNER)

    assert run.candidate_count == 1
    assert run.scored_count == 0
    assert run.strong_count == 0


def test_non_eligible_scores_are_kept_for_shadow_calibration(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.recommendations.get_match_scorer", lambda: _ObservationScorer())

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
        catalog = catalog_and_enqueue_job(session, SCANNER, catalog_job)
        assert catalog is not None and catalog.id is not None

        run = generate_shadow_recommendations(session, catalog.id, SCANNER)
        persisted = session.exec(select(RecommendationRun)).one()

    assert run.status == "completed"
    assert persisted.source_user_id is None
    assert run.candidate_count == 1


def test_goozali_suggestions_use_65_floor_and_explicit_beta_membership(monkeypatch):
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
