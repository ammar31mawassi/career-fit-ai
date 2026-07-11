from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlmodel import Session
from uuid import UUID

from ..config import get_settings
from ..database import get_session
from ..schemas import (
    ClarificationAnswerIn,
    JobCreateIn,
    JobOut,
    JobStatusPatchIn,
    JobSummaryOut,
    ProfileAnalyzeResult,
    ProfileFactCreateIn,
    ProfileFactPatchIn,
    ProfileOut,
    ProfilePreferencesIn,
    ProfileSourcesIn,
)
from ..services.auth import current_user_id
from ..services.jobs import create_or_analyze_job, job_output, list_job_summaries, list_jobs, update_job_status
from ..services.profile import (
    analyze_profile,
    add_fact,
    answer_question,
    complete_onboarding,
    patch_fact,
    profile_output,
    update_profile_sources,
    update_profile_preferences,
    upload_cv_source,
    upload_linkedin_pdf_source,
)


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    return profile_output(session, user_id)


@router.post("/profile/cv", response_model=ProfileOut)
async def upload_cv(
    file: UploadFile = File(...),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Upload a PDF CV.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded CV is empty.")
    if len(data) > get_settings().max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded CV is too large. Use a PDF under 5 MB.")
    return upload_cv_source(session, user_id, file.filename or "cv.pdf", data)


@router.post("/profile/linkedin-pdf", response_model=ProfileOut)
async def upload_linkedin_pdf(
    file: UploadFile = File(...),
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded LinkedIn PDF is empty.")
    if len(data) > get_settings().max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded LinkedIn PDF is too large. Use a PDF under 5 MB.")
    return upload_linkedin_pdf_source(session, user_id, file.filename or "linkedin.pdf", data)


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
    user_id: UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> ProfileOut:
    try:
        return complete_onboarding(session, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
        return update_job_status(session, user_id, job_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
