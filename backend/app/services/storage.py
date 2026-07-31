from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import UUID

from ..config import get_settings


SUPABASE_LIST_PAGE_SIZE = 1000
SUPABASE_DELETE_BATCH_SIZE = 100
SUPABASE_LIST_RESPONSE_LIMIT = 2_000_000


def save_private_file(user_id: UUID, filename: str, data: bytes, content_type: str) -> str:
    settings = get_settings()
    storage_path = _validated_private_storage_path(f"{user_id}/{filename}", expected_user_id=user_id)
    if settings.supabase_url and settings.supabase_secret_key:
        _upload_to_supabase(storage_path, data, content_type)
        return storage_path

    local_path = settings.local_upload_dir / storage_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    return str(local_path.relative_to(settings.local_upload_dir)).replace("\\", "/")


def load_private_file(
    storage_path: str,
    *,
    expected_user_id: UUID | None = None,
) -> bytes | None:
    storage_path = _validated_private_storage_path(
        storage_path,
        expected_user_id=expected_user_id,
    )
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


def delete_private_file(
    storage_path: str,
    *,
    expected_user_id: UUID | None = None,
) -> None:
    if not storage_path:
        return
    storage_path = _validated_private_storage_path(
        storage_path,
        expected_user_id=expected_user_id,
    )
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


def delete_private_user_files(user_id: UUID) -> None:
    """Delete every object below one verified user prefix, including orphans."""
    settings = get_settings()
    if settings.supabase_url and settings.supabase_secret_key:
        paths = _list_supabase_user_files(user_id)
        for start in range(0, len(paths), SUPABASE_DELETE_BATCH_SIZE):
            _delete_supabase_files(paths[start : start + SUPABASE_DELETE_BATCH_SIZE])
        if _list_supabase_user_files(user_id):
            raise RuntimeError("Supabase Storage user prefix is not empty after deletion.")
        return

    root = settings.local_upload_dir.resolve()
    user_root = (root / str(user_id)).resolve()
    if user_root.parent != root:
        raise RuntimeError("Refusing to delete a storage prefix outside the private upload directory.")
    if not user_root.exists():
        return
    if not user_root.is_dir():
        raise RuntimeError("The private user storage prefix is not a directory.")
    shutil.rmtree(user_root)


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


def _list_supabase_user_files(user_id: UUID) -> list[str]:
    settings = get_settings()
    assert settings.supabase_url and settings.supabase_secret_key
    quoted_bucket = urllib.parse.quote(settings.supabase_storage_bucket, safe="")
    endpoint = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/list/{quoted_bucket}"
    headers = _supabase_storage_headers(content_type="application/json")
    root_prefix = str(user_id)
    directories = [root_prefix]
    seen_directories = {root_prefix}
    files: set[str] = set()

    while directories:
        directory = directories.pop()
        offset = 0
        seen_pages: set[tuple[tuple[str, str], ...]] = set()
        while True:
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(
                    {
                        "prefix": directory,
                        "limit": SUPABASE_LIST_PAGE_SIZE,
                        "offset": offset,
                        "sortBy": {"column": "name", "order": "asc"},
                    }
                ).encode("utf-8"),
                method="POST",
                headers=headers,
            )
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = response.read(SUPABASE_LIST_RESPONSE_LIMIT + 1)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"Supabase Storage listing failed: {exc.code} {detail}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError("Supabase Storage listing could not be reached.") from exc
            if len(raw) > SUPABASE_LIST_RESPONSE_LIMIT:
                raise RuntimeError("Supabase Storage listing response was too large.")
            try:
                items = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("Supabase Storage returned an invalid listing response.") from exc
            if not isinstance(items, list):
                raise RuntimeError("Supabase Storage returned an invalid listing response.")
            page_signature = tuple(
                (str(item.get("name") or ""), str(item.get("id") or ""))
                for item in items
                if isinstance(item, dict)
            )
            if items and page_signature in seen_pages:
                raise RuntimeError("Supabase Storage listing pagination did not advance.")
            seen_pages.add(page_signature)

            for item in items:
                if not isinstance(item, dict):
                    raise RuntimeError("Supabase Storage returned an invalid object entry.")
                name = str(item.get("name") or "")
                if not name or name in {".", ".."} or "/" in name or "\\" in name:
                    raise RuntimeError("Supabase Storage returned an unsafe object name.")
                storage_path = _validated_private_storage_path(
                    f"{directory}/{name}",
                    expected_user_id=user_id,
                )
                is_directory = item.get("id") is None and item.get("metadata") is None
                if is_directory:
                    if storage_path not in seen_directories:
                        seen_directories.add(storage_path)
                        directories.append(storage_path)
                else:
                    files.add(storage_path)

            if len(items) < SUPABASE_LIST_PAGE_SIZE:
                break
            offset += len(items)

    return sorted(files)


def _delete_supabase_files(storage_paths: list[str]) -> None:
    if not storage_paths:
        return
    try:
        expected_user_id = UUID(storage_paths[0].split("/", 1)[0])
    except (ValueError, IndexError) as exc:
        raise RuntimeError("Private storage path has an invalid owner prefix.") from exc
    verified_paths = [
        _validated_private_storage_path(path, expected_user_id=expected_user_id)
        for path in storage_paths
    ]
    settings = get_settings()
    assert settings.supabase_url and settings.supabase_secret_key
    quoted_bucket = urllib.parse.quote(settings.supabase_storage_bucket, safe="")
    endpoint = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{quoted_bucket}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"prefixes": verified_paths}).encode("utf-8"),
        method="DELETE",
        headers=_supabase_storage_headers(content_type="application/json"),
    )
    try:
        with urllib.request.urlopen(request, timeout=20):
            return
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Supabase Storage bulk deletion failed: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Supabase Storage bulk deletion could not be reached.") from exc


def _supabase_storage_headers(*, content_type: str | None = None) -> dict[str, str]:
    settings = get_settings()
    assert settings.supabase_secret_key
    headers = {
        "apikey": settings.supabase_secret_key,
        "User-Agent": "careerfit-api/1.0",
    }
    if content_type:
        headers["Content-Type"] = content_type
    if settings.supabase_secret_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {settings.supabase_secret_key}"
    return headers


def _validated_private_storage_path(
    storage_path: str,
    *,
    expected_user_id: UUID | None = None,
) -> str:
    if (
        not storage_path
        or storage_path != storage_path.strip()
        or storage_path.startswith("/")
        or storage_path.endswith("/")
        or "//" in storage_path
        or "\\" in storage_path
    ):
        raise RuntimeError("Private storage path is malformed.")
    parts = storage_path.split("/")
    if len(parts) < 2 or any(part in {"", ".", ".."} for part in parts):
        raise RuntimeError("Private storage path is malformed.")
    try:
        owner_id = UUID(parts[0])
    except ValueError as exc:
        raise RuntimeError("Private storage path has an invalid owner prefix.") from exc
    if parts[0] != str(owner_id):
        raise RuntimeError("Private storage owner prefix is not canonical.")
    if expected_user_id is not None and owner_id != expected_user_id:
        raise RuntimeError("Refusing to access another user's private storage.")
    return "/".join(parts)
