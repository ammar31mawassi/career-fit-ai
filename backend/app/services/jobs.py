from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from ..models import Job, JobMatch, JobStatusEvent, Profile, ResumeAdvice
from ..schemas import JobCreateIn, JobMatchOut, JobOut, JobStatusEventOut, RequirementModel, ResumeAdviceOut
from .job_research import JOB_READER_VERSION, extract_job_from_input, requirements_from_json
from .matcher import score_match
from .profile import candidate_snapshot, get_or_create_profile


def create_or_analyze_job(session: Session, user_id: UUID, payload: JobCreateIn) -> JobOut:
    profile = get_or_create_profile(session, user_id)
    if profile.status == "needs_cv":
        raise ValueError("Upload at least one CV before matching jobs.")

    content_hash = _content_hash(payload.source_url, payload.description_text, payload.company, payload.role)
    existing = session.exec(
        select(Job).where(Job.user_id == user_id, Job.content_hash == content_hash)
    ).first()
    if existing and _can_reuse(existing, payload):
        return job_output(session, user_id, existing.id or 0)

    try:
        extracted = extract_job_from_input(
            payload.source_url,
            payload.company,
            payload.role,
            payload.description_text,
        )
    except Exception as exc:
        if existing and existing.status == "analyzed":
            return job_output(session, user_id, existing.id or 0)
        job = existing or Job(user_id=user_id, content_hash=content_hash, created_at=_now())
        job.source_url = payload.source_url.strip()
        job.company = payload.company.strip() or "Unknown Company"
        job.role = payload.role.strip() or "Unknown Role"
        job.description_text = payload.description_text.strip()
        job.status = "failed"
        job.error = str(exc)[:500]
        job.updated_at = _now()
        session.add(job)
        session.commit()
        session.refresh(job)
        return job_output(session, user_id, job.id or 0)

    job = existing or Job(user_id=user_id, content_hash=content_hash, created_at=_now())
    job.source_url = extracted.source_url
    job.company = extracted.company
    job.role = extracted.role
    job.location = extracted.location
    job.description_text = extracted.description_text
    job.source_title = extracted.source_title
    job.source_confidence = extracted.source_confidence
    job.application_link = extracted.application_link
    job.requirements_json = extracted.requirements.to_json()
    job.status = "analyzed"
    job.error = ""
    job.updated_at = _now()
    session.add(job)
    session.commit()
    session.refresh(job)
    _save_match(session, user_id, profile, job)
    return job_output(session, user_id, job.id or 0)


def _can_reuse(job: Job, payload: JobCreateIn) -> bool:
    if job.status != "analyzed":
        return False
    requirements = requirements_from_json(job.requirements_json)
    if requirements.reader_version != JOB_READER_VERSION:
        return False
    pasted = " ".join(payload.description_text.lower().split())
    stored = " ".join(job.description_text.lower().split())
    if pasted and pasted != stored:
        return False
    return True


def list_jobs(session: Session, user_id: UUID, query: str = "", limit: int = 100) -> list[JobOut]:
    statement = select(Job).where(Job.user_id == user_id).order_by(Job.updated_at.desc()).limit(limit)
    jobs = list(session.exec(statement).all())
    if query.strip():
        normalized = query.strip().lower()
        jobs = [
            job
            for job in jobs
            if normalized in " ".join([job.company, job.role, job.source_url, job.description_text]).lower()
        ]
    return [_job_to_out(session, user_id, job) for job in jobs]


def job_output(session: Session, user_id: UUID, job_id: int) -> JobOut:
    job = session.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise ValueError("Job not found.")
    return _job_to_out(session, user_id, job)


def update_job_status(session: Session, user_id: UUID, job_id: int, status: str) -> JobOut:
    job = session.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise ValueError("Job not found.")
    match = session.exec(select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job_id)).first()
    if not match:
        profile = get_or_create_profile(session, user_id)
        match = _save_match(session, user_id, profile, job)
    previous_status = match.status
    match.status = status
    match.updated_at = _now()
    session.add(match)
    if previous_status != status:
        session.add(JobStatusEvent(user_id=user_id, match_id=match.id or 0, status=status, created_at=_now()))
    session.commit()
    return job_output(session, user_id, job_id)


