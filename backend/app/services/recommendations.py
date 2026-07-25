from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, text
from sqlmodel import Session, select

from ..models import (
    Job,
    JobDiscoveryBetaMember,
    JobRecommendation,
    Profile,
    ProfileInterest,
    RecommendationRun,
    SharedJobCatalog,
)
from ..schemas import JobOut, JobRecommendationOut
from .goozali_reader import GOOZALI_READER_VERSION, classify_goozali_text
from .job_research import JobRequirements, requirements_from_json
from .job_routing import route_job_fields
from .matcher import MODEL_VERSION
from .profile import candidate_snapshot
from .scoring import get_match_scorer


QUEUE_NAME = "careerfit_job_recommendations"
MAX_CANDIDATES_PER_JOB = 250
MAX_DISCOVERY_BACKFILL_JOBS = 40
MAX_DISCOVERY_SCORE_BUDGET = 250
DISCOVERY_CATALOG_BATCH_SIZE = 250
SHADOW_SCORE_THRESHOLD = 76.0
SHADOW_CONFIDENCE_THRESHOLD = 0.55
DISCOVERY_SUGGESTION_THRESHOLD = 65.0
DISCOVERY_SUGGESTION_CONFIDENCE = 0.45


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
        enqueue_catalog_job(session, catalog.id or 0, source_user_id)
    session.commit()
    return catalog


