from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import Session, select

from ..models import Job, JobMatch, JobStatusEvent, Profile, ResumeAdvice
from ..schemas import (
    JobCreateIn,
    JobMatchOut,
    JobMatchSummaryOut,
    JobOut,
    JobStatusEventOut,
    JobSummaryOut,
    RequirementModel,
    ResumeAdviceOut,
)
from .agent_workflows import (
    JOB_READER_WORKFLOW_VERSION,
    attach_subject,
    complete_run,
    complete_step,
    fail_run,
    fail_step,
    latest_agent_run_for_subject,
    start_agent_run,
    start_step,
)
from .job_research import JOB_READER_VERSION, extract_job_from_input, requirements_from_json
from .profile import candidate_snapshot, get_or_create_profile
from .recommendations import catalog_and_enqueue_job
from .scoring import get_match_scorer


def create_or_analyze_job(session: Session, user_id: UUID, payload: JobCreateIn) -> JobOut:
    profile = get_or_create_profile(session, user_id)
    if profile.status == "needs_cv":
        raise ValueError("Upload at least one CV before matching jobs.")

    content_hash = _content_hash(payload.source_url, payload.description_text, payload.company, payload.role)
    run = start_agent_run(
        session,
        user_id,
        "job_reader",
        input_hash=content_hash,
        version=JOB_READER_WORKFLOW_VERSION,
        subject_type="job",
        summary="Job reader workflow started.",
    )
    validation_step = start_step(session, run, "validate_profile", "Validate profile readiness")
    complete_step(
        session,
        validation_step,
        "Profile has a CV-backed analysis state and can be matched.",
        {"profile_status": profile.status},
    )

    dedupe_step = start_step(session, run, "dedupe_lookup", "Check saved-job cache")
    existing = session.exec(
        select(Job).where(Job.user_id == user_id, Job.content_hash == content_hash)
    ).first()
    if existing and _can_reuse(existing, payload):
        attach_subject(session, run, "job", existing.id or 0)
        complete_step(
            session,
            dedupe_step,
            "Existing job analysis reused; no rescan needed.",
            {"job_id": existing.id or 0, "reader_version": JOB_READER_VERSION},
        )
        complete_run(session, run, "Existing saved job reused.", status="reused")
        session.commit()
        _catalog_for_discovery(session, user_id, existing)
        return job_output(session, user_id, existing.id or 0)
    complete_step(
        session,
        dedupe_step,
        "No reusable analysis found; scanning the submitted source.",
        {"had_existing_job": bool(existing)},
    )

    extraction_step = start_step(session, run, "extract_job", "Extract job content and source metadata")
    try:
        extracted = extract_job_from_input(
            payload.source_url,
            payload.company,
            payload.role,
            payload.description_text,
        )
    except Exception as exc:
        fail_step(session, extraction_step, str(exc), {"source_url": payload.source_url.strip()})
        if existing and existing.status == "analyzed":
            attach_subject(session, run, "job", existing.id or 0)
            complete_run(session, run, "Extraction failed, existing analyzed job reused.", status="reused")
            session.commit()
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
        attach_subject(session, run, "job", job.id or 0)
        fail_run(session, run, str(exc), "Job reader failed during extraction.")
        session.commit()
        return job_output(session, user_id, job.id or 0)
    complete_step(
        session,
        extraction_step,
        "Job content extracted and normalized.",
        {
            "company": extracted.company,
            "role": extracted.role,
            "source_confidence": round(extracted.source_confidence, 3),
            "description_chars": len(extracted.description_text),
        },
    )

    classifier_step = start_step(session, run, "classify_requirements", "Classify requirements and constraints")
    complete_step(
        session,
        classifier_step,
        "Requirements classified into must-have, preferred, nice-to-have, experience, and constraints.",
        {
            "must_have": len(extracted.requirements.must_have_skills),
            "preferred": len(extracted.requirements.preferred_skills),
            "nice_to_have": len(extracted.requirements.nice_to_have_skills),
            "extraction_completeness": round(extracted.requirements.extraction_completeness, 3),
            "reader_version": extracted.requirements.reader_version,
        },
    )

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
    session.flush()
    attach_subject(session, run, "job", job.id or 0)
    match_step = start_step(session, run, "match_profile_evidence", "Match profile evidence to requirements")
    try:
        match = _save_match(session, user_id, profile, job, commit=False)
    except Exception as exc:
        fail_step(session, match_step, str(exc), {"job_id": job.id or 0})
        fail_run(session, run, str(exc), "Job reader failed during evidence matching.")
        session.commit()
        raise
    complete_step(
        session,
        match_step,
        "Evidence matcher scored the role and generated resume direction.",
        {
            "score": round(match.score, 2),
            "fit_level": match.fit_level,
            "confidence": round(match.confidence, 3),
            "model_version": match.model_version,
        },
    )
    advice_step = start_step(session, run, "validate_resume_advice", "Validate resume advice is fact-constrained")
    complete_step(
        session,
        advice_step,
        "Resume advice stored from evidenced projects, skills, and about templates.",
        {"match_id": match.id or 0},
    )
    complete_run(session, run, "Job analyzed, matched, and saved.")
    session.commit()
    _catalog_for_discovery(session, user_id, job)
    return job_output(session, user_id, job.id or 0)


