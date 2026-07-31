from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config import _app_env, _uuid_values, get_settings, validate_security_settings
from app.services import auth


USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_asymmetric_token_uses_cached_jwks_verifier(monkeypatch):
    token = "header.payload.signature"
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda received: {"alg": "ES256", "kid": "test-key"})
    monkeypatch.setattr(auth, "_verify_with_jwks", lambda received, url: USER_ID)
    monkeypatch.setattr(auth, "_verify_with_auth_user", lambda *_: pytest.fail("unexpected remote fallback"))

    assert auth._verify_supabase_token(token) == USER_ID


def test_legacy_token_keeps_auth_user_fallback(monkeypatch):
    token = jwt.encode({"sub": str(USER_ID)}, "legacy-secret-at-least-thirty-two-bytes", algorithm="HS256")
    monkeypatch.setattr(auth, "_verify_with_auth_user", lambda received, url, key: USER_ID)

    assert auth._verify_supabase_token(token) == USER_ID


def test_payload_requires_uuid_subject():
    with pytest.raises(HTTPException) as caught:
        auth._payload_user_id({"sub": "not-a-uuid"})

    assert caught.value.status_code == 401


def test_app_env_defaults_to_fail_closed_production():
    assert _app_env(None) == "production"
    assert _app_env(" development ") == "development"

    with pytest.raises(RuntimeError, match="APP_ENV must be one of"):
        _app_env("prodution")


def test_production_security_configuration_is_validated_without_secret_values():
    unsafe = replace(
        get_settings(),
        app_env="production",
        dev_auth_enabled=True,
        backend_api_key="short",
        supabase_url=None,
        supabase_anon_key=None,
        supabase_secret_key=None,
    )

    with pytest.raises(RuntimeError) as caught:
        validate_security_settings(unsafe)

    message = str(caught.value)
    assert "BACKEND_API_KEY" in message
    assert "ENABLE_DEV_AUTH" in message
    assert "SUPABASE_URL" in message
    assert "SUPABASE_ANON_KEY" in message
    assert "SUPABASE_SECRET_KEY" in message
    assert "short" not in message


@pytest.mark.parametrize("app_env", ("staging", "production"))
def test_internal_key_is_required_in_deployed_environments(monkeypatch, app_env):
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            app_env=app_env,
            backend_api_key="a-secure-internal-key-with-32-characters",
            backend_api_key_next="next-secure-internal-key-with-32-characters",
        ),
    )

    with pytest.raises(HTTPException) as missing:
        auth.require_internal_key(None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as wrong:
        auth.require_internal_key("wrong")
    assert wrong.value.status_code == 401

    assert auth.require_internal_key("a-secure-internal-key-with-32-characters") is None
    assert auth.require_internal_key("next-secure-internal-key-with-32-characters") is None


def test_staging_security_configuration_is_validated():
    unsafe = replace(
        get_settings(),
        app_env="staging",
        dev_auth_enabled=True,
        backend_api_key="short",
        database_url="sqlite:///staging.db",
        allowed_origins=("http://staging.example",),
        frontend_url="http://staging.example",
        public_api_url="http://api.staging.example",
        supabase_url="http://supabase.internal",
        supabase_anon_key=None,
        supabase_secret_key=None,
    )

    with pytest.raises(RuntimeError) as caught:
        validate_security_settings(unsafe)

    message = str(caught.value)
    assert "ENABLE_DEV_AUTH" in message
    assert "DATABASE_URL must use PostgreSQL" in message
    assert "ALLOWED_ORIGINS" in message
    assert "SUPABASE_URL must be an absolute HTTPS URL" in message


def test_complete_deployed_security_configuration_is_accepted():
    safe = replace(
        get_settings(),
        app_env="staging",
        dev_auth_enabled=False,
        backend_api_key="a-secure-internal-key-with-32-characters",
        database_url="postgresql+psycopg://user:password@db.example/careerfit",
        allowed_origins=("https://staging.example",),
        frontend_url="https://staging.example",
        public_api_url="https://api.staging.example",
        supabase_url="https://project.supabase.co",
        supabase_anon_key="publishable-test-key",
        supabase_secret_key="sb_secret_test",
        max_upload_bytes=5 * 1024 * 1024,
        ocr_service_url="https://ocr.staging.example",
        resend_api_key=None,
        notification_from_email=None,
        notification_signing_secret=None,
    )

    validate_security_settings(safe)


def test_deployed_security_configuration_allows_a_strong_rotation_key():
    rotating = replace(
        get_settings(),
        app_env="production",
        dev_auth_enabled=False,
        backend_api_key="legacy-short-key",
        backend_api_key_next="next-secure-internal-key-with-32-characters",
        database_url="postgresql+psycopg://user:password@db.example/careerfit",
        allowed_origins=("https://careerfit.example",),
        frontend_url="https://careerfit.example",
        public_api_url="https://api.careerfit.example",
        supabase_url="https://project.supabase.co",
        supabase_anon_key="publishable-test-key",
        supabase_secret_key="sb_secret_test",
        max_upload_bytes=5 * 1024 * 1024,
        resend_api_key=None,
        notification_from_email=None,
        notification_signing_secret=None,
    )

    validate_security_settings(rotating)


def test_development_auth_bypass_requires_explicit_flag(monkeypatch):
    request = Request({"type": "http", "headers": []})
    base = SimpleNamespace(
        app_env="development",
        dev_auth_enabled=False,
        supabase_url=None,
        supabase_anon_key=None,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: base)

    with pytest.raises(HTTPException) as disabled:
        auth.current_user_id(request, None, authorization=None, x_dev_user_id=None)
    assert disabled.value.status_code == 401

    enabled = SimpleNamespace(**{**vars(base), "dev_auth_enabled": True})
    monkeypatch.setattr(auth, "get_settings", lambda: enabled)

    assert auth.current_user_id(
        request,
        None,
        authorization=None,
        x_dev_user_id=None,
    ) == UUID("00000000-0000-0000-0000-000000000001")


def test_invalid_beta_uuid_configuration_fails_loudly():
    with pytest.raises(RuntimeError, match="GOOZALI_BETA_USER_IDS.*invalid UUID"):
        _uuid_values(
            "00000000-0000-0000-0000-000000000001,not-a-uuid",
            "GOOZALI_BETA_USER_IDS",
        )
