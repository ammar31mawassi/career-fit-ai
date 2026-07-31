from __future__ import annotations

import hashlib
import json
import logging
import time
import base64
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import (
    AgentRun,
    AgentStep,
    Job,
    JobMatch,
    JobRequirementRevision,
    JobStatusEvent,
    Profile,
    ResumeAdvice,
)
from ..schemas import (
    JobCreateIn,
    JobMatchOut,
    JobMatchSummaryOut,
    JobOut,
    JobStatusEventOut,
    JobSummaryOut,
    JobSummaryPageOut,
    JobRequirementsReviewIn,
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
from .advice_quality import OUTPUT_POLICY_VERSION, enforce_resume_advice
from .about_templates import TEMPLATE_VERSION
from .job_research import (
    JOB_READER_VERSION,
    extract_job_from_input,
    requirements_from_json,
    validate_pasted_job_description,
)
from .matcher import MODEL_VERSION
from .profile import (
    MATCHABLE_PROFILE_REQUIRED,
    candidate_snapshot,
    get_or_create_profile,
    profile_is_matchable,
)
from .recommendations import catalog_and_enqueue_job, record_recommendation_application
from .scoring import get_match_scorer
from .telemetry import current_trace_id, record_evaluation_example, record_extraction_metric, safe_error_code


ProgressCallback = Callable[[str, int], None]
logger = logging.getLogger("careerfit.jobs")


def create_or_analyze_job(
    session: Session,
    user_id: UUID,
    payload: JobCreateIn,
    progress_callback: ProgressCallback | None = None,
) -> JobOut:
    _report_progress(progress_callback, "validate_profile", 5)
    profile = get_or_create_profile(session, user_id)
    if not profile_is_matchable(session, profile):
        raise ValueError(MATCHABLE_PROFILE_REQUIRED)
    if payload.description_text.strip():
        validate_pasted_job_description(payload.description_text)

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
    _report_progress(progress_callback, "dedupe_lookup", 12)
    existing = session.exec(
        select(Job).where(Job.user_id == user_id, Job.content_hash == content_hash)
    ).first()
    if existing and _can_reuse(session, user_id, existing, payload):
        extraction_provenance = _latest_extraction_provenance(
            session,
            user_id,
            existing.id or 0,
            fallback_reader_version=requirements_from_json(
                existing.requirements_json
            ).reader_version,
        )
        attach_subject(session, run, "job", existing.id or 0)
        complete_step(
            session,
            dedupe_step,
            "Existing job analysis reused; no rescan needed.",
            {"job_id": existing.id or 0, "reader_version": JOB_READER_VERSION},
        )
        reuse_extraction_step = start_step(
            session,
            run,
            "extract_job",
            "Reuse stored job extraction",
        )
        complete_step(
            session,
            reuse_extraction_step,
            "Stored extraction provenance reused; no remote page was fetched.",
            extraction_provenance,
        )
        complete_run(session, run, "Existing saved job reused.", status="reused")
        session.commit()
        _catalog_for_discovery(
            session,
            user_id,
            existing,
            consented=payload.contribute_public_posting,
        )
        _report_progress(progress_callback, "ready", 100)
        return job_output(session, user_id, existing.id or 0)
    complete_step(
        session,
        dedupe_step,
        "No reusable analysis found; scanning the submitted source.",
        {"had_existing_job": bool(existing)},
    )

    extraction_step = start_step(session, run, "extract_job", "Extract job content and source metadata")
    extraction_started = time.perf_counter()
    _report_progress(progress_callback, "extract_job", 26)
    try:
        extracted = extract_job_from_input(
            payload.source_url,
            payload.company,
            payload.role,
            payload.description_text,
        )
    except Exception as exc:
        error_code = safe_error_code("JOB_READ", exc)
        fallback_provenance = (
            _latest_extraction_provenance(
                session,
                user_id,
                existing.id or 0,
                fallback_reader_version=requirements_from_json(
                    existing.requirements_json
                ).reader_version,
            )
            if existing and existing.status == "analyzed"
            else {}
        )
        logger.exception(
            "job_extraction_failed trace_id=%s error_code=%s",
            current_trace_id(),
            error_code,
        )
        fail_step(
            session,
            extraction_step,
            error_code,
            {
                "has_source_url": bool(payload.source_url.strip()),
                **fallback_provenance,
                **(
                    {"provenance_origin": "stored_fallback"}
                    if fallback_provenance
                    else {}
                ),
            },
        )
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
        job.error = "CareerFit could not read enough job information. Check the URL or paste the full public description."
        job.updated_at = _now()
        session.add(job)
        session.flush()
        record_extraction_metric(
            session,
            user_id,
            workflow_type="job_extraction",
            subject_type="job",
            subject_id=job.id,
            strategy="url" if payload.source_url.strip() else "pasted",
            status="failed",
            duration_ms=round((time.perf_counter() - extraction_started) * 1000),
            input_length=len(payload.description_text),
            error_code=error_code,
        )
        session.commit()
        session.refresh(job)
        attach_subject(session, run, "job", job.id or 0)
        fail_run(session, run, error_code, "Job reader failed during extraction.")
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
            "reader_strategy": extracted.reader_strategy,
            "reader_version": extracted.requirements.reader_version,
        },
    )
    _report_progress(progress_callback, "classify_requirements", 55)

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
    record_extraction_metric(
        session,
        user_id,
        workflow_type="job_extraction",
        subject_type="job",
        subject_id=job.id,
        strategy=extracted.reader_strategy,
        duration_ms=round((time.perf_counter() - extraction_started) * 1000),
        input_length=len(payload.description_text),
        output_length=len(extracted.description_text),
        counts={
            "must_have": len(extracted.requirements.must_have_skills),
            "preferred": len(extracted.requirements.preferred_skills),
            "nice_to_have": len(extracted.requirements.nice_to_have_skills),
            "responsibilities": len(extracted.requirements.responsibilities),
        },
    )
    attach_subject(session, run, "job", job.id or 0)
    match_step = start_step(session, run, "match_profile_evidence", "Match profile evidence to requirements")
    _report_progress(progress_callback, "match_profile_evidence", 74)
    try:
        match = save_match(session, user_id, profile, job, commit=False)
    except Exception as exc:
        error_code = safe_error_code("JOB_MATCH", exc)
        logger.exception(
            "job_matching_failed trace_id=%s error_code=%s job_id=%s",
            current_trace_id(),
            error_code,
            job.id or 0,
        )
        fail_step(session, match_step, error_code, {"job_id": job.id or 0})
        fail_run(session, run, error_code, "Job reader failed during evidence matching.")
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
    _report_progress(progress_callback, "validate_resume_advice", 91)
    complete_step(
        session,
        advice_step,
        "Resume advice passed the evidence and clarity postcondition.",
        {
            "match_id": match.id or 0,
            **_resume_advice_quality_snapshot(match.feature_snapshot_json),
        },
    )
    complete_run(session, run, "Job analyzed, matched, and saved.")
    session.commit()
    _catalog_for_discovery(
        session,
        user_id,
        job,
        consented=payload.contribute_public_posting,
    )
    _report_progress(progress_callback, "ready", 100)
    return job_output(session, user_id, job.id or 0)