def _catalog_for_discovery(session: Session, user_id: UUID, job: Job) -> None:
    try:
        catalog_and_enqueue_job(session, user_id, job)
    except Exception:
        # Discovery enrichment must never make the scanner's own saved result fail.
        session.rollback()


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
    if not jobs:
        return []

    job_ids = [job.id for job in jobs if job.id is not None]
    matches = list(
        session.exec(
            select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id.in_(job_ids))
        ).all()
    )
    matches_by_job = {match.job_id: match for match in matches}

    match_ids = [match.id for match in matches_by_job.values() if match.id is not None]
    advice_by_match: dict[int, ResumeAdvice] = {}
    events_by_match: dict[int, list[JobStatusEvent]] = {match_id: [] for match_id in match_ids}
    if match_ids:
        advice = session.exec(
            select(ResumeAdvice).where(ResumeAdvice.user_id == user_id, ResumeAdvice.match_id.in_(match_ids))
        ).all()
        advice_by_match = {item.match_id: item for item in advice}
        events = session.exec(
            select(JobStatusEvent)
            .where(JobStatusEvent.user_id == user_id, JobStatusEvent.match_id.in_(match_ids))
            .order_by(JobStatusEvent.created_at)
        ).all()
        for event in events:
            events_by_match.setdefault(event.match_id, []).append(event)

    return [
        _job_to_out_from_loaded(
            job,
            matches_by_job.get(job.id or 0),
            advice_by_match,
            events_by_match,
        )
        for job in jobs
    ]


def list_job_summaries(session: Session, user_id: UUID, query: str = "", limit: int = 100) -> list[JobSummaryOut]:
    filters = [Job.user_id == user_id]
    if query.strip():
        pattern = f"%{query.strip()}%"
        filters.append(
            or_(
                Job.company.ilike(pattern),
                Job.role.ilike(pattern),
                Job.location.ilike(pattern),
                Job.source_url.ilike(pattern),
                Job.description_text.ilike(pattern),
                Job.requirements_json.ilike(pattern),
            )
        )

    statement = (
        select(
            Job.id,
            Job.source_url,
            Job.company,
            Job.role,
            Job.location,
            Job.source_confidence,
            Job.application_link,
            Job.status,
            Job.error,
            Job.created_at,
            Job.updated_at,
            Job.requirements_json,
        )
        .where(*filters)
        .order_by(Job.updated_at.desc())
        .limit(limit)
    )
    rows = list(session.exec(statement).all())
    if not rows:
        return []

    job_ids = [int(row[0]) for row in rows if row[0] is not None]
    matches = list(
        session.exec(
            select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id.in_(job_ids))
        ).all()
    )
    matches_by_job = {match.job_id: match for match in matches}

    return [_summary_from_row(row, matches_by_job.get(int(row[0]))) for row in rows]


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


