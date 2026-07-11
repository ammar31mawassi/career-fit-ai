from __future__ import annotations

import json
import urllib.error
import urllib.request
from functools import lru_cache
from uuid import UUID, uuid5, NAMESPACE_URL

from fastapi import Depends, Header, HTTPException, Request
import jwt
from jwt import InvalidTokenError, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

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
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid Supabase session.") from exc

    # Asymmetric Supabase signing keys can be verified locally after the JWKS is
    # cached. Legacy HS256 projects still require the Auth endpoint until rotated.
    if header.get("alg") in {"ES256", "RS256"} and header.get("kid"):
        return _verify_with_jwks(token, settings.supabase_url)
    return _verify_with_auth_user(token, settings.supabase_url, settings.supabase_anon_key)


@lru_cache(maxsize=4)
def _jwks_client(supabase_url: str) -> PyJWKClient:
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True, cache_jwk_set=True, lifespan=600)


def _verify_with_jwks(token: str, supabase_url: str) -> UUID:
    issuer = f"{supabase_url.rstrip('/')}/auth/v1"
    try:
        signing_key = _jwks_client(supabase_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub", "role"]},
        )
    except PyJWKClientConnectionError as exc:
        raise HTTPException(status_code=502, detail="Supabase auth verification failed.") from exc
    except (InvalidTokenError, PyJWKClientError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Supabase session.") from exc
    if payload.get("role") != "authenticated":
        raise HTTPException(status_code=401, detail="Invalid Supabase session.")
    return _payload_user_id(payload)


def _verify_with_auth_user(token: str, supabase_url: str, anon_key: str) -> UUID:
    request = urllib.request.Request(
        f"{supabase_url.rstrip('/')}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": anon_key,
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
    return _payload_user_id({"sub": payload.get("id")})


def _payload_user_id(payload: dict[str, object]) -> UUID:
    try:
        return UUID(str(payload.get("sub") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Supabase session.") from exc