def _catalog_for_discovery(
    session: Session,
    user_id: UUID,
    job: Job,
    *,
    consented: bool,
) -> None:
    if not consented:
        return
    try:
        catalog_and_enqueue_job(session, user_id, job)
    except Exception:
        # Discovery enrichment must never make the scanner's own saved result fail.
        session.rollback()


def _can_reuse(session: Session, user_id: UUID, job: Job, payload: JobCreateIn) -> bool:
    if job.status != "analyzed":
        return False
    requirements = requirements_from_json(job.requirements_json)
    if requirements.reader_version != JOB_READER_VERSION:
        return False
    pasted = " ".join(payload.description_text.lower().split())
    stored = " ".join(job.description_text.lower().split())
    if pasted and pasted != stored:
        return False
    match = session.exec(
        select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job.id)
    ).first()
    if match is None:
        return False
    snapshot = _load_json_object(match.feature_snapshot_json)
    quality = snapshot.get("resume_advice_quality")
    template = snapshot.get("resume_advice_template")
    return bool(
        isinstance(quality, dict)
        and quality.get("policy_version") == OUTPUT_POLICY_VERSION
        and quality.get("passed") is True
        and isinstance(template, dict)
        and template.get("version") == TEMPLATE_VERSION
    )


def list_jobs(session: Session, user_id: UUID, query: str = "", limit: int = 100) -> list[JobOut]:
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
            )
        )
    statement = select(Job).where(*filters).order_by(Job.updated_at.desc()).limit(limit)
    jobs = list(session.exec(statement).all())
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
            .order_by(JobStatusEvent.id)
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


