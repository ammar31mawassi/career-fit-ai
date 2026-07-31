from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
VALID_APP_ENVS = frozenset({"development", "test", "staging", "production"})


@dataclass(frozen=True)
class Settings:
    app_env: str
    dev_auth_enabled: bool
    database_url: str
    database_pool_size: int
    database_max_overflow: int
    allowed_origins: tuple[str, ...]
    backend_api_key: str | None
    supabase_url: str | None
    supabase_anon_key: str | None
    supabase_secret_key: str | None
    supabase_storage_bucket: str
    local_upload_dir: Path
    max_upload_bytes: int
    ocr_service_url: str | None
    ocr_service_token: str | None
    github_token: str | None
    cron_secret: str | None
    score_calibration_path: Path | None
    frontend_url: str
    public_api_url: str
    goozali_enabled: bool
    goozali_embed_url: str
    goozali_initial_lookback_hours: int
    goozali_max_jobs_per_run: int
    goozali_beta_user_ids: tuple[UUID, ...]
    resend_api_key: str | None
    notification_from_email: str | None
    notification_signing_secret: str | None
    # Backend-only overlap key used for zero-downtime internal-key rotation.
    # It must never be configured on the frontend or retained after rotation.
    backend_api_key_next: str | None = None


def _csv_values(value: str) -> tuple[str, ...]:
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


def _path_value(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (ROOT_DIR / path).resolve()


def _bool_value(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _app_env(value: str | None) -> str:
    # Authentication must fail closed when a deployment forgets APP_ENV.
    # Local development remains an explicit opt-in through .env.example.
    normalized = (value or "production").strip().lower()
    if normalized not in VALID_APP_ENVS:
        choices = ", ".join(sorted(VALID_APP_ENVS))
        raise RuntimeError(f"APP_ENV must be one of: {choices}.")
    return normalized


def _uuid_values(value: str, variable_name: str = "UUID list") -> tuple[UUID, ...]:
    parsed: list[UUID] = []
    for item in value.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        try:
            parsed.append(UUID(candidate))
        except ValueError as exc:
            raise RuntimeError(
                f"{variable_name} contains an invalid UUID: {candidate!r}."
            ) from exc
    return tuple(parsed)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_env=_app_env(os.getenv("APP_ENV")),
        dev_auth_enabled=_bool_value(os.getenv("ENABLE_DEV_AUTH", "false")),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/career_fit_ai.db"),
        database_pool_size=max(1, int(os.getenv("DATABASE_POOL_SIZE", "1"))),
        database_max_overflow=max(0, int(os.getenv("DATABASE_MAX_OVERFLOW", "1"))),
        allowed_origins=_csv_values(
            os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        ),
        backend_api_key=os.getenv("BACKEND_API_KEY") or None,
        supabase_url=(os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or None),
        supabase_anon_key=(
            os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or None
        ),
        supabase_secret_key=(
            os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or None
        ),
        supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "profile-documents"),
        local_upload_dir=_path_value(os.getenv("LOCAL_UPLOAD_DIR", "./data/uploads")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024))),
        ocr_service_url=os.getenv("OCR_SERVICE_URL") or None,
        ocr_service_token=os.getenv("OCR_SERVICE_TOKEN") or None,
        github_token=os.getenv("GITHUB_TOKEN") or None,
        cron_secret=os.getenv("CRON_SECRET") or None,
        score_calibration_path=(
            _path_value(os.environ["SCORE_CALIBRATION_PATH"])
            if os.getenv("SCORE_CALIBRATION_PATH")
            else None
        ),
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000").strip().rstrip("/"),
        public_api_url=os.getenv("PUBLIC_API_URL", "http://127.0.0.1:8000").strip().rstrip("/"),
        goozali_enabled=_bool_value(os.getenv("GOOZALI_DISCOVERY_ENABLED", "false")),
        goozali_embed_url=os.getenv(
            "GOOZALI_EMBED_URL",
            "https://airtable.com/embed/appwewqLk7iUY4azc/shrQBuWjXd0YgPqV6?backgroundColor=cyan&viewControls=on",
        ).strip(),
        goozali_initial_lookback_hours=max(
            1, int(os.getenv("GOOZALI_INITIAL_LOOKBACK_HOURS", "72"))
        ),
        goozali_max_jobs_per_run=max(1, int(os.getenv("GOOZALI_MAX_JOBS_PER_RUN", "40"))),
        goozali_beta_user_ids=_uuid_values(
            os.getenv("GOOZALI_BETA_USER_IDS", ""),
            "GOOZALI_BETA_USER_IDS",
        ),
        resend_api_key=os.getenv("RESEND_API_KEY") or None,
        notification_from_email=os.getenv("NOTIFICATION_FROM_EMAIL") or None,
        notification_signing_secret=os.getenv("NOTIFICATION_SIGNING_SECRET") or None,
        backend_api_key_next=os.getenv("BACKEND_API_KEY_NEXT") or None,
    )


