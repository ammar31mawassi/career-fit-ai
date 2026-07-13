from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from threading import Lock

from fastapi import Request
from sqlalchemy import text
from starlette.responses import JSONResponse

from ..config import get_settings
from ..database import engine


@dataclass(frozen=True)
class RateLimitPolicy:
    key: str
    limit: int
    window_seconds: int
    methods: frozenset[str]
    paths: frozenset[str]


@dataclass
class Bucket:
    count: int
    reset_at: float


POLICIES: tuple[RateLimitPolicy, ...] = (
    RateLimitPolicy(
        key="job-scan",
        limit=10,
        window_seconds=60 * 60,
        methods=frozenset({"POST"}),
        paths=frozenset({"/api/jobs", "/api/job-scans"}),
    ),
    RateLimitPolicy(
        key="profile-analyze",
        limit=6,
        window_seconds=60 * 60,
        methods=frozenset({"POST"}),
        paths=frozenset({"/api/profile/analyze"}),
    ),
    RateLimitPolicy(
        key="file-upload",
        limit=8,
        window_seconds=60 * 60,
        methods=frozenset({"POST"}),
        paths=frozenset({"/api/profile/cv", "/api/profile/cv/browser-ocr", "/api/profile/linkedin-pdf"}),
    ),
    RateLimitPolicy(
        key="general-write",
        limit=180,
        window_seconds=10 * 60,
        methods=frozenset({"POST", "PUT", "PATCH", "DELETE"}),
        paths=frozenset(),
    ),
)

_buckets: dict[str, Bucket] = {}
_lock = Lock()


def rate_limit_keys(request: Request, policy: RateLimitPolicy) -> list[str]:
    authorization = request.headers.get("authorization", "")
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    address = forwarded or request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    keys = [f"{policy.key}:ip:{hashlib.sha256(address.encode('utf-8')).hexdigest()[:24]}"]
    if authorization.lower().startswith("bearer "):
        token_digest = hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:24]
        keys.insert(0, f"{policy.key}:bearer:{token_digest}")
    return keys


def matching_policies(request: Request) -> list[RateLimitPolicy]:
    method = request.method.upper()
    path = request.url.path.rstrip("/") or "/"
    if method in {"GET", "HEAD", "OPTIONS"} or path == "/api/health":
        return []
    policies: list[RateLimitPolicy] = []
    for policy in POLICIES:
        if method not in policy.methods:
            continue
        if policy.paths and path not in policy.paths:
            continue
        policies.append(policy)
    return policies


def check_rate_limit(request: Request) -> JSONResponse | None:
    policies = matching_policies(request)
    if not policies:
        return None
    settings = get_settings()
    if settings.app_env == "production":
        try:
            checks = [
                (policy, key)
                for policy in policies
                for key in rate_limit_keys(request, policy)
            ]
            for (policy, _), result in zip(checks, _consume_distributed_batch(checks), strict=True):
                if not result["allowed"]:
                    return _limited_response(policy, result["retry_after"], result["remaining"])
        except Exception:
            return JSONResponse(
                {"detail": "Request protection is temporarily unavailable. Try again shortly."},
                status_code=503,
                headers={"Retry-After": "10"},
            )
        return None

    now = time.time()
    expired_before = now - 24 * 60 * 60
    with _lock:
        if len(_buckets) > 5000:
            for key, bucket in list(_buckets.items()):
                if bucket.reset_at < expired_before:
                    _buckets.pop(key, None)

        for policy in policies:
            for key in rate_limit_keys(request, policy):
                bucket = _buckets.get(key)
                if bucket is None or bucket.reset_at <= now:
                    bucket = Bucket(count=0, reset_at=now + policy.window_seconds)
                    _buckets[key] = bucket
                if bucket.count >= policy.limit:
                    retry_after = max(1, int(bucket.reset_at - now))
                    return _limited_response(policy, retry_after, 0, reset_at=int(bucket.reset_at))
                bucket.count += 1
    return None


def _consume_distributed(key: str, limit: int, window_seconds: int) -> dict[str, int | bool]:
    statement = text(
        "select allowed, remaining, retry_after "
        "from public.consume_rate_limit(:bucket_key, :request_limit, :window_seconds)"
    )
    with engine.begin() as connection:
        row = connection.execute(
            statement,
            {"bucket_key": key, "request_limit": limit, "window_seconds": window_seconds},
        ).mappings().one()
    return {
        "allowed": bool(row["allowed"]),
        "remaining": int(row["remaining"]),
        "retry_after": int(row["retry_after"]),
    }


def _consume_distributed_batch(
    checks: list[tuple[RateLimitPolicy, str]],
) -> list[dict[str, int | bool]]:
    """Consume every applicable bucket in one database round trip.

    Serverless runtimes use NullPool, so opening a new TLS/Postgres connection
    for every user/IP/policy bucket made ordinary writes spend several seconds
    in rate limiting alone.
    """
    if not checks:
        return []
    values: list[str] = []
    parameters: dict[str, object] = {}
    for index, (policy, key) in enumerate(checks):
        values.append(f"(:key_{index}, :limit_{index}, :window_{index}, {index})")
        parameters[f"key_{index}"] = key
        parameters[f"limit_{index}"] = policy.limit
        parameters[f"window_{index}"] = policy.window_seconds
    statement = text(
        "with checks(bucket_key, request_limit, window_seconds, ordinal) as (values "
        + ",".join(values)
        + ") select checks.ordinal, result.allowed, result.remaining, result.retry_after "
        "from checks cross join lateral public.consume_rate_limit("
        "checks.bucket_key, checks.request_limit, checks.window_seconds) result "
        "order by checks.ordinal"
    )
    with engine.begin() as connection:
        rows = connection.execute(statement, parameters).mappings().all()
    return [
        {
            "allowed": bool(row["allowed"]),
            "remaining": int(row["remaining"]),
            "retry_after": int(row["retry_after"]),
        }
        for row in rows
    ]


def _limited_response(
    policy: RateLimitPolicy,
    retry_after: int,
    remaining: int,
    *,
    reset_at: int | None = None,
) -> JSONResponse:
    headers = {
        "Retry-After": str(max(1, retry_after)),
        "X-RateLimit-Limit": str(policy.limit),
        "X-RateLimit-Remaining": str(max(0, remaining)),
    }
    if reset_at is not None:
        headers["X-RateLimit-Reset"] = str(reset_at)
    return JSONResponse(
        {"detail": f"Rate limit reached for {policy.key}. Try again later."},
        status_code=429,
        headers=headers,
    )