def list_job_summary_page(
    session: Session,
    user_id: UUID,
    *,
    query: str = "",
    limit: int = 30,
    cursor: str = "",
    watermark: datetime | None = None,
) -> JobSummaryPageOut:
    filters = [Job.user_id == user_id]
    if watermark is not None:
        filters.append(Job.updated_at <= watermark)
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
    decoded = _decode_cursor(cursor)
    if decoded is not None:
        cursor_time, cursor_id = decoded
        filters.append(
            or_(
                Job.updated_at < cursor_time,
                and_(Job.updated_at == cursor_time, Job.id < cursor_id),
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
        .order_by(Job.updated_at.desc(), Job.id.desc())
        .limit(limit + 1)
    )
    rows = list(session.exec(statement).all())
    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    if not visible_rows:
        return JobSummaryPageOut(watermark=watermark)
    job_ids = [int(row[0]) for row in visible_rows if row[0] is not None]
    matches = list(
        session.exec(
            select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id.in_(job_ids))
        ).all()
    )
    matches_by_job = {match.job_id: match for match in matches}
    items = [_summary_from_row(row, matches_by_job.get(int(row[0]))) for row in visible_rows]
    last = visible_rows[-1]
    next_cursor = _encode_cursor(last[10], int(last[0])) if has_more else None
    return JobSummaryPageOut(
        items=items,
        next_cursor=next_cursor,
        watermark=watermark or visible_rows[0][10],
    )


def job_output(session: Session, user_id: UUID, job_id: int) -> JobOut:
    job = session.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise ValueError("Job not found.")
    return _job_to_out(session, user_id, job)


def update_job_status(
    session: Session,
    user_id: UUID,
    job_id: int,
    status: str,
    *,
    occurred_at: datetime | None = None,
    note: str = "",
    source: str = "user",
) -> JobOut:
    job = session.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise ValueError("Job not found.")
    match = session.exec(
        select(JobMatch)
        .where(JobMatch.user_id == user_id, JobMatch.job_id == job_id)
        .with_for_update()
    ).first()
    if not match:
        profile = get_or_create_profile(session, user_id)
        save_match(session, user_id, profile, job)
        # save_match commits its insert/race recovery path. Reacquire the row
        # lock so a first transition cannot race another first transition.
        match = session.exec(
            select(JobMatch)
            .where(JobMatch.user_id == user_id, JobMatch.job_id == job_id)
            .with_for_update()
        ).one()
    previous_status = match.status
    if previous_status == status:
        # Release the row lock without changing updated_at or validating metadata
        # for an event that will not be written.
        session.commit()
        return job_output(session, user_id, job_id)
    event_time = _status_event_time(occurred_at)
    clean_note = _status_note(note)
    if source not in {"system", "user", "correction", "backfill", "legacy"}:
        raise ValueError("Invalid application stage event source.")
    match.status = status
    match.updated_at = _now()
    session.add(match)
    session.add(
        JobStatusEvent(
            user_id=user_id,
            match_id=match.id or 0,
            previous_status=previous_status,
            status=status,
            occurred_at=event_time,
            source=source,
            note=clean_note,
            created_at=_now(),
        )
    )
    if status == "Applied":
        record_recommendation_application(session, user_id, job_id)
    session.commit()
    return job_output(session, user_id, job_id)


def rematch_job(session: Session, user_id: UUID, job_id: int) -> JobOut:
    job = session.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise ValueError("Job not found.")
    profile = get_or_create_profile(session, user_id)
    if not profile_is_matchable(session, profile):
        raise ValueError(MATCHABLE_PROFILE_REQUIRED)
    save_match(session, user_id, profile, job)
    return job_output(session, user_id, job_id)


