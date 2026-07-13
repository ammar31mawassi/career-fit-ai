from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from ..config import get_settings
from ..models import JobRequirementRevision, Profile, ProfileFactFeedback, ProfileSource
from ..schemas import (
    AccountExportOut,
    AccountFeedbackExportOut,
    AccountRequirementFeedbackOut,
    AccountSourceExportOut,
)
from .jobs import list_jobs
from .profile import profile_output
from .storage import delete_private_file


def export_account(session: Session, user_id: UUID) -> AccountExportOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    sources = [] if profile is None else list(
        session.exec(
            select(ProfileSource)
            .where(ProfileSource.profile_id == profile.id)
            .order_by(ProfileSource.created_at)
        ).all()
    )
    feedback = [] if profile is None else list(
        session.exec(
            select(ProfileFactFeedback)
            .where(ProfileFactFeedback.profile_id == profile.id)
            .order_by(ProfileFactFeedback.created_at)
        ).all()
    )
    requirement_feedback = list(
        session.exec(
            select(JobRequirementRevision)
            .where(JobRequirementRevision.user_id == user_id)
            .order_by(JobRequirementRevision.created_at)
        ).all()
    )
    return AccountExportOut(
        exported_at=datetime.now(timezone.utc),
        profile=profile_output(session, user_id),
        sources=[
            AccountSourceExportOut(
                source_type=source.source_type,
                title=source.title,
                content_text=source.content_text,
                updated_at=source.updated_at,
            )
            for source in sources
        ],
        fact_feedback=[
            AccountFeedbackExportOut(
                fact_type=item.fact_type,
                action=item.action,
                original_value=item.original_value,
                corrected_value=item.corrected_value,
                created_at=item.created_at,
            )
            for item in feedback
        ],
        requirement_feedback=[
            AccountRequirementFeedbackOut(
                job_id=item.job_id,
                original_requirements=_json_dict(item.original_requirements_json),
                corrected_requirements=_json_dict(item.corrected_requirements_json),
                changed_fields=_json_list(item.changed_fields_json),
                created_at=item.created_at,
            )
            for item in requirement_feedback
        ],
        jobs=list_jobs(session, user_id, limit=10_000),
    )


def _json_dict(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def delete_account(session: Session, user_id: UUID) -> None:
    sources = list(
        session.exec(select(ProfileSource).where(ProfileSource.user_id == user_id)).all()
    )
    for source in sources:
        if source.storage_path:
            delete_private_file(source.storage_path)
    _delete_supabase_auth_user(user_id)
    # Auth deletion cascades through every user-owned public table. End the
    # read transaction so this session cannot expose a stale identity map.
    session.rollback()
    session.expire_all()


def _delete_supabase_auth_user(user_id: UUID) -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise RuntimeError("Account deletion is not configured.")
    endpoint = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}"
    headers = {
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
        "User-Agent": "careerfit-api/1.0",
    }
    try:
        with urllib.request.urlopen(
            urllib.request.Request(endpoint, method="DELETE", headers=headers),
            timeout=20,
        ):
            return
    except urllib.error.HTTPError as exc:
        exc.read()
        raise RuntimeError("Supabase account deletion failed.") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Supabase account deletion could not be reached.") from exc