def _save_match(
    session: Session,
    user_id: UUID,
    profile: Profile,
    job: Job,
    *,
    commit: bool = True,
) -> JobMatch:
    requirements = requirements_from_json(job.requirements_json)
    snapshot = candidate_snapshot(session, profile)
    result = get_match_scorer().score(
        snapshot,
        job.company,
        job.role,
        requirements,
        job.source_confidence,
    )
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
    session.flush()
    if is_new:
        session.add(JobStatusEvent(user_id=user_id, match_id=match.id or 0, status=match.status, created_at=_now()))
        session.flush()

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
    if commit:
        session.commit()
    else:
        session.flush()
    return match


def _job_to_out(session: Session, user_id: UUID, job: Job) -> JobOut:
    match = session.exec(select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job.id)).first()
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if match and profile and profile.status == "ready" and _is_after(profile.updated_at, match.analyzed_at):
        match = _save_match(session, user_id, profile, job)
    return _job_to_out_from_loaded(job, match, {}, {}, session=session, user_id=user_id)


def _summary_from_row(row, match: JobMatch | None) -> JobSummaryOut:
    (
        job_id,
        source_url,
        company,
        role,
        location,
        source_confidence,
        application_link,
        status,
        error,
        created_at,
        updated_at,
        requirements_json,
    ) = row
    requirements = requirements_from_json(requirements_json)
    top_skills = _unique_limited(
        [*requirements.must_have_skills, *requirements.preferred_skills, *requirements.nice_to_have_skills],
        7,
    )
    missing = _load_list(match.missing_blockers_json) if match else []
    gaps = _load_list(match.gaps_json) if match else []
    primary_signal = (
        missing[0]
        if missing
        else gaps[0]
        if gaps
        else error
        if status == "failed" and error
        else requirements.summary
    )
    return JobSummaryOut(
        id=int(job_id),
        source_url=source_url,
        company=company,
        role=role,
        location=location,
        source_confidence=float(source_confidence or 0),
        application_link=application_link,
        status=status,
        error=error,
        created_at=created_at,
        updated_at=updated_at,
        requirement_summary=requirements.summary,
        top_skills=top_skills,
        min_years_experience=requirements.min_years_experience,
        extraction_completeness=requirements.extraction_completeness,
        primary_signal=primary_signal,
        match=_match_summary_to_out(match) if match else None,
    )


def _job_to_out_from_loaded(
    job: Job,
    match: JobMatch | None,
    advice_by_match: dict[int, ResumeAdvice],
    events_by_match: dict[int, list[JobStatusEvent]],
    *,
    session: Session | None = None,
    user_id: UUID | None = None,
) -> JobOut:
    match_id = match.id or 0 if match else 0
    match_out = None
    agent_run_out = None
    if match:
        if session is not None and user_id is not None:
            match_out = _match_out(session, user_id, match)
        else:
            match_out = _match_to_out(
                match,
                advice_by_match.get(match_id),
                events_by_match.get(match_id, []),
            )
    if session is not None and user_id is not None and job.id is not None:
        agent_run_out = latest_agent_run_for_subject(session, user_id, "job_reader", "job", job.id)
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
        match=match_out,
        agent_run=agent_run_out,
    )


def _match_summary_to_out(match: JobMatch) -> JobMatchSummaryOut:
    return JobMatchSummaryOut(
        id=match.id or 0,
        score=match.score,
        fit_level=match.fit_level,  # type: ignore[arg-type]
        confidence=match.confidence,
        status=match.status,  # type: ignore[arg-type]
        analyzed_at=match.analyzed_at,
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
    return _match_to_out(match, advice, events)


def _match_to_out(
    match: JobMatch,
    advice: ResumeAdvice | None,
    events: list[JobStatusEvent],
) -> JobMatchOut:
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


def _unique_limited(values: list[str], limit: int) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split())
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
        if len(output) >= limit:
            break
    return output


def _now() -> datetime:
    return datetime.now(timezone.utc)
