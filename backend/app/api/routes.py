from __future__ import annotations

import secrets
import hashlib
import logging
import time
from datetime import datetime
from html import escape as html_escape
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from starlette.responses import HTMLResponse, JSONResponse
from sqlmodel import Session
from uuid import UUID

from ..config import get_settings
from ..database import get_session
from ..schemas import (
    AccountDeleteIn,
    AccountExportOut,
    BrowserOcrIn,
    ClarificationAnswerIn,
    JobCreateIn,
    JobOut,
    JobRecommendationActionOut,
    JobRecommendationEventIn,
    JobRecommendationOut,
    JobRecommendationPatchIn,
    JobSummaryPageOut,
    JobRequirementsReviewIn,
    JobScanOut,
    JobStatusPatchIn,
    JobSummaryOut,
    OnboardingAnalyzeIn,
    OnboardingCompleteIn,
    NotificationPreferenceIn,
    NotificationPreferenceOut,
    ProfileAnalyzeResult,
    ProfileFactBulkReviewIn,
    ProfileFactCreateIn,
    ProfileFactPatchIn,
    ProfileOut,
    ProfilePreferencesIn,
    ProfileSourcesIn,
    WorkspaceBootstrapOut,
)
from ..services.account import delete_account, export_account
from ..services.auth import current_user_id
from ..services.job_scans import (
    cancel_job_scan,
    create_job_scan,
    latest_active_scan,
    process_one_queued_scan,
    process_user_scan,
    scan_output,
)
from ..services.jobs import (
    create_or_analyze_job,
    job_output,
    list_job_summaries,
    list_job_summary_page,
    list_jobs,
    rematch_job,
    review_job_requirements,
    update_job_status,
)
from ..services.onboarding import analyze_onboarding_profile, cleanup_abandoned_onboarding
from ..services.profile import (
    apply_browser_ocr,
    analyze_profile,
    add_fact,
    answer_question,
    complete_onboarding,
    patch_fact,
    patch_facts_bulk,
    profile_output,
    update_profile_sources,
    update_profile_preferences,
    upload_cv_source,
    upload_linkedin_pdf_source,
)
from ..services.recommendations import (
    list_recommendations,
    process_one_queued_recommendation,
    record_recommendation_view,
    refresh_user_recommendations,
    update_recommendation,
)
from ..services.notifications import (
    get_notification_preference,
    process_one_queued_email,
    unsubscribe_email,
    update_notification_preference,
)
from ..services.job_discovery import run_goozali_discovery


router = APIRouter(prefix="/api")
logger = logging.getLogger("careerfit.api")
UPLOAD_READ_CHUNK_BYTES = 64 * 1024
PDF_UPLOAD_CONTENT_TYPES = frozenset({"application/pdf", "application/octet-stream"})


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness(session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        session.exec(text("select 1")).one()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database readiness check failed.",
        ) from exc
    return {"status": "ready"}


