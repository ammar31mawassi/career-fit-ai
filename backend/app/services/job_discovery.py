from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from ..config import Settings, get_settings
from ..models import JobDiscoveryBetaMember, JobSourceRun, SharedJobCatalog
from .goozali import GoozaliFetchResult, GoozaliJob, SOURCE_NAME, fetch_goozali_jobs
from .goozali_reader import classify_goozali_job
from .job_routing import route_job_fields
from .recommendations import enqueue_catalog_job


STALE_AFTER = timedelta(hours=48)


@dataclass(frozen=True)
class DiscoveryOutcome:
    status: str
    records_seen: int = 0
    records_valid: int = 0
    created: int = 0
    updated: int = 0
    ignored: int = 0
    deactivated: int = 0


def run_goozali_discovery(
    session: Session,
    *,
    settings: Settings | None = None,
    fetcher=fetch_goozali_jobs,
    now: datetime | None = None,
) -> DiscoveryOutcome:
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    _sync_beta_members(session, settings.goozali_beta_user_ids, now)
    run = JobSourceRun(source_name=SOURCE_NAME)
    session.add(run)
    session.commit()
    session.refresh(run)
    if not settings.goozali_enabled:
        run.status = "disabled"
        run.completed_at = now
        session.add(run)
        session.commit()
        return DiscoveryOutcome(status="disabled")
    try:
        result: GoozaliFetchResult = fetcher(settings.goozali_embed_url)
        outcome = _ingest_fetch_result(session, result, settings, now)
        run.status = "completed"
        run.records_seen = outcome.records_seen
        run.records_valid = outcome.records_valid
        run.created_count = outcome.created
        run.updated_count = outcome.updated
        run.ignored_count = outcome.ignored
        run.deactivated_count = outcome.deactivated
        run.completed_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()
        return outcome
    except Exception as exc:
        session.rollback()
        persisted = session.get(JobSourceRun, run.id or 0)
        if persisted is not None:
            persisted.status = "failed"
            persisted.error_code = type(exc).__name__[:100]
            persisted.error = _safe_error(exc)
            persisted.completed_at = datetime.now(timezone.utc)
            session.add(persisted)
            session.commit()
        raise


def _ingest_fetch_result(
    session: Session,
    result: GoozaliFetchResult,
    settings: Settings,
    now: datetime,
) -> DiscoveryOutcome:
    existing = {
        item.external_id: item
        for item in session.exec(
            select(SharedJobCatalog).where(SharedJobCatalog.source_name == SOURCE_NAME)
        ).all()
        if item.external_id
    }
    seen_ids = {job.external_id for job in result.jobs}
    cutoff = now - timedelta(hours=settings.goozali_initial_lookback_hours)
    new_jobs = [
        job
        for job in result.jobs
        if job.external_id not in existing
        and max(job.discovered_at, job.source_published_at or job.discovered_at) >= cutoff
    ][: settings.goozali_max_jobs_per_run]
    selected_ids = {job.external_id for job in new_jobs}
    selected = [
        job
        for job in result.jobs
        if job.external_id in existing or job.external_id in selected_ids
    ]
    created = 0
    updated = 0
    for job in selected:
        catalog = existing.get(job.external_id)
        changed = catalog is None or _materially_changed(catalog, job)
        if catalog is None:
            catalog = SharedJobCatalog(
                content_hash=_stable_hash(job.external_id),
                source_name=SOURCE_NAME,
                external_id=job.external_id,
            )
            created += 1
        elif changed:
            updated += 1
        catalog.last_seen_at = now
        catalog.active = True
        if changed:
            requirements = classify_goozali_job(job)
            fields = route_job_fields(job.role, requirements, job.career_field)
            catalog.source_url = job.source_url
            catalog.application_link = job.application_link
            catalog.company = job.company
            catalog.role = job.role
            catalog.location = job.location
            catalog.description_text = job.description_text
            catalog.requirements_json = requirements.to_json()
            catalog.domain = requirements.domain
            catalog.career_fields_json = json.dumps(fields)
            catalog.source_confidence = job.source_confidence
            catalog.source_published_at = job.source_published_at
            catalog.updated_at = now
        session.add(catalog)
        session.flush()
        if changed:
            enqueue_catalog_job(session, catalog.id or 0, None)

    deactivated = 0
    for external_id, catalog in existing.items():
        if external_id in seen_ids or not catalog.active:
            continue
        last_seen = catalog.last_seen_at or catalog.updated_at
        if last_seen <= now - STALE_AFTER:
            catalog.active = False
            catalog.updated_at = now
            session.add(catalog)
            deactivated += 1
    session.commit()
    ignored = max(0, result.records_valid - len(selected))
    return DiscoveryOutcome(
        status="completed",
        records_seen=result.records_seen,
        records_valid=result.records_valid,
        created=created,
        updated=updated,
        ignored=ignored,
        deactivated=deactivated,
    )


def _sync_beta_members(session: Session, user_ids: tuple[UUID, ...], now: datetime) -> None:
    configured = set(user_ids)
    existing = {
        member.user_id: member
        for member in session.exec(
            select(JobDiscoveryBetaMember).where(JobDiscoveryBetaMember.market_code == "IL")
        ).all()
    }
    for user_id, member in existing.items():
        should_be_active = user_id in configured
        if member.active != should_be_active:
            member.active = should_be_active
            member.updated_at = now
            session.add(member)
    for user_id in configured - set(existing):
        session.add(
            JobDiscoveryBetaMember(
                user_id=user_id,
                market_code="IL",
                active=True,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()


def _materially_changed(catalog: SharedJobCatalog, job: GoozaliJob) -> bool:
    return any(
        (
            catalog.company != job.company,
            catalog.role != job.role,
            catalog.location != job.location,
            catalog.description_text != job.description_text,
            catalog.application_link != job.application_link,
        )
    )


def _stable_hash(external_id: str) -> str:
    return hashlib.sha256(f"{SOURCE_NAME}|{external_id}".encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    return (message or type(exc).__name__)[:500]
