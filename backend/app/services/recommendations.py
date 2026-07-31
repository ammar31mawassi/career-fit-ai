from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, text, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import (
    ExtractionMetric,
    Job,
    JobDiscoveryBetaMember,
    JobRecommendation,
    Profile,
    ProfileInterest,
    RecommendationEvent,
    RecommendationFieldCalibration,
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
QUEUE_VISIBILITY_SECONDS = 900
QUEUE_MAX_ATTEMPTS = 3
MAX_CANDIDATES_PER_JOB = 250
MAX_DISCOVERY_BACKFILL_JOBS = 40
MAX_DISCOVERY_SCORE_BUDGET = 250
DISCOVERY_CATALOG_BATCH_SIZE = 250
SHADOW_SCORE_THRESHOLD = 76.0
SHADOW_CONFIDENCE_THRESHOLD = 0.55
DISCOVERY_SUGGESTION_THRESHOLD = 40.0
DISCOVERY_SUGGESTION_CONFIDENCE = 0.45
CALIBRATION_WINDOW_DAYS = 90
CALIBRATION_MINIMUM_SAMPLE = 20
CALIBRATION_BAND_MINIMUM_SAMPLE = 8
CALIBRATION_REFRESH_INTERVAL = timedelta(hours=1)
ACTIONABLE_RECOMMENDATION_STATUSES = ("available", "shadow_eligible")
SCORABLE_RECOMMENDATION_STATUSES = (
    "available",
    "shadow_eligible",
    "shadow_observation",
)
CALIBRATION_NEGATIVE_DISMISS_REASONS = {"wrong_field", "missing_skills"}
DISMISS_REASONS = {
    "too_senior",
    "wrong_field",
    "wrong_location",
    "missing_skills",
    "employment_type",
    "not_interested",
    "other",
}
PUBLIC_JOB_READER_STRATEGIES = frozenset(
    {
        "json_ld",
        "json_ld+scoped_html",
        "meta_description",
        "scoped_html",
        "workday_api",
        "workday_api+scoped_html",
    }
)
logger = logging.getLogger(__name__)


def catalog_and_enqueue_job(session: Session, source_user_id: UUID, job: Job) -> SharedJobCatalog | None:
    if not _has_public_job_provenance(session, source_user_id, job):
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


def _has_public_job_provenance(session: Session, source_user_id: UUID, job: Job) -> bool:
    """Only redistribute descriptions that were read from a public job URL.

    A URL on its own is not proof of public provenance because the scanner also
    accepts pasted text alongside an optional application URL. ExtractionMetric
    records which input actually supplied the description. Requiring the latest
    successful metric also prevents a later pasted rescan from overwriting a
    previously public catalog entry.
    """
    if job.id is None or job.status != "analyzed" or not job.source_url.strip():
        return False
    latest_metric = session.exec(
        select(ExtractionMetric)
        .where(
            ExtractionMetric.user_id == source_user_id,
            ExtractionMetric.workflow_type == "job_extraction",
            ExtractionMetric.subject_type == "job",
            ExtractionMetric.subject_id == job.id,
        )
        .order_by(ExtractionMetric.created_at.desc(), ExtractionMetric.id.desc())
    ).first()
    return bool(
        latest_metric
        and latest_metric.status == "succeeded"
        and latest_metric.strategy in PUBLIC_JOB_READER_STRATEGIES
    )


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
        profiles = _rotated_candidate_profiles(session, statement, catalog)
        run.candidate_count = len(profiles)
        scorer = get_match_scorer()
        primary_field = fields[0] if fields else ""
        _refresh_stale_field_calibration(session, primary_field)
        minimum_score = discovery_threshold_for_field(session, primary_field)
        candidate_user_ids = [profile.user_id for profile in profiles]
        already_saved_users = {
            user_id
            for user_id in session.exec(
                select(Job.user_id).where(
                    Job.content_hash == catalog.content_hash,
                    Job.user_id.in_(candidate_user_ids or [UUID(int=0)]),
                )
            ).all()
        }
        recommendations_by_key = {
            (recommendation.user_id, recommendation.model_version): recommendation
            for recommendation in session.exec(
                select(JobRecommendation).where(
                    JobRecommendation.catalog_job_id == catalog_job_id,
                    JobRecommendation.user_id.in_(candidate_user_ids or [UUID(int=0)]),
                )
            ).all()
        }
        for profile in profiles:
            if profile.user_id in already_saved_users:
                continue
            snapshot = candidate_snapshot(session, profile)
            scored, is_strong = _score_catalog_for_profile(
                session,
                catalog,
                profile,
                snapshot,
                requirements,
                fields,
                scorer,
                minimum_score=minimum_score,
                already_saved=False,
                recommendations_by_key=recommendations_by_key,
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
        run_id = run.id
        error = str(exc)[:500]
        # A failed flush leaves SQLAlchemy/PostgreSQL in a failed transaction.
        # Record the durable failure only after restoring a clean transaction.
        session.rollback()
        failed_run = session.get(RecommendationRun, run_id) if run_id is not None else None
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.error = error
            failed_run.completed_at = _now()
            session.add(failed_run)
            session.commit()
        raise


def process_one_queued_recommendation(session: Session) -> RecommendationRun | None:
    if session.get_bind().dialect.name != "postgresql":
        return None
    row = session.exec(
        text(
            "select msg_id, read_ct, message "
            "from pgmq.read(:queue_name, :visibility_seconds, 1)"
        ).bindparams(
            queue_name=QUEUE_NAME,
            visibility_seconds=QUEUE_VISIBILITY_SECONDS,
        )
    ).first()
    if row is None:
        return None
    msg_id = int(row[0])
    read_count = int(row[1])
    try:
        message = row[2] if isinstance(row[2], dict) else json.loads(str(row[2]))
        if not isinstance(message, dict):
            raise TypeError("Queue message must be an object.")
        catalog_job_id = int(message["catalog_job_id"])
        if catalog_job_id <= 0:
            raise ValueError("Catalog job id must be positive.")
        source_user_id = (
            UUID(str(message["source_user_id"]))
            if message.get("source_user_id")
            else None
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Archiving malformed recommendation queue message msg_id=%s", msg_id)
        _archive_queue_message(session, msg_id)
        session.commit()
        return None

    # Persist PGMQ's read count and visibility lease independently of the scoring
    # transaction. Otherwise a pre-run validation failure can hot-loop forever.
    session.commit()
    try:
        run = generate_shadow_recommendations(
            session,
            catalog_job_id,
            source_user_id,
        )
    except Exception:
        session.rollback()
        if read_count >= QUEUE_MAX_ATTEMPTS:
            logger.exception(
                "Archiving recommendation queue message after %s attempts msg_id=%s",
                read_count,
                msg_id,
            )
            _archive_queue_message(session, msg_id)
            session.commit()
        else:
            logger.exception(
                "Recommendation queue message will retry attempt=%s msg_id=%s",
                read_count,
                msg_id,
            )
        return None
    _archive_queue_message(session, msg_id)
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
    prepared: list[tuple[JobRecommendation, SharedJobCatalog, JobRequirements, list[str]]] = []
    primary_fields: set[str] = set()
    for item in recommendations:
        catalog = catalogs.get(item.catalog_job_id)
        if catalog is None:
            continue
        requirements = _catalog_requirements(catalog)
        fields = _catalog_fields(catalog, requirements)
        prepared.append((item, catalog, requirements, fields))
        primary_fields.add(fields[0] if fields else "")
    calibrations = {
        item.career_field: item.minimum_score
        for item in session.exec(
            select(RecommendationFieldCalibration).where(
                RecommendationFieldCalibration.career_field.in_(primary_fields or {"__none__"})
            )
        ).all()
    }
    output: list[JobRecommendationOut] = []
    for item, catalog, requirements, fields in prepared:
        if not _career_field_eligible(interests, fields):
            continue
        if item.score < calibrations.get(fields[0] if fields else "", DISCOVERY_SUGGESTION_THRESHOLD):
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
    threshold_cache: dict[str, float] = {}
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
        primary_field = fields[0] if fields else ""
        if primary_field not in threshold_cache:
            threshold_cache[primary_field] = discovery_threshold_for_field(session, primary_field)
        was_scored, is_available = _score_catalog_for_profile(
            session,
            catalog,
            profile,
            snapshot,
            requirements,
            fields,
            scorer,
            queue_email=False,
            minimum_score=threshold_cache[primary_field],
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
    *,
    dismiss_reason: str | None = None,
) -> tuple[JobRecommendationOut, JobOut | None]:
    # Imported lazily because jobs catalogues completed scans into this module.
    from .jobs import job_output, save_match

    if status not in {"dismissed", "saved"}:
        raise ValueError("Unsupported recommendation action.")
    if status == "dismissed" and dismiss_reason not in DISMISS_REASONS:
        raise ValueError("Choose a valid dismissal reason.")
    recommendation = session.get(JobRecommendation, recommendation_id)
    if recommendation is None or recommendation.user_id != user_id:
        raise ValueError("Recommendation not found.")
    catalog = session.get(SharedJobCatalog, recommendation.catalog_job_id)
    if catalog is None or not catalog.active:
        raise ValueError("Recommended job is no longer available.")
    try:
        recommendation, transitioned = _transition_recommendation_action(
            session,
            recommendation,
            status,
        )
        if status == "dismissed":
            _record_recommendation_event(
                session,
                recommendation,
                catalog,
                "dismissed",
                dismiss_reason=dismiss_reason or "",
            )
            session.commit()
            return _recommendation_out(recommendation, catalog), None

        if not transitioned and recommendation.materialized_job_id is not None:
            job_id = recommendation.materialized_job_id
            _record_recommendation_event(
                session,
                recommendation,
                catalog,
                "saved",
                materialized_job_id=job_id,
            )
            session.commit()
            return (
                _recommendation_out(recommendation, catalog),
                job_output(session, user_id, job_id),
            )
        if not transitioned:
            # Heal a historical `saved` row without a materialized job while
            # retaining the same row lock/conditional semantics as a new action.
            claimed_missing_job = session.execute(
                update(JobRecommendation)
                .where(
                    JobRecommendation.id == recommendation_id,
                    JobRecommendation.user_id == user_id,
                    JobRecommendation.status == "saved",
                    JobRecommendation.materialized_job_id.is_(None),
                )
                .values(updated_at=_now())
                .execution_options(synchronize_session=False)
            )
            if claimed_missing_job.rowcount != 1:
                session.expire_all()
                current = session.get(JobRecommendation, recommendation_id)
                if (
                    current is not None
                    and current.user_id == user_id
                    and current.status == "saved"
                    and current.materialized_job_id is not None
                ):
                    session.commit()
                    return (
                        _recommendation_out(current, catalog),
                        job_output(session, user_id, current.materialized_job_id),
                    )
                raise ValueError("Recommendation was already handled.")

        job = session.exec(
            select(Job).where(Job.user_id == user_id, Job.content_hash == catalog.content_hash)
        ).first()
        if job is None:
            candidate_job = Job(user_id=user_id, content_hash=catalog.content_hash)
            try:
                with session.begin_nested():
                    session.add(candidate_job)
                    session.flush()
            except IntegrityError:
                job = session.exec(
                    select(Job).where(
                        Job.user_id == user_id,
                        Job.content_hash == catalog.content_hash,
                    )
                ).one()
            else:
                job = candidate_job
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
        recommendation.materialized_job_id = job.id
        recommendation.updated_at = _now()
        session.add(recommendation)
        _record_recommendation_event(
            session,
            recommendation,
            catalog,
            "saved",
            materialized_job_id=job.id,
        )
        session.commit()
        return (
            _recommendation_out(recommendation, catalog),
            job_output(session, user_id, job.id or 0),
        )
    except Exception:
        session.rollback()
        raise


def _transition_recommendation_action(
    session: Session,
    recommendation: JobRecommendation,
    status: str,
) -> tuple[JobRecommendation, bool]:
    transitioned = session.execute(
        update(JobRecommendation)
        .where(
            JobRecommendation.id == recommendation.id,
            JobRecommendation.user_id == recommendation.user_id,
            JobRecommendation.status.in_(ACTIONABLE_RECOMMENDATION_STATUSES),
        )
        .values(status=status, updated_at=_now())
        .execution_options(synchronize_session=False)
    )
    session.expire_all()
    current = session.get(JobRecommendation, recommendation.id)
    if current is None or current.user_id != recommendation.user_id:
        raise ValueError("Recommendation not found.")
    if transitioned.rowcount == 1:
        return current, True
    if current.status in {"dismissed", "saved"} and current.status != status:
        raise ValueError("Recommendation was already handled.")
    if current.status != status:
        raise ValueError("Recommendation is not actionable.")
    return current, False


def record_recommendation_view(
    session: Session,
    user_id: UUID,
    recommendation_id: int,
) -> None:
    recommendation = session.get(JobRecommendation, recommendation_id)
    if recommendation is None or recommendation.user_id != user_id:
        raise ValueError("Recommendation not found.")
    catalog = session.get(SharedJobCatalog, recommendation.catalog_job_id)
    if catalog is None:
        raise ValueError("Recommended job is no longer available.")
    _record_recommendation_event(session, recommendation, catalog, "viewed")
    session.commit()


def record_recommendation_application(
    session: Session,
    user_id: UUID,
    job_id: int,
) -> None:
    recommendation = session.exec(
        select(JobRecommendation)
        .where(
            JobRecommendation.user_id == user_id,
            JobRecommendation.materialized_job_id == job_id,
        )
        .order_by(JobRecommendation.updated_at.desc())
    ).first()
    if recommendation is None:
        job = session.get(Job, job_id)
        if job is None or job.user_id != user_id:
            return
        catalog = session.exec(
            select(SharedJobCatalog).where(SharedJobCatalog.content_hash == job.content_hash)
        ).first()
        if catalog is None:
            return
        recommendation = session.exec(
            select(JobRecommendation)
            .where(
                JobRecommendation.user_id == user_id,
                JobRecommendation.catalog_job_id == (catalog.id or 0),
                JobRecommendation.status == "saved",
            )
            .order_by(JobRecommendation.updated_at.desc())
        ).first()
        if recommendation is None:
            return
        recommendation.materialized_job_id = job_id
        session.add(recommendation)
    catalog = session.get(SharedJobCatalog, recommendation.catalog_job_id)
    if catalog is None:
        return
    _record_recommendation_event(
        session,
        recommendation,
        catalog,
        "applied",
        materialized_job_id=job_id,
    )


def discovery_threshold_for_field(session: Session, career_field: str) -> float:
    if not career_field:
        return DISCOVERY_SUGGESTION_THRESHOLD
    calibration = session.get(RecommendationFieldCalibration, career_field)
    if calibration is None or calibration.minimum_score not in {40.0, 50.0, 65.0}:
        return DISCOVERY_SUGGESTION_THRESHOLD
    return calibration.minimum_score


def refresh_field_calibration(
    session: Session,
    career_field: str,
) -> RecommendationFieldCalibration | None:
    if not career_field or career_field == "unknown":
        return None
    cutoff = _now() - timedelta(days=CALIBRATION_WINDOW_DAYS)
    events = list(
        session.exec(
            select(
                RecommendationEvent.recommendation_id,
                RecommendationEvent.event_type,
                RecommendationEvent.score,
                RecommendationEvent.dismiss_reason,
            ).where(
                RecommendationEvent.career_field == career_field,
                RecommendationEvent.event_type.in_(["saved", "applied", "dismissed"]),
                RecommendationEvent.created_at >= cutoff,
            )
        ).all()
    )
    # A recommendation may be saved and later applied. It still contributes one
    # positive example so frequent users do not receive extra voting weight.
    outcomes: dict[int, tuple[bool, float]] = {}
    for recommendation_id, event_type, score, dismiss_reason in events:
        if (
            event_type == "dismissed"
            and dismiss_reason not in CALIBRATION_NEGATIVE_DISMISS_REASONS
        ):
            # Logistics and individual preference are not global relevance
            # labels, so they must not suppress future exposure for a field.
            continue
        is_positive = event_type in {"saved", "applied"}
        current = outcomes.get(recommendation_id)
        if current is None or (is_positive and not current[0]):
            outcomes[recommendation_id] = (is_positive, score)

    values = list(outcomes.values())
    possible = [value for value in values if 40 <= value[1] < 50]
    medium = [value for value in values if 50 <= value[1] < 65]
    positive_count = sum(1 for is_positive, _score in values if is_positive)
    possible_positive_count = sum(1 for is_positive, _score in possible if is_positive)
    medium_positive_count = sum(1 for is_positive, _score in medium if is_positive)

    minimum_score = DISCOVERY_SUGGESTION_THRESHOLD
    if len(values) >= CALIBRATION_MINIMUM_SAMPLE:
        if (
            len(possible) >= CALIBRATION_BAND_MINIMUM_SAMPLE
            and possible_positive_count / len(possible) < 0.15
        ):
            minimum_score = 50.0
        if (
            len(medium) >= CALIBRATION_BAND_MINIMUM_SAMPLE
            and medium_positive_count / len(medium) < 0.20
        ):
            minimum_score = 65.0

    calibration_values = {
        "minimum_score": minimum_score,
        "sample_size": len(values),
        "positive_count": positive_count,
        "negative_count": len(values) - positive_count,
        "possible_sample_size": len(possible),
        "possible_positive_count": possible_positive_count,
        "medium_sample_size": len(medium),
        "medium_positive_count": medium_positive_count,
        "window_days": CALIBRATION_WINDOW_DAYS,
        "updated_at": _now(),
    }
    calibration = session.get(RecommendationFieldCalibration, career_field)
    if calibration is None:
        candidate = RecommendationFieldCalibration(
            career_field=career_field,
            **calibration_values,
        )
        try:
            with session.begin_nested():
                session.add(candidate)
                session.flush()
        except IntegrityError:
            calibration = session.get(RecommendationFieldCalibration, career_field)
            if calibration is None:
                raise
        else:
            return candidate
    for key, value in calibration_values.items():
        setattr(calibration, key, value)
    session.add(calibration)
    session.flush()
    return calibration


def _refresh_stale_field_calibration(session: Session, career_field: str) -> None:
    """Refresh feedback aggregates off the user-action request path."""
    if not career_field or career_field == "unknown":
        return
    calibration = session.get(RecommendationFieldCalibration, career_field)
    if calibration is None:
        refresh_field_calibration(session, career_field)
        return
    updated_at = calibration.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if updated_at <= _now() - CALIBRATION_REFRESH_INTERVAL:
        refresh_field_calibration(session, career_field)


def _record_recommendation_event(
    session: Session,
    recommendation: JobRecommendation,
    catalog: SharedJobCatalog,
    event_type: str,
    *,
    dismiss_reason: str = "",
    materialized_job_id: int | None = None,
) -> RecommendationEvent:
    recommendation_id = recommendation.id or 0
    existing = session.exec(
        select(RecommendationEvent).where(
            RecommendationEvent.user_id == recommendation.user_id,
            RecommendationEvent.recommendation_id == recommendation_id,
            RecommendationEvent.event_type == event_type,
        )
    ).first()
    if existing is not None:
        return existing
    event = RecommendationEvent(
        user_id=recommendation.user_id,
        recommendation_id=recommendation_id,
        catalog_job_id=recommendation.catalog_job_id,
        materialized_job_id=materialized_job_id or recommendation.materialized_job_id,
        event_type=event_type,
        dismiss_reason=dismiss_reason,
        score=recommendation.score,
        score_band=_score_band(recommendation.score),
        career_field=_primary_field(recommendation),
        source_name=catalog.source_name,
        model_version=recommendation.model_version,
    )
    try:
        with session.begin_nested():
            session.add(event)
            session.flush()
    except IntegrityError:
        concurrent = session.exec(
            select(RecommendationEvent).where(
                RecommendationEvent.user_id == recommendation.user_id,
                RecommendationEvent.recommendation_id == recommendation_id,
                RecommendationEvent.event_type == event_type,
            )
        ).one()
        return concurrent
    return event


def _primary_field(recommendation: JobRecommendation) -> str:
    fields = _json_list(recommendation.career_fields_json)
    return fields[0].strip() if fields and fields[0].strip() else "unknown"


def _score_band(score: float) -> str:
    if score < 50:
        return "possible"
    if score < 75:
        return "medium"
    return "strong"


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


def _archive_queue_message(session: Session, msg_id: int) -> None:
    session.exec(
        text("select pgmq.archive(:queue_name, :msg_id)").bindparams(
            queue_name=QUEUE_NAME,
            msg_id=msg_id,
        )
    )


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
    minimum_score: float | None = None,
    already_saved: bool | None = None,
    recommendations_by_key: dict[tuple[UUID, str], JobRecommendation] | None = None,
) -> tuple[bool, bool]:
    if already_saved is None:
        already_saved = (
            session.exec(
                select(Job.id).where(
                    Job.user_id == profile.user_id,
                    Job.content_hash == catalog.content_hash,
                )
            ).first()
            is not None
        )
    if already_saved or not _cheap_eligible(snapshot, requirements, catalog.location):
        return False, False
    result = scorer.score(
        snapshot,
        catalog.company,
        catalog.role,
        requirements,
        catalog.source_confidence,
    )
    threshold = (
        minimum_score
        if minimum_score is not None
        else discovery_threshold_for_field(session, fields[0] if fields else "")
    )
    is_available = _is_available_recommendation(result, threshold)
    recommendation = (
        recommendations_by_key.get((profile.user_id, result.model_version))
        if recommendations_by_key is not None
        else session.exec(
            select(JobRecommendation).where(
                JobRecommendation.user_id == profile.user_id,
                JobRecommendation.catalog_job_id == (catalog.id or 0),
                JobRecommendation.model_version == result.model_version,
            )
        ).first()
    )
    recommendation_values = {
        "score": result.score,
        "fit_level": result.fit_level,
        "confidence": result.confidence,
        "career_fields_json": json.dumps(fields),
        "reasons_json": json.dumps(result.matched_evidence[:4]),
        "match_snapshot_json": json.dumps(
            {
                "matched_evidence": result.matched_evidence,
                "gaps": result.gaps,
                "component_scores": result.component_scores,
                "projects": result.projects,
                "skill_order": result.skill_order,
                "about_text": result.about_text,
            },
            sort_keys=True,
        ),
        "status": "available" if is_available else "shadow_observation",
        "updated_at": _now(),
    }
    inserted = False
    if recommendation is None:
        candidate = JobRecommendation(
            user_id=profile.user_id,
            catalog_job_id=catalog.id or 0,
            model_version=result.model_version,
            **recommendation_values,
        )
        try:
            with session.begin_nested():
                session.add(candidate)
                session.flush()
        except IntegrityError:
            recommendation = session.exec(
                select(JobRecommendation).where(
                    JobRecommendation.user_id == profile.user_id,
                    JobRecommendation.catalog_job_id == (catalog.id or 0),
                    JobRecommendation.model_version == result.model_version,
                )
            ).one()
        else:
            recommendation = candidate
            inserted = True
            if recommendations_by_key is not None:
                recommendations_by_key[(profile.user_id, result.model_version)] = recommendation
            actionable_available = is_available
    if not inserted:
        if recommendation is None:
            raise RuntimeError("Recommendation upsert did not return a row.")
        updated = session.execute(
            update(JobRecommendation)
            .where(
                JobRecommendation.id == recommendation.id,
                JobRecommendation.status.in_(SCORABLE_RECOMMENDATION_STATUSES),
            )
            .values(**recommendation_values)
            .execution_options(synchronize_session=False)
        )
        session.expire(recommendation)
        actionable_available = updated.rowcount == 1 and is_available
    if (
        queue_email
        and actionable_available
        and catalog.source_name == "goozali"
        and _is_email_eligible(result)
    ):
        from .notifications import queue_recommendation_email

        queue_recommendation_email(session, recommendation)
    return True, actionable_available


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


def _rotated_candidate_profiles(
    session: Session,
    statement,
    catalog: SharedJobCatalog,
) -> list[Profile]:
    """Select a stable, per-job rotation instead of an arbitrary first 250."""
    digest = hashlib.sha256(
        f"{catalog.id or 0}:{catalog.content_hash}".encode("utf-8")
    ).digest()
    rotation_point = UUID(bytes=digest[:16])
    after = list(
        session.exec(
            statement.where(Profile.user_id >= rotation_point)
            .order_by(Profile.user_id)
            .limit(MAX_CANDIDATES_PER_JOB)
        ).all()
    )
    remaining = MAX_CANDIDATES_PER_JOB - len(after)
    if remaining <= 0:
        return after
    before = list(
        session.exec(
            statement.where(Profile.user_id < rotation_point)
            .order_by(Profile.user_id)
            .limit(remaining)
        ).all()
    )
    return [*after, *before]


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


def _is_available_recommendation(
    result,
    minimum_score: float = DISCOVERY_SUGGESTION_THRESHOLD,
) -> bool:
    if result.missing_blockers:
        return False
    return (
        result.fit_level in {"Weak", "Medium", "Strong"}
        and result.score >= max(DISCOVERY_SUGGESTION_THRESHOLD, min(65.0, minimum_score))
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