def _save_match(session: Session, user_id: UUID, profile: Profile, job: Job) -> JobMatch:
    requirements = requirements_from_json(job.requirements_json)
    snapshot = candidate_snapshot(session, profile)
    result = score_match(snapshot, job.company, job.role, requirements, job.source_confidence)
    match = session.exec(select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job.id)).first()
    if match is None:
        match = JobMatch(user_id=user_id, job_id=job.id or 0)
        is_new = True
    else:
        is_new = False
    match.score = result.score
    match.fit_level = result.fit_level
    match.confidence = result.confidence
    match.matched_evidence_json = json.dumps(result.matched_evidence)
    match.missing_blockers_json = json.dumps(result.missing_blockers)
    match.gaps_json = json.dumps(result.gaps)
    match.model_version = result.model_version
    match.ontology_version = result.ontology_version
    match.component_scores_json = json.dumps(result.component_scores, sort_keys=True)
    match.applied_caps_json = json.dumps(result.applied_caps)
    match.feature_snapshot_json = json.dumps(result.feature_snapshot, sort_keys=True)
    match.analyzed_at = _now()
    match.updated_at = _now()
    session.add(match)
    session.commit()
    session.refresh(match)
    if is_new:
        session.add(JobStatusEvent(user_id=user_id, match_id=match.id or 0, status=match.status, created_at=_now()))
        session.commit()

    advice = session.exec(
        select(ResumeAdvice).where(ResumeAdvice.user_id == user_id, ResumeAdvice.match_id == match.id)
    ).first()
    if advice is None:
        advice = ResumeAdvice(user_id=user_id, match_id=match.id or 0)
    advice.projects_json = json.dumps(result.projects)
    advice.skill_order_json = json.dumps(result.skill_order)
    advice.about_text = result.about_text
    advice.template_id = result.about_template_id
    advice.evidence_json = json.dumps(result.about_evidence)
    advice.generated_at = _now()
    session.add(advice)
    session.commit()
    return match


def _job_to_out(session: Session, user_id: UUID, job: Job) -> JobOut:
    match = session.exec(select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job.id)).first()
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if match and profile and profile.status == "ready" and _is_after(profile.updated_at, match.analyzed_at):
        match = _save_match(session, user_id, profile, job)
    return JobOut(
        id=job.id or 0,
        source_url=job.source_url,
        company=job.company,
        role=job.role,
        location=job.location,
        description_text=job.description_text,
        source_title=job.source_title,
        source_confidence=job.source_confidence,
        application_link=job.application_link,
        status=job.status,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        requirements=RequirementModel.model_validate(asdict(requirements_from_json(job.requirements_json))),
        match=_match_out(session, user_id, match) if match else None,
    )


def _is_after(left: datetime, right: datetime) -> bool:
    if left.tzinfo is None:
        left = left.replace(tzinfo=timezone.utc)
    if right.tzinfo is None:
        right = right.replace(tzinfo=timezone.utc)
    return left > right


def _match_out(session: Session, user_id: UUID, match: JobMatch) -> JobMatchOut:
    advice = session.exec(
        select(ResumeAdvice).where(ResumeAdvice.user_id == user_id, ResumeAdvice.match_id == match.id)
    ).first()
    events = list(
        session.exec(
            select(JobStatusEvent)
            .where(JobStatusEvent.user_id == user_id, JobStatusEvent.match_id == match.id)
            .order_by(JobStatusEvent.created_at)
        ).all()
    )
    return JobMatchOut(
        id=match.id or 0,
        score=match.score,
        fit_level=match.fit_level,  # type: ignore[arg-type]
        confidence=match.confidence,
        status=match.status,  # type: ignore[arg-type]
        matched_evidence=_load_list(match.matched_evidence_json),
        missing_blockers=_load_list(match.missing_blockers_json),
        gaps=_load_list(match.gaps_json),
        model_version=match.model_version,
        ontology_version=match.ontology_version,
        component_scores=_load_dict(match.component_scores_json),
        applied_caps=_load_list(match.applied_caps_json),
        status_history=[
            JobStatusEventOut(status=event.status, created_at=event.created_at)  # type: ignore[arg-type]
            for event in events
        ],
        resume_advice=ResumeAdviceOut(
            projects=_load_list(advice.projects_json) if advice else [],
            skill_order=_load_list(advice.skill_order_json) if advice else [],
            about_text=advice.about_text if advice else "",
            template_id=advice.template_id if advice else "",
            evidence=_load_list(advice.evidence_json) if advice else [],
        ),
        analyzed_at=match.analyzed_at,
    )


def _content_hash(source_url: str, description: str, company: str, role: str) -> str:
    normalized_url = source_url.strip().rstrip("/").lower()
    if normalized_url:
        return hashlib.sha256(f"url|{normalized_url}".encode("utf-8")).hexdigest()
    normalized_text = " ".join(description.lower().split())
    payload = "|".join([normalized_text, company.strip().lower(), role.strip().lower()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_list(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [value]
    return [str(item) for item in parsed] if isinstance(parsed, list) else [str(parsed)]


def _load_dict(value: str) -> dict[str, float]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    output: dict[str, float] = {}
    for key, item in parsed.items():
        try:
            output[str(key)] = float(item)
        except (TypeError, ValueError):
            continue
    return output


def _now() -> datetime:
    return datetime.now(timezone.utc)
