from __future__ import annotations

import pytest

from scripts import production_smoke


def _valid_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(production_smoke, "TARGET_ENV", "staging")
    monkeypatch.setattr(production_smoke, "FRONTEND", "https://frontend.staging.example")
    monkeypatch.setattr(production_smoke, "BACKEND", "https://backend.staging.example")
    monkeypatch.setattr(production_smoke, "SUPABASE", "https://project.supabase.co")
    monkeypatch.setattr(production_smoke, "ANON_KEY", "public-test-key")
    monkeypatch.setattr(production_smoke, "SECRET_KEY", "private-test-key")
    monkeypatch.setattr(production_smoke, "INTERNAL_KEY", "internal-test-key")
    monkeypatch.setattr(production_smoke, "EMAIL_DOMAIN", "example.com")


def test_smoke_requires_an_explicit_staging_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _valid_configuration(monkeypatch)
    monkeypatch.setattr(production_smoke, "TARGET_ENV", "production")

    with pytest.raises(SystemExit, match="must not run against production"):
        production_smoke.validate_configuration()


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("FRONTEND", "http://frontend.staging.example"),
        ("BACKEND", "https://user:password@backend.staging.example"),
        ("SUPABASE", "https://project.supabase.co/rest/v1"),
    ],
)
def test_smoke_accepts_only_https_origins(
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    value: str,
) -> None:
    _valid_configuration(monkeypatch)
    monkeypatch.setattr(production_smoke, setting, value)

    with pytest.raises(SystemExit, match="absolute HTTPS origin"):
        production_smoke.validate_configuration()


def test_storage_cleanup_verification_requires_an_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _valid_configuration(monkeypatch)
    monkeypatch.setattr(
        production_smoke,
        "json_request",
        lambda *args, **kwargs: (200, []),
    )

    assert production_smoke.storage_prefix_is_empty(
        "00000000-0000-0000-0000-000000000101"
    )

    monkeypatch.setattr(
        production_smoke,
        "json_request",
        lambda *args, **kwargs: (200, [{"name": "cv.pdf"}]),
    )
    assert not production_smoke.storage_prefix_is_empty(
        "00000000-0000-0000-0000-000000000101"
    )
