from __future__ import annotations

from uuid import UUID

import jwt
import pytest
from fastapi import HTTPException

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
