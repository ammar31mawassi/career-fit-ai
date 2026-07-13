from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import UUID

from ..config import get_settings


def save_private_file(user_id: UUID, filename: str, data: bytes, content_type: str) -> str:
    settings = get_settings()
    storage_path = f"{user_id}/{filename}"
    if settings.supabase_url and settings.supabase_secret_key:
        _upload_to_supabase(storage_path, data, content_type)
        return storage_path

    local_path = settings.local_upload_dir / storage_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    return str(local_path.relative_to(settings.local_upload_dir)).replace("\\", "/")


def load_private_file(storage_path: str) -> bytes | None:
    settings = get_settings()
    if settings.supabase_url and settings.supabase_secret_key:
        quoted_bucket = urllib.parse.quote(settings.supabase_storage_bucket, safe="")
        quoted_path = "/".join(urllib.parse.quote(part, safe="") for part in storage_path.split("/"))
        headers = {"apikey": settings.supabase_secret_key}
        if settings.supabase_secret_key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {settings.supabase_secret_key}"
        endpoints = (
            f"{settings.supabase_url.rstrip('/')}/storage/v1/object/authenticated/{quoted_bucket}/{quoted_path}",
            f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{quoted_bucket}/{quoted_path}",
        )
        for endpoint in endpoints:
            try:
                with urllib.request.urlopen(urllib.request.Request(endpoint, headers=headers), timeout=20) as response:
                    return response.read()
            except (urllib.error.HTTPError, urllib.error.URLError):
                continue
        return None

    root = settings.local_upload_dir.resolve()
    local_path = (root / storage_path).resolve()
    if root not in local_path.parents or not local_path.is_file():
        return None
    return local_path.read_bytes()


def delete_private_file(storage_path: str) -> None:
    if not storage_path:
        return
    settings = get_settings()
    if settings.supabase_url and settings.supabase_secret_key:
        quoted_bucket = urllib.parse.quote(settings.supabase_storage_bucket, safe="")
        quoted_path = "/".join(urllib.parse.quote(part, safe="") for part in storage_path.split("/"))
        endpoint = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{quoted_bucket}/{quoted_path}"
        headers = {
            "apikey": settings.supabase_secret_key,
            "User-Agent": "careerfit-api/1.0",
        }
        if settings.supabase_secret_key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {settings.supabase_secret_key}"
        try:
            with urllib.request.urlopen(
                urllib.request.Request(endpoint, method="DELETE", headers=headers),
                timeout=20,
            ):
                return
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Supabase Storage deletion failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Supabase Storage deletion could not be reached.") from exc

    root = settings.local_upload_dir.resolve()
    local_path = (root / Path(storage_path)).resolve()
    if root not in local_path.parents:
        raise RuntimeError("Refusing to delete a file outside the private upload directory.")
    if local_path.is_file():
        local_path.unlink()


def _upload_to_supabase(storage_path: str, data: bytes, content_type: str) -> None:
    settings = get_settings()
    assert settings.supabase_url and settings.supabase_secret_key
    quoted_bucket = urllib.parse.quote(settings.supabase_storage_bucket, safe="")
    quoted_path = "/".join(urllib.parse.quote(part, safe="") for part in storage_path.split("/"))
    endpoint = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{quoted_bucket}/{quoted_path}"
    headers = {
        "apikey": settings.supabase_secret_key,
        "Content-Type": content_type,
        "x-upsert": "true",
        "User-Agent": "careerfit-api/1.0",
    }
    # Legacy service_role JWTs are valid bearer tokens. New sb_secret keys must
    # only be sent as apikey values and never exposed to browser code.
    if settings.supabase_secret_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {settings.supabase_secret_key}"
    request = urllib.request.Request(
        endpoint,
        data=data,
        method="PUT",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=20):
            return
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Supabase Storage upload failed: {exc.code} {detail}") from exc