def generate_shadow_recommendations(
    session: Session,
    catalog_job_id: int,
    source_user_id: UUID | None,
) -> RecommendationRun:
    catalog = session.get(SharedJobCatalog, catalog_job_id)
    if catalog is None or not catalog.active:
        raise ValueError("Catalog job not found.")
    requirements = _catalog_requirements(catalog)
    fields = _catalog_fields(catalog, requirements)
    # Queue messages may outlive the account that originally scanned a shared job.
    # Do not let that stale audit reference block recommendations for other users.
    source_profile = session.exec(
        select(Profile.id).where(Profile.user_id == source_user_id)
    ).first() if source_user_id is not None else None
    active_source_user_id = source_user_id if source_profile is not None else None
    run = RecommendationRun(catalog_job_id=catalog_job_id, source_user_id=active_source_user_id)
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
                ProfileInterest.interest.in_(fields[:1] or ["__none__"]),
            )
            .distinct()
            .limit(MAX_CANDIDATES_PER_JOB)
        )
        if catalog.source_name == "goozali":
            statement = statement.join(
                JobDiscoveryBetaMember,
                JobDiscoveryBetaMember.user_id == Profile.user_id,
            ).where(
                JobDiscoveryBetaMember.market_code == "IL",
                JobDiscoveryBetaMember.active.is_(True),
            )
        if active_source_user_id is not None:
            statement = statement.where(Profile.user_id != active_source_user_id)
        profiles = list(session.exec(statement).all())
        run.candidate_count = len(profiles)
        scorer = get_match_scorer()
        for profile in profiles:
            snapshot = candidate_snapshot(session, profile)
            scored, is_strong = _score_catalog_for_profile(
                session,
                catalog,
                profile,
                snapshot,
                requirements,
                fields,
                scorer,
            )
            run.scored_count += int(scored)
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
        UUID(str(message["source_user_id"])) if message.get("source_user_id") else None,
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
    if limit <= 0:
        return []
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile is None or not profile.recommendations_enabled:
        return []
    recommendations = list(
        session.exec(
            select(JobRecommendation)
            .where(
                JobRecommendation.user_id == user_id,
                JobRecommendation.status.in_(["available", "shadow_eligible"]),
                JobRecommendation.model_version.like(f"{MODEL_VERSION}%"),
            )
            .order_by(JobRecommendation.score.desc(), JobRecommendation.updated_at.desc())
            .limit(max(limit, 1) * 4)
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
    interests = {
        value
        for value in session.exec(
            select(ProfileInterest.interest).where(ProfileInterest.profile_id == profile.id)
        ).all()
    }
    snapshot = candidate_snapshot(session, profile)
    output: list[JobRecommendationOut] = []
    for item in recommendations:
        catalog = catalogs.get(item.catalog_job_id)
        if catalog is None:
            continue
        requirements = _catalog_requirements(catalog)
        fields = _catalog_fields(catalog, requirements)
        if not _career_field_eligible(interests, fields):
            continue
        if not _cheap_eligible(snapshot, requirements, catalog.location):
            continue
        output.append(_recommendation_out(item, catalog, fields))
        if len(output) >= limit:
            break
    return output


def refresh_user_recommendations(
    session: Session,
    user_id: UUID,
    limit: int = MAX_DISCOVERY_BACKFILL_JOBS,
) -> list[JobRecommendationOut]:
    """Score eligible catalog jobs for a user who enabled or updated discovery."""
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if (
        profile is None
        or profile.status != "ready"
        or not profile.onboarding_completed
        or not profile.recommendations_enabled
    ):
        return []
    interests = {
        value
        for value in session.exec(
            select(ProfileInterest.interest).where(ProfileInterest.profile_id == profile.id)
        ).all()
    }
    if not interests:
        return []
    beta_member = session.exec(
        select(JobDiscoveryBetaMember.user_id).where(
            JobDiscoveryBetaMember.user_id == user_id,
            JobDiscoveryBetaMember.market_code == "IL",
            JobDiscoveryBetaMember.active.is_(True),
        )
    ).first() is not None
    snapshot = candidate_snapshot(session, profile)
    scorer = get_match_scorer()
    recommendation_target = max(1, min(limit, MAX_DISCOVERY_BACKFILL_JOBS))
    scored = 0
    available = 0
    for catalog in _candidate_catalogs(session, interests, beta_member):
        requirements = _catalog_requirements(catalog)
        fields = _catalog_fields(catalog, requirements)
        if not _career_field_eligible(interests, fields):
            continue
        if catalog.first_seen_by == user_id:
            continue
        was_scored, is_available = _score_catalog_for_profile(
            session,
            catalog,
            profile,
            snapshot,
            requirements,
            fields,
            scorer,
            queue_email=False,
        )
        scored += int(was_scored)
        available += int(is_available)
        if available >= recommendation_target or scored >= MAX_DISCOVERY_SCORE_BUDGET:
            break
    session.commit()
    return list_recommendations(session, user_id, limit=30)


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
    job.requirements_json = _catalog_requirements(catalog).to_json()
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


def enqueue_catalog_job(
    session: Session,
    catalog_job_id: int,
    source_user_id: UUID | None,
) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    payload = json.dumps(
        {
            "catalog_job_id": catalog_job_id,
            "source_user_id": str(source_user_id) if source_user_id else None,
        }
    )
    session.exec(
        text("select * from pgmq.send(:queue_name, cast(:payload as jsonb))").bindparams(
            queue_name=QUEUE_NAME,
            payload=payload,
        )
    )
    session.flush()


def _score_catalog_for_profile(
    session: Session,
    catalog: SharedJobCatalog,
    profile: Profile,
    snapshot,
    requirements,
    fields: list[str],
    scorer,
    *,
    queue_email: bool = True,
) -> tuple[bool, bool]:
    already_saved = session.exec(
        select(Job.id).where(
            Job.user_id == profile.user_id,
            Job.content_hash == catalog.content_hash,
        )
    ).first()
    if already_saved or not _cheap_eligible(snapshot, requirements, catalog.location):
        return False, False
    result = scorer.score(
        snapshot,
        catalog.company,
        catalog.role,
        requirements,
        catalog.source_confidence,
    )
    is_available = _is_available_recommendation(result)
    recommendation = session.exec(
        select(JobRecommendation).where(
            JobRecommendation.user_id == profile.user_id,
            JobRecommendation.catalog_job_id == (catalog.id or 0),
            JobRecommendation.model_version == result.model_version,
        )
    ).first()
    if recommendation is None:
        recommendation = JobRecommendation(
            user_id=profile.user_id,
            catalog_job_id=catalog.id or 0,
            model_version=result.model_version,
        )
    terminal_status = recommendation.status in {"dismissed", "saved"}
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
    if not terminal_status:
        recommendation.status = "available" if is_available else "shadow_observation"
    recommendation.updated_at = _now()
    session.add(recommendation)
    session.flush()
    if queue_email and catalog.source_name == "goozali" and _is_email_eligible(result):
        from .notifications import queue_recommendation_email

        queue_recommendation_email(session, recommendation)
    return True, is_available and not terminal_status


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
    career_fields: list[str] | None = None,
) -> JobRecommendationOut:
    return JobRecommendationOut(
        id=recommendation.id or 0,
        catalog_job_id=catalog.id or 0,
        source_name=catalog.source_name,
        source_url=catalog.source_url,
        application_link=catalog.application_link,
        company=catalog.company,
        role=catalog.role,
        location=catalog.location,
        score=recommendation.score,
        fit_level=recommendation.fit_level,  # type: ignore[arg-type]
        confidence=recommendation.confidence,
        career_fields=career_fields or _json_list(recommendation.career_fields_json),
        reasons=_json_list(recommendation.reasons_json),
        status=recommendation.status,
        created_at=recommendation.created_at,
    )


def _catalog_requirements(catalog: SharedJobCatalog) -> JobRequirements:
    stored = requirements_from_json(catalog.requirements_json)
    if catalog.source_name != "goozali" or stored.reader_version == GOOZALI_READER_VERSION:
        return stored
    return classify_goozali_text(catalog.description_text, catalog.role)


def _candidate_catalogs(
    session: Session,
    interests: set[str],
    beta_member: bool,
) -> Iterator[SharedJobCatalog]:
    """Page through field-relevant jobs before applying expensive scoring."""
    field_filters = [
        SharedJobCatalog.career_fields_json.contains(json.dumps(interest))
        for interest in sorted(interests)
    ]
    catalog_filters = [
        SharedJobCatalog.active.is_(True),
        or_(*field_filters),
    ]
    if not beta_member:
        catalog_filters.append(SharedJobCatalog.source_name != "goozali")
    offset = 0
    while True:
        statement = (
            select(SharedJobCatalog)
            .where(*catalog_filters)
            .order_by(SharedJobCatalog.updated_at.desc(), SharedJobCatalog.id.desc())
            .offset(offset)
            .limit(DISCOVERY_CATALOG_BATCH_SIZE)
        )
        batch = list(session.exec(statement).all())
        if not batch:
            return
        yield from batch
        offset += len(batch)


def _catalog_fields(catalog: SharedJobCatalog, requirements: JobRequirements) -> list[str]:
    stored_fields = _json_list(catalog.career_fields_json)
    declared_field = stored_fields[0] if catalog.source_name == "goozali" and stored_fields else ""
    return route_job_fields(catalog.role, requirements, declared_field)


def _career_field_eligible(interests: set[str], fields: list[str]) -> bool:
    # Career choices are an explicit user filter, not a soft scoring signal.
    # The first field is the role's primary function; secondary technical domains
    # must not make a management or operations role leak into an engineering feed.
    return bool(fields and fields[0] in interests)


def _cheap_eligible(snapshot, requirements, job_location: str) -> bool:
    if (
        requirements.min_years_experience > 0
        and snapshot.years_experience < requirements.min_years_experience
    ):
        return False
    senior_years = (
        max(4.0, requirements.min_years_experience)
        if requirements.experience_requirement_known
        else 5.0
    )
    if requirements.seniority == "senior" and snapshot.years_experience < senior_years:
        return False
    if "part-time" in snapshot.availability.lower() and "full-time" in requirements.availability.lower():
        return False
    if "remote" in requirements.work_mode.lower() or "remote" in job_location.lower():
        return True
    candidate_tokens = _location_tokens(snapshot.location)
    job_tokens = _location_tokens(requirements.location_requirement or job_location)
    return not candidate_tokens or not job_tokens or bool(candidate_tokens & job_tokens)


def _is_available_recommendation(result) -> bool:
    if result.missing_blockers:
        return False
    return (
        result.fit_level in {"Medium", "Strong"}
        and result.score >= DISCOVERY_SUGGESTION_THRESHOLD
        and result.confidence >= DISCOVERY_SUGGESTION_CONFIDENCE
    )


def _is_email_eligible(result) -> bool:
    return (
        result.fit_level == "Strong"
        and result.score >= SHADOW_SCORE_THRESHOLD
        and result.confidence >= SHADOW_CONFIDENCE_THRESHOLD
        and not result.missing_blockers
    )


def _location_tokens(value: str) -> set[str]:
    ignored = {"israel", "hybrid", "onsite", "on-site", "remote", "office"}
    return {
        token
        for token in "".join(character if character.isalnum() else " " for character in value.lower()).split()
        if len(token) > 2 and token not in ignored
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)