def review_job_requirements(
    session: Session,
    user_id: UUID,
    job_id: int,
    payload: JobRequirementsReviewIn,
) -> JobOut:
    job = session.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise ValueError("Job not found.")
    original = requirements_from_json(job.requirements_json)
    corrected = replace(
        original,
        must_have_skills=payload.must_have_skills,
        preferred_skills=payload.preferred_skills,
        nice_to_have_skills=payload.nice_to_have_skills,
        all_skills=_unique_limited(
            [*payload.must_have_skills, *payload.preferred_skills, *payload.nice_to_have_skills],
            100,
        ),
        min_years_experience=payload.min_years_experience,
        experience_requirement_known=payload.experience_requirement_known,
        seniority=payload.seniority.strip().lower() or "unspecified",
        education=payload.education.strip(),
        work_mode=payload.work_mode.strip(),
        domain=payload.domain.strip(),
        location_requirement=payload.location_requirement.strip(),
        summary=_reviewed_requirement_summary(payload),
        skill_groups=[],
        reader_version=f"{original.reader_version}+user-reviewed",
        extraction_completeness=1.0,
    )
    changed_fields = [
        name
        for name in (
            "must_have_skills",
            "preferred_skills",
            "nice_to_have_skills",
            "min_years_experience",
            "experience_requirement_known",
            "seniority",
            "education",
            "work_mode",
            "domain",
            "location_requirement",
        )
        if getattr(original, name) != getattr(corrected, name)
    ]
    if not changed_fields:
        return job_output(session, user_id, job_id)
    job.requirements_json = corrected.to_json()
    job.updated_at = _now()
    session.add(job)
    revision = JobRequirementRevision(
        user_id=user_id,
        job_id=job_id,
        original_requirements_json=original.to_json(),
        corrected_requirements_json=corrected.to_json(),
        changed_fields_json=json.dumps(changed_fields),
        matcher_version=MODEL_VERSION,
    )
    session.add(revision)
    session.flush()
    record_evaluation_example(
        session,
        user_id,
        example_type="job_requirement_review",
        subject_id=revision.id,
        label="corrected",
        model_version=original.reader_version,
        features={
            "changed_fields": changed_fields,
            "original_completeness": round(original.extraction_completeness, 3),
            "source_confidence": round(job.source_confidence, 3),
            "original_skill_counts": {
                "must": len(original.must_have_skills),
                "preferred": len(original.preferred_skills),
                "nice": len(original.nice_to_have_skills),
            },
            "corrected_skill_counts": {
                "must": len(corrected.must_have_skills),
                "preferred": len(corrected.preferred_skills),
                "nice": len(corrected.nice_to_have_skills),
            },
        },
    )
    profile = get_or_create_profile(session, user_id)
    save_match(session, user_id, profile, job, commit=False)
    session.commit()
    return job_output(session, user_id, job_id)