@router.get("/account/export", response_model=AccountExportOut)
def download_account_export(
    response: Response,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> AccountExportOut:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Disposition"] = 'attachment; filename="careerfit-export.json"'
    return export_account(session, user_id)


@router.delete("/account", status_code=204)
def remove_account(
    payload: AccountDeleteIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> Response:
    del payload
    try:
        delete_account(session, user_id)
    except RuntimeError as exc:
        logger.exception("account_deletion_failed user_id=%s", user_id)
        raise HTTPException(
            status_code=503,
            detail="Account deletion could not be completed. Try again.",
        ) from exc
    return Response(status_code=204)


@router.get("/workspace/bootstrap", response_model=WorkspaceBootstrapOut)
def workspace_bootstrap(
    limit: int = Query(default=50, ge=1, le=100),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> WorkspaceBootstrapOut:
    page = list_job_summary_page(session, user_id, limit=limit)
    return WorkspaceBootstrapOut(
        user_id=str(user_id),
        profile=profile_output(session, user_id),
        jobs=page.items,
        jobs_next_cursor=page.next_cursor,
        jobs_watermark=page.watermark,
    )


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    return profile_output(session, user_id)


@router.post("/profile/cv", response_model=ProfileOut)
def upload_cv(
    file: UploadFile = File(...),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    filename, data = _read_pdf_upload(file, default_filename="cv.pdf")
    try:
        return upload_cv_source(session, user_id, filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/profile/cv/browser-ocr", response_model=ProfileOut)
def save_browser_ocr(
    payload: BrowserOcrIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    try:
        return apply_browser_ocr(session, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/profile/linkedin-pdf", response_model=ProfileOut)
def upload_linkedin_pdf(
    file: UploadFile = File(...),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    filename, data = _read_pdf_upload(file, default_filename="linkedin.pdf")
    try:
        return upload_linkedin_pdf_source(session, user_id, filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _read_pdf_upload(file: UploadFile, *, default_filename: str) -> tuple[str, bytes]:
    """Read at most the configured limit plus one byte inside FastAPI's sync worker pool."""
    filename = file.filename or default_filename
    if file.content_type not in PDF_UPLOAD_CONTENT_TYPES or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Upload a PDF document.")

    limit = get_settings().max_upload_bytes
    buffered = bytearray()
    while len(buffered) <= limit:
        remaining = limit + 1 - len(buffered)
        chunk = file.file.read(min(UPLOAD_READ_CHUNK_BYTES, remaining))
        if not chunk:
            break
        buffered.extend(chunk)

    if not buffered:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
    if len(buffered) > limit:
        raise HTTPException(status_code=413, detail="Uploaded PDF is too large.")
    data = bytes(buffered)
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Uploaded file does not contain a valid PDF header.")
    return filename, data


@router.put("/profile/sources", response_model=ProfileOut)
def save_sources(
    payload: ProfileSourcesIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    return update_profile_sources(session, user_id, payload)


@router.put("/profile/preferences", response_model=ProfileOut)
def save_preferences(
    payload: ProfilePreferencesIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    return update_profile_preferences(session, user_id, payload)


@router.post("/profile/onboarding/complete", response_model=ProfileOut)
def finish_onboarding(
    payload: OnboardingCompleteIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    try:
        return complete_onboarding(session, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/profile/onboarding/analyze", response_model=ProfileAnalyzeResult)
def analyze_onboarding(
    payload: OnboardingAnalyzeIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileAnalyzeResult:
    return analyze_onboarding_profile(session, user_id, payload)


@router.post("/profile/analyze", response_model=ProfileAnalyzeResult)
def analyze(
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileAnalyzeResult:
    return analyze_profile(session, user_id)


@router.patch("/profile/facts/{fact_id}", response_model=ProfileOut)
def update_fact(
    fact_id: int,
    payload: ProfileFactPatchIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    try:
        return patch_fact(session, user_id, fact_id, payload.value, payload.review_status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/profile/facts", response_model=ProfileOut)
def bulk_update_facts(
    payload: ProfileFactBulkReviewIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    try:
        return patch_facts_bulk(session, user_id, payload.fact_ids, payload.review_status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/profile/facts", response_model=ProfileOut)
def create_fact(
    payload: ProfileFactCreateIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    return add_fact(session, user_id, payload.fact_type, payload.value)


@router.patch("/profile/questions/{question_id}", response_model=ProfileOut)
def update_question(
    question_id: int,
    payload: ClarificationAnswerIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    try:
        return answer_question(session, user_id, question_id, payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs", response_model=JobOut)
def create_job(
    payload: JobCreateIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobOut:
    try:
        return create_or_analyze_job(session, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/job-scans", response_model=JobScanOut, status_code=202)
def queue_job_scan(
    payload: JobCreateIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobScanOut:
    try:
        return create_job_scan(session, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/job-scans/active", response_model=JobScanOut | None)
def active_job_scan(
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobScanOut | None:
    return latest_active_scan(session, user_id)


@router.get("/job-scans/{scan_id}", response_model=JobScanOut)
def job_scan_status(
    scan_id: int,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobScanOut:
    try:
        return scan_output(session, user_id, scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/job-scans/{scan_id}/process", response_model=JobScanOut)
def process_job_scan(
    scan_id: int,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobScanOut:
    try:
        return process_user_scan(session, user_id, scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/job-scans/{scan_id}", response_model=JobScanOut)
def cancel_scan(
    scan_id: int,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobScanOut:
    try:
        return cancel_job_scan(session, user_id, scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/recommendations", response_model=list[JobRecommendationOut])
def recommendations(
    limit: int = Query(default=12, ge=1, le=30),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> list[JobRecommendationOut]:
    return list_recommendations(session, user_id, limit)


@router.post("/recommendations/refresh", response_model=list[JobRecommendationOut])
def refresh_recommendations(
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> list[JobRecommendationOut]:
    return refresh_user_recommendations(session, user_id)


@router.patch("/recommendations/{recommendation_id}", response_model=JobRecommendationActionOut)
def patch_recommendation(
    recommendation_id: int,
    payload: JobRecommendationPatchIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobRecommendationActionOut:
    try:
        recommendation, job = update_recommendation(
            session,
            user_id,
            recommendation_id,
            payload.status,
            dismiss_reason=payload.dismiss_reason,
        )
        return JobRecommendationActionOut(recommendation=recommendation, job=job)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/recommendations/{recommendation_id}/events", status_code=204)
def create_recommendation_event(
    recommendation_id: int,
    payload: JobRecommendationEventIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> Response:
    try:
        if payload.event_type == "viewed":
            record_recommendation_view(session, user_id, recommendation_id)
        return Response(status_code=204)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[JobOut])
def jobs(
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=250),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> list[JobOut]:
    return list_jobs(session, user_id, query=query, limit=limit)


@router.get("/jobs/summary", response_model=list[JobSummaryOut])
def job_summaries(
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=250),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> list[JobSummaryOut]:
    return list_job_summaries(session, user_id, query=query, limit=limit)


@router.get("/jobs/summary-page", response_model=None)
def job_summary_page(
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=30, ge=1, le=100),
    cursor: str = Query(default="", max_length=500),
    watermark: datetime | None = Query(default=None),
    if_none_match: str = Header(default="", alias="If-None-Match"),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    try:
        page = list_job_summary_page(
            session,
            user_id,
            query=query,
            limit=limit,
            cursor=cursor,
            watermark=watermark,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    page_response = JSONResponse(content=jsonable_encoder(page))
    etag = f'"{hashlib.sha256(page_response.body).hexdigest()[:24]}"'
    if if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    page_response.headers["ETag"] = etag
    return page_response


@router.get("/notifications/preferences", response_model=NotificationPreferenceOut)
def notification_preferences(
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> NotificationPreferenceOut:
    return get_notification_preference(session, user_id)


@router.put("/notifications/preferences", response_model=NotificationPreferenceOut)
def put_notification_preferences(
    payload: NotificationPreferenceIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> NotificationPreferenceOut:
    try:
        return update_notification_preference(session, user_id, payload.email_enabled)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/notifications/unsubscribe", response_class=HTMLResponse)
def unsubscribe_confirmation(token: str = Query(min_length=20, max_length=300)) -> HTMLResponse:
    safe_token = html_escape(token)
    return HTMLResponse(
        "<!doctype html><html><body style='font-family:system-ui;max-width:560px;margin:64px auto;padding:24px'>"
        "<h1>Stop CareerFit job emails?</h1><p>In-app job suggestions will remain available.</p>"
        f"<form method='post'><input type='hidden' name='token' value='{safe_token}'>"
        "<button type='submit' style='padding:12px 18px'>Stop job emails</button></form></body></html>"
    )


@router.post("/notifications/unsubscribe", response_class=HTMLResponse)
def unsubscribe_notification_email(
    token: str = Query(min_length=20, max_length=300),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if not unsubscribe_email(session, token):
        return HTMLResponse("<h1>This unsubscribe link is invalid.</h1>", status_code=400)
    return HTMLResponse("<h1>Job emails are off.</h1><p>In-app recommendations remain available.</p>")


@router.get("/jobs/{job_id}", response_model=JobOut)
def job_detail(
    job_id: int,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobOut:
    try:
        return job_output(session, user_id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/jobs/{job_id}/status", response_model=JobOut)
def patch_job_status(
    job_id: int,
    payload: JobStatusPatchIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobOut:
    try:
        return update_job_status(
            session,
            user_id,
            job_id,
            payload.status,
            occurred_at=payload.occurred_at,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/rematch", response_model=JobOut)
def refresh_job_match(
    job_id: int,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobOut:
    try:
        return rematch_job(session, user_id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/jobs/{job_id}/requirements", response_model=JobOut)
def update_job_requirements(
    job_id: int,
    payload: JobRequirementsReviewIn,
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> JobOut:
    try:
        return review_job_requirements(session, user_id, job_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.api_route("/workers/process", methods=["GET", "POST"])
def process_background_work(
    authorization: str = Header(default=""),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    _authorize_worker(authorization)
    deadline = time.monotonic() + 50
    scans_processed = 0
    for _ in range(5):
        if time.monotonic() >= deadline:
            break
        scan = process_one_queued_scan(session)
        if scan is not None and scan.status in {"succeeded", "failed", "cancelled"}:
            scans_processed += 1
    onboarding_cleanups = (
        cleanup_abandoned_onboarding(session)
        if time.monotonic() < deadline
        else 0
    )
    recommendation = (
        process_one_queued_recommendation(session)
        if time.monotonic() < deadline
        else None
    )
    email = process_one_queued_email(session) if time.monotonic() < deadline else None
    return {
        "scans_processed": scans_processed,
        "recommendations_processed": int(recommendation is not None),
        "emails_processed": int(email is not None),
        "onboarding_cleanups": onboarding_cleanups,
    }


@router.api_route("/workers/discover", methods=["GET", "POST"])
def process_discovery_work(
    authorization: str = Header(default=""),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _authorize_worker(authorization)
    deadline = time.monotonic() + 50
    outcome = run_goozali_discovery(session)
    recommendations_processed = 0
    emails_processed = 0
    for _ in range(50):
        if time.monotonic() >= deadline:
            break
        if process_one_queued_recommendation(session) is None:
            break
        recommendations_processed += 1
    for _ in range(50):
        if time.monotonic() >= deadline:
            break
        if process_one_queued_email(session) is None:
            break
        emails_processed += 1
    return {
        "source_status": outcome.status,
        "records_seen": outcome.records_seen,
        "records_valid": outcome.records_valid,
        "jobs_created": outcome.created,
        "jobs_updated": outcome.updated,
        "jobs_deactivated": outcome.deactivated,
        "source_health_reason": outcome.health_reason,
        "deactivation_suppressed": outcome.deactivation_suppressed,
        "recommendations_processed": recommendations_processed,
        "emails_processed": emails_processed,
    }


def _authorize_worker(authorization: str) -> None:
    settings = get_settings()
    expected = settings.cron_secret or settings.backend_api_key
    supplied = authorization.removeprefix("Bearer ").strip()
    if not expected or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Worker authorization required.")
