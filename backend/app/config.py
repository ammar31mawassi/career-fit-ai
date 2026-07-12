from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
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


def _csv_values(value: str) -> tuple[str, ...]:
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


def _path_value(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (ROOT_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development").strip().lower(),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/career_fit_ai.db"),
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
    )