def save_match(
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
    checked_advice = enforce_resume_advice(
        snapshot,
        job.role,
        requirements,
        projects=result.projects,
        skill_order=result.skill_order,
        about_text=result.about_text,
        evidence=result.about_evidence,
    )
    feature_snapshot = dict(result.feature_snapshot)
    feature_snapshot["resume_advice_template"] = {
        "id": result.about_template_id,
        "version": TEMPLATE_VERSION,
    }
    feature_snapshot["resume_advice_quality"] = checked_advice.report.public_dict()
    result = replace(
        result,
        projects=checked_advice.projects,
        skill_order=checked_advice.skill_order,
        about_text=checked_advice.about_text,
        about_evidence=checked_advice.evidence,
        feature_snapshot=feature_snapshot,
    )
    now = _now()
    match_values = {
        "score": result.score,
        "fit_level": result.fit_level,
        "confidence": result.confidence,
        "matched_evidence_json": json.dumps(result.matched_evidence),
        "missing_blockers_json": json.dumps(result.missing_blockers),
        "gaps_json": json.dumps(result.gaps),
        "model_version": result.model_version,
        "ontology_version": result.ontology_version,
        "component_scores_json": json.dumps(result.component_scores, sort_keys=True),
        "applied_caps_json": json.dumps(result.applied_caps),
        "feature_snapshot_json": json.dumps(result.feature_snapshot, sort_keys=True),
        "analyzed_at": now,
        "updated_at": now,
    }
    advice_values = {
        "projects_json": json.dumps(result.projects),
        "skill_order_json": json.dumps(result.skill_order),
        "about_text": result.about_text,
        "template_id": result.about_template_id,
        "evidence_json": json.dumps(result.about_evidence),
        "generated_at": now,
    }
    try:
        match = session.exec(
            select(JobMatch).where(
                JobMatch.user_id == user_id,
                JobMatch.job_id == job.id,
            )
        ).first()
        inserted_match = False
        if match is None:
            candidate_match = JobMatch(
                user_id=user_id,
                job_id=job.id or 0,
                **match_values,
            )
            try:
                with session.begin_nested():
                    session.add(candidate_match)
                    session.flush()
            except IntegrityError:
                match = session.exec(
                    select(JobMatch).where(
                        JobMatch.user_id == user_id,
                        JobMatch.job_id == job.id,
                    )
                ).one()
            else:
                match = candidate_match
                inserted_match = True
        if not inserted_match:
            if match is None:
                raise RuntimeError("Job match upsert did not return a row.")
            # Never touch `status`: a concurrent application transition is a
            # user decision and must win over a background rematch.
            for key, value in match_values.items():
                setattr(match, key, value)
            session.add(match)
            session.flush()
        if inserted_match:
            session.add(
                JobStatusEvent(
                    user_id=user_id,
                    match_id=match.id or 0,
                    previous_status="",
                    status=match.status,
                    occurred_at=now,
                    source="system",
                    note="",
                    created_at=now,
                )
            )
            session.flush()

        advice = session.exec(
            select(ResumeAdvice).where(
                ResumeAdvice.user_id == user_id,
                ResumeAdvice.match_id == match.id,
            )
        ).first()
        inserted_advice = False
        if advice is None:
            candidate_advice = ResumeAdvice(
                user_id=user_id,
                match_id=match.id or 0,
                **advice_values,
            )
            try:
                with session.begin_nested():
                    session.add(candidate_advice)
                    session.flush()
            except IntegrityError:
                advice = session.exec(
                    select(ResumeAdvice).where(
                        ResumeAdvice.user_id == user_id,
                        ResumeAdvice.match_id == match.id,
                    )
                ).one()
            else:
                advice = candidate_advice
                inserted_advice = True
        if not inserted_advice:
            if advice is None:
                raise RuntimeError("Resume advice upsert did not return a row.")
            for key, value in advice_values.items():
                setattr(advice, key, value)
            session.add(advice)
            session.flush()
        if commit:
            session.commit()
        else:
            session.flush()
        return match
    except Exception:
        # Keep both direct calls and larger caller-owned units of work atomic.
        # For commit=False this intentionally rolls back the caller's pending
        # job/recommendation transition as one failed unit.
        session.rollback()
        raise


def _job_to_out(session: Session, user_id: UUID, job: Job) -> JobOut:
    match = session.exec(select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job.id)).first()
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


def _reviewed_requirement_summary(payload: JobRequirementsReviewIn) -> str:
    parts: list[str] = []
    if payload.must_have_skills:
        parts.append(f"Must have: {', '.join(payload.must_have_skills[:5])}")
    if payload.preferred_skills:
        parts.append(f"Preferred: {', '.join(payload.preferred_skills[:4])}")
    if payload.experience_requirement_known:
        parts.append(f"Experience: {payload.min_years_experience:g}+ years")
    if payload.seniority and payload.seniority != "unspecified":
        parts.append(f"Seniority: {payload.seniority}")
    return ". ".join(parts) or "Requirements reviewed by the user."


def _report_progress(callback: ProgressCallback | None, step: str, progress: int) -> None:
    if callback is not None:
        callback(step, max(0, min(100, progress)))


def _encode_cursor(updated_at: datetime, job_id: int) -> str:
    raw = f"{updated_at.isoformat()}|{job_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, int] | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        timestamp, raw_id = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8").rsplit("|", 1)
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed, int(raw_id)
    except (ValueError, TypeError, UnicodeDecodeError):
        raise ValueError("Invalid job page cursor.") from None


def _match_out(session: Session, user_id: UUID, match: JobMatch) -> JobMatchOut:
    advice = session.exec(
        select(ResumeAdvice).where(ResumeAdvice.user_id == user_id, ResumeAdvice.match_id == match.id)
    ).first()
    events = list(
        session.exec(
            select(JobStatusEvent)
            .where(JobStatusEvent.user_id == user_id, JobStatusEvent.match_id == match.id)
            .order_by(JobStatusEvent.id)
        ).all()
    )
    return _match_to_out(match, advice, events)