def _is_secure_absolute_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username


def validate_security_settings(settings: Settings) -> None:
    """Reject deployed startup when security or dependency boundaries are unsafe."""

    if settings.app_env not in {"staging", "production"}:
        return

    missing: list[str] = []
    if settings.dev_auth_enabled:
        missing.append("ENABLE_DEV_AUTH must be false")
    if not settings.backend_api_key:
        missing.append("BACKEND_API_KEY (at least 32 characters)")
    elif len(settings.backend_api_key) < 32 and not settings.backend_api_key_next:
        missing.append("BACKEND_API_KEY (at least 32 characters)")
    if settings.backend_api_key_next and len(settings.backend_api_key_next) < 32:
        missing.append("BACKEND_API_KEY_NEXT (at least 32 characters)")
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not settings.supabase_anon_key:
        missing.append("SUPABASE_ANON_KEY")
    if not settings.supabase_secret_key:
        missing.append("SUPABASE_SECRET_KEY")
    if settings.supabase_url and not _is_secure_absolute_url(settings.supabase_url):
        missing.append("SUPABASE_URL must be an absolute HTTPS URL")
    if not settings.database_url.lower().startswith(("postgresql://", "postgresql+psycopg://")):
        missing.append("DATABASE_URL must use PostgreSQL")
    if not settings.allowed_origins or any(
        origin == "*" or not _is_secure_absolute_url(origin)
        for origin in settings.allowed_origins
    ):
        missing.append("ALLOWED_ORIGINS must contain only explicit HTTPS origins")
    if not _is_secure_absolute_url(settings.frontend_url):
        missing.append("FRONTEND_URL must be an absolute HTTPS URL")
    elif settings.frontend_url not in settings.allowed_origins:
        missing.append("FRONTEND_URL must be present in ALLOWED_ORIGINS")
    if not _is_secure_absolute_url(settings.public_api_url):
        missing.append("PUBLIC_API_URL must be an absolute HTTPS URL")
    if settings.ocr_service_url and not _is_secure_absolute_url(settings.ocr_service_url):
        missing.append("OCR_SERVICE_URL must be an absolute HTTPS URL")
    if not 1024 * 1024 <= settings.max_upload_bytes <= 20 * 1024 * 1024:
        missing.append("MAX_UPLOAD_BYTES must be between 1 MiB and 20 MiB")

    notification_values = (
        settings.resend_api_key,
        settings.notification_from_email,
        settings.notification_signing_secret,
    )
    if any(notification_values) and not all(notification_values):
        missing.append("notification settings must be configured together")
    if (
        settings.notification_signing_secret
        and len(settings.notification_signing_secret) < 32
    ):
        missing.append("NOTIFICATION_SIGNING_SECRET (at least 32 characters)")

    if missing:
        raise RuntimeError(
            "Deployed security configuration is incomplete: " + ", ".join(missing) + "."
        )
