from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session, select

from ..models import (
    Job,
    JobRecommendation,
    Profile,
    ProfileInterest,
    RecommendationRun,
    SharedJobCatalog,
)
from .job_research import requirements_from_json
from .job_routing import route_job_fields
from .profile import candidate_snapshot
from .scoring import get_match_scorer


QUEUE_NAME = "careerfit_job_recommendations"
MAX_CANDIDATES_PER_JOB = 250
SHADOW_SCORE_THRESHOLD = 76.0
SHADOW_CONFIDENCE_THRESHOLD = 0.55


def catalog_and_enqueue_job(session: Session, source_user_id: UUID, job: Job) -> SharedJobCatalog | None:
    if job.status != "analyzed":
        return None
    requirements = requirements_from_json(job.requirements_json)
    fields = route_job_fields(job.role, requirements)
    catalog = session.exec(
        select(SharedJobCatalog).where(SharedJobCatalog.content_hash == job.content_hash)
    ).first()
    should_enqueue = catalog is None
    if catalog is None:
        catalog = SharedJobCatalog(content_hash=job.content_hash, first_seen_by=source_user_id)
    else:
        should_enqueue = any(
            (
                catalog.requirements_json != job.requirements_json,
                catalog.description_text != job.description_text,
                catalog.role != job.role,
            )
        )
    catalog.source_url = job.source_url
    catalog.application_link = job.application_link
    catalog.company = job.company
    catalog.role = job.role
    catalog.location = job.location
    catalog.description_text = job.description_text
    catalog.requirements_json = job.requirements_json
    catalog.domain = requirements.domain
    catalog.career_fields_json = json.dumps(fields)
    catalog.source_confidence = job.source_confidence
    catalog.active = True
    catalog.updated_at = _now()
    session.add(catalog)
    session.commit()
    session.refresh(catalog)
    if should_enqueue:
        _enqueue_if_supported(session, catalog.id or 0, source_user_id)
    return catalog


def generate_shadow_recommendations(
    session: Session,
    catalog_job_id: int,
    source_user_id: UUID,
) -> RecommendationRun:
    catalog = session.get(SharedJobCatalog, catalog_job_id)
    if catalog is None or not catalog.active:
        raise ValueError("Catalog job not found.")
    fields = _json_list(catalog.career_fields_json)
    run = RecommendationRun(catalog_job_id=catalog_job_id, source_user_id=source_user_id)
    session.add(run)
    session.commit()
    session.refresh(run)
    try:
        statement = (
            select(Profile)
            .join(ProfileInterest, ProfileInterest.profile_id == Profile.id)
            .where(
                Profile.status == "ready",
                Profile.onboarding_completed.is_(True),
                Profile.user_id != source_user_id,
                ProfileInterest.interest.in_(fields or ["__none__"]),
            )
            .distinct()
            .limit(MAX_CANDIDATES_PER_JOB)
        )
        profiles = list(session.exec(statement).all())
        run.candidate_count = len(profiles)
        requirements = requirements_from_json(catalog.requirements_json)
        for profile in profiles:
            already_saved = session.exec(
                select(Job.id).where(Job.user_id == profile.user_id, Job.content_hash == catalog.content_hash)
            ).first()
            if already_saved:
                continue
            result = get_match_scorer().score(
                candidate_snapshot(session, profile),
                catalog.company,
                catalog.role,
                requirements,
                catalog.source_confidence,
            )
            run.scored_count += 1
            if (
                result.fit_level != "Strong"
                or result.score < SHADOW_SCORE_THRESHOLD
                or result.confidence < SHADOW_CONFIDENCE_THRESHOLD
                or result.missing_blockers
            ):
                continue
            recommendation = session.exec(
                select(JobRecommendation).where(
                    JobRecommendation.user_id == profile.user_id,
                    JobRecommendation.catalog_job_id == catalog_job_id,
                    JobRecommendation.model_version == result.model_version,
                )
            ).first()
            if recommendation is None:
                recommendation = JobRecommendation(
                    user_id=profile.user_id,
                    catalog_job_id=catalog_job_id,
                    model_version=result.model_version,
                )
            recommendation.score = result.score
            recommendation.fit_level = result.fit_level
            recommendation.confidence = result.confidence
            recommendation.career_fields_json = json.dumps(fields)
            recommendation.reasons_json = json.dumps(result.matched_evidence[:4])
            recommendation.match_snapshot_json = json.dumps(
                {
                    "matched_evidence": result.matched_evidence,
                    "gaps": result.gaps,
                    "component_scores": result.component_scores,
                    "projects": result.projects,
                    "skill_order": result.skill_order,
                    "about_text": result.about_text,
                },
                sort_keys=True,
            )
            recommendation.status = "shadow"
            recommendation.updated_at = _now()
            session.add(recommendation)
            run.strong_count += 1
        run.status = "completed"
        run.completed_at = _now()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)[:500]
        run.completed_at = _now()
        session.add(run)
        session.commit()
        raise


def process_one_queued_recommendation(session: Session) -> RecommendationRun | None:
    if session.get_bind().dialect.name != "postgresql":
        return None
    row = session.exec(
        text("select msg_id, message from pgmq.read(:queue_name, 180, 1)").bindparams(
            queue_name=QUEUE_NAME
        )
    ).first()
    if row is None:
        return None
    message = row[1] if isinstance(row[1], dict) else json.loads(str(row[1]))
    run = generate_shadow_recommendations(
        session,
        int(message["catalog_job_id"]),
        UUID(str(message["source_user_id"])),
    )
    session.exec(
        text("select pgmq.archive(:queue_name, :msg_id)").bindparams(
            queue_name=QUEUE_NAME,
            msg_id=int(row[0]),
        )
    )
    session.commit()
    return run


def _enqueue_if_supported(session: Session, catalog_job_id: int, source_user_id: UUID) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    payload = json.dumps({"catalog_job_id": catalog_job_id, "source_user_id": str(source_user_id)})
    session.exec(
        text("select * from pgmq.send(:queue_name, cast(:payload as jsonb))").bindparams(
            queue_name=QUEUE_NAME,
            payload=payload,
        )
    )
    session.commit()


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _now() -> datetime:
    return datetime.now(timezone.utc)