def _match_to_out(
    match: JobMatch,
    advice: ResumeAdvice | None,
    events: list[JobStatusEvent],
) -> JobMatchOut:
    snapshot = _load_json_object(match.feature_snapshot_json)
    quality = snapshot.get("resume_advice_quality")
    template = snapshot.get("resume_advice_template")
    quality = quality if isinstance(quality, dict) else {}
    template = template if isinstance(template, dict) else {}
    raw_findings = quality.get("findings")
    findings = raw_findings if isinstance(raw_findings, list) else []
    quality_current = bool(
        quality.get("passed") is True
        and quality.get("policy_version") == OUTPUT_POLICY_VERSION
        and template.get("version") == TEMPLATE_VERSION
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
            JobStatusEventOut(
                previous_status=(event.previous_status or None),  # type: ignore[arg-type]
                status=event.status,  # type: ignore[arg-type]
                occurred_at=event.occurred_at,
                source=event.source,  # type: ignore[arg-type]
                note=event.note,
                created_at=event.created_at,
            )
            for event in events
        ],
        resume_advice=ResumeAdviceOut(
            projects=_load_list(advice.projects_json) if advice else [],
            skill_order=_load_list(advice.skill_order_json) if advice else [],
            about_text=advice.about_text if advice else "",
            template_id=advice.template_id if advice else "",
            evidence=_load_list(advice.evidence_json) if advice else [],
            template_version=str(template.get("version") or ""),
            quality_policy_version=str(quality.get("policy_version") or ""),
            quality_checked=quality_current,
            quality_repaired=bool(quality.get("repaired")),
            quality_findings=[
                item
                for item in findings
                if isinstance(item, dict)
                and isinstance(item.get("code"), str)
                and item.get("severity") in {"error", "warning"}
                and isinstance(item.get("message"), str)
            ],
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


def _status_event_time(value: datetime | None) -> datetime:
    now = _now()
    if value is None:
        return now
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Application stage date must include a timezone.")
    normalized = value.astimezone(timezone.utc)
    if normalized > now + timedelta(minutes=5):
        raise ValueError("Application stage date cannot be in the future.")
    return normalized


def _status_note(value: str) -> str:
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise ValueError("Application stage note contains a control character.")
    cleaned = " ".join(value.split())
    if len(cleaned) > 500:
        raise ValueError("Application stage note must be 500 characters or fewer.")
    return cleaned


def _latest_extraction_provenance(
    session: Session,
    user_id: UUID,
    job_id: int,
    *,
    fallback_reader_version: str,
) -> dict[str, object]:
    step = session.exec(
        select(AgentStep)
        .join(AgentRun, AgentRun.id == AgentStep.run_id)
        .where(
            AgentRun.user_id == user_id,
            AgentRun.workflow_type == "job_reader",
            AgentRun.subject_type == "job",
            AgentRun.subject_id == job_id,
            AgentStep.user_id == user_id,
            AgentStep.step_key == "extract_job",
            AgentStep.status == "completed",
        )
        .order_by(AgentRun.id.desc(), AgentStep.id.desc())
    ).first()
    stored = _load_json_object(step.output_json) if step is not None else {}
    output: dict[str, object] = {}
    strategy = stored.get("reader_strategy")
    version = stored.get("reader_version")
    if isinstance(strategy, str) and strategy:
        output["reader_strategy"] = strategy
    output["reader_version"] = (
        version if isinstance(version, str) and version else fallback_reader_version
    )
    return output


def _resume_advice_quality_snapshot(value: str) -> dict[str, object]:
    snapshot = _load_json_object(value)
    quality = snapshot.get("resume_advice_quality")
    if not isinstance(quality, dict):
        return {
            "policy_version": "",
            "template_version": "",
            "evidence_count": 0,
            "hard_error_count": 1,
            "warning_codes": ["missing_quality_metadata"],
        }
    template = snapshot.get("resume_advice_template")
    return {
        "policy_version": str(quality.get("policy_version") or ""),
        "template_version": (
            str(template.get("version") or "") if isinstance(template, dict) else ""
        ),
        "evidence_count": int(quality.get("evidence_count") or 0),
        "hard_error_count": int(quality.get("hard_error_count") or 0),
        "warning_codes": (
            quality.get("warning_codes") if isinstance(quality.get("warning_codes"), list) else []
        ),
        "repaired": bool(quality.get("repaired")),
    }


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


def _load_json_object(value: str) -> dict[str, object]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
