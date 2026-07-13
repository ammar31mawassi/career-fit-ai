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
from ..schemas import JobOut, JobRecommendationOut
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
    session.flush()
    if should_enqueue:
        _enqueue_if_supported(session, catalog.id or 0, source_user_id)
    session.commit()
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
                Profile.recommendations_enabled.is_(True),
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
            snapshot = candidate_snapshot(session, profile)
            if not _cheap_eligible(snapshot, requirements, catalog.location):
                continue
            result = get_match_scorer().score(
                snapshot,
                catalog.company,
                catalog.role,
                requirements,
                catalog.source_confidence,
            )
            run.scored_count += 1
            is_strong = (
                result.fit_level == "Strong"
                and result.score >= SHADOW_SCORE_THRESHOLD
                and result.confidence >= SHADOW_CONFIDENCE_THRESHOLD
                and not result.missing_blockers
            )
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
            recommendation.status = "available" if is_strong else "shadow_observation"
            recommendation.updated_at = _now()
            session.add(recommendation)
            if is_strong:
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


def list_recommendations(session: Session, user_id: UUID, limit: int = 12) -> list[JobRecommendationOut]:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile is None or not profile.recommendations_enabled:
        return []
    recommendations = list(
        session.exec(
            select(JobRecommendation)
            .where(
                JobRecommendation.user_id == user_id,
                JobRecommendation.status.in_(["available", "shadow_eligible"]),
            )
            .order_by(JobRecommendation.score.desc(), JobRecommendation.updated_at.desc())
            .limit(limit)
        ).all()
    )
    if not recommendations:
        return []
    catalogs = {
        item.id: item
        for item in session.exec(
            select(SharedJobCatalog).where(
                SharedJobCatalog.id.in_([item.catalog_job_id for item in recommendations]),
                SharedJobCatalog.active.is_(True),
            )
        ).all()
    }
    return [
        _recommendation_out(item, catalogs[item.catalog_job_id])
        for item in recommendations
        if item.catalog_job_id in catalogs
    ]


def update_recommendation(
    session: Session,
    user_id: UUID,
    recommendation_id: int,
    status: str,
) -> tuple[JobRecommendationOut, JobOut | None]:
    # Imported lazily because jobs catalogues completed scans into this module.
    from .jobs import job_output, save_match

    recommendation = session.get(JobRecommendation, recommendation_id)
    if recommendation is None or recommendation.user_id != user_id:
        raise ValueError("Recommendation not found.")
    catalog = session.get(SharedJobCatalog, recommendation.catalog_job_id)
    if catalog is None or not catalog.active:
        raise ValueError("Recommended job is no longer available.")
    if status == "dismissed":
        recommendation.status = "dismissed"
        recommendation.updated_at = _now()
        session.add(recommendation)
        session.commit()
        return _recommendation_out(recommendation, catalog), None
    if status != "saved":
        raise ValueError("Unsupported recommendation action.")
    job = session.exec(
        select(Job).where(Job.user_id == user_id, Job.content_hash == catalog.content_hash)
    ).first()
    if job is None:
        job = Job(user_id=user_id, content_hash=catalog.content_hash)
    job.source_url = catalog.source_url
    job.application_link = catalog.application_link
    job.company = catalog.company
    job.role = catalog.role
    job.location = catalog.location
    job.description_text = catalog.description_text
    job.source_title = catalog.role
    job.source_confidence = catalog.source_confidence
    job.requirements_json = catalog.requirements_json
    job.status = "analyzed"
    job.error = ""
    job.updated_at = _now()
    session.add(job)
    session.flush()
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).one()
    save_match(session, user_id, profile, job, commit=False)
    recommendation.status = "saved"
    recommendation.updated_at = _now()
    session.add(recommendation)
    session.commit()
    return _recommendation_out(recommendation, catalog), job_output(session, user_id, job.id or 0)


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
    session.flush()


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _json_dict(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _recommendation_out(
    recommendation: JobRecommendation,
    catalog: SharedJobCatalog,
) -> JobRecommendationOut:
    return JobRecommendationOut(
        id=recommendation.id or 0,
        catalog_job_id=catalog.id or 0,
        source_url=catalog.source_url,
        application_link=catalog.application_link,
        company=catalog.company,
        role=catalog.role,
        location=catalog.location,
        score=recommendation.score,
        fit_level=recommendation.fit_level,  # type: ignore[arg-type]
        confidence=recommendation.confidence,
        career_fields=_json_list(recommendation.career_fields_json),
        reasons=_json_list(recommendation.reasons_json),
        status=recommendation.status,
        created_at=recommendation.created_at,
    )


def _cheap_eligible(snapshot, requirements, job_location: str) -> bool:
    if requirements.seniority == "senior" and snapshot.years_experience < 3:
        return False
    if requirements.min_years_experience >= 3 and snapshot.years_experience == 0:
        return False
    if "part-time" in snapshot.availability.lower() and "full-time" in requirements.availability.lower():
        return False
    if "remote" in requirements.work_mode.lower() or "remote" in job_location.lower():
        return True
    candidate_tokens = _location_tokens(snapshot.location)
    job_tokens = _location_tokens(requirements.location_requirement or job_location)
    return not candidate_tokens or not job_tokens or bool(candidate_tokens & job_tokens)


def _location_tokens(value: str) -> set[str]:
    ignored = {"israel", "hybrid", "onsite", "on-site", "remote", "office"}
    return {
        token
        for token in "".join(character if character.isalnum() else " " for character in value.lower()).split()
        if len(token) > 2 and token not in ignored
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)
