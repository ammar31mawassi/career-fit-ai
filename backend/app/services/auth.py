from __future__ import annotations

import json
import urllib.error
import urllib.request
from uuid import UUID, uuid5, NAMESPACE_URL

from fastapi import Depends, Header, HTTPException, Request

from ..config import get_settings


def require_internal_key(x_internal_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if settings.app_env != "production":
        return
    if not settings.backend_api_key:
        raise HTTPException(status_code=503, detail="Backend API key is not configured.")
    if x_internal_api_key != settings.backend_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized.")


def current_user_id(
    request: Request,
    _: None = Depends(require_internal_key),
    authorization: str | None = Header(default=None),
    x_dev_user_id: str | None = Header(default=None),
) -> UUID:
    settings = get_settings()
    if settings.app_env in {"development", "test"} and x_dev_user_id:
        try:
            return UUID(x_dev_user_id)
        except ValueError:
            return uuid5(NAMESPACE_URL, f"career-fit-dev:{x_dev_user_id}")
    if settings.app_env == "development" and not authorization:
        return UUID("00000000-0000-0000-0000-000000000001")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.split(" ", 1)[1].strip()
    if not settings.supabase_url or not settings.supabase_anon_key:
        if settings.app_env == "production":
            raise HTTPException(status_code=503, detail="Supabase auth is not configured.")
        return UUID("00000000-0000-0000-0000-000000000001")
    return _verify_supabase_token(token)


def _verify_supabase_token(token: str) -> UUID:
    settings = get_settings()
    assert settings.supabase_url and settings.supabase_anon_key
    request = urllib.request.Request(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": settings.supabase_anon_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise HTTPException(status_code=401, detail="Invalid Supabase session.") from exc
        raise HTTPException(status_code=502, detail="Supabase auth verification failed.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Supabase auth verification failed.") from exc
    try:
        user_id = UUID(str(payload.get("id") or ""))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Supabase session.")
    return user_id
