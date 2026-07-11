from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from threading import Lock

from fastapi import Request
from starlette.responses import JSONResponse


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
        paths=frozenset({"/api/jobs"}),
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
        paths=frozenset({"/api/profile/cv", "/api/profile/linkedin-pdf"}),
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


def rate_limit_key(request: Request, policy: RateLimitPolicy) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        subject = "bearer:" + hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:24]
    else:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        subject = "ip:" + (forwarded or request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown"))
    return f"{policy.key}:{subject}"


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
    now = time.time()
    expired_before = now - 24 * 60 * 60
    with _lock:
        if len(_buckets) > 5000:
            for key, bucket in list(_buckets.items()):
                if bucket.reset_at < expired_before:
                    _buckets.pop(key, None)

        for policy in matching_policies(request):
            key = rate_limit_key(request, policy)
            bucket = _buckets.get(key)
            if bucket is None or bucket.reset_at <= now:
                bucket = Bucket(count=0, reset_at=now + policy.window_seconds)
                _buckets[key] = bucket
            if bucket.count >= policy.limit:
                retry_after = max(1, int(bucket.reset_at - now))
                return JSONResponse(
                    {"detail": f"Rate limit reached for {policy.key}. Try again later."},
                    status_code=429,
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(policy.limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(bucket.reset_at)),
                    },
                )
            bucket.count += 1
    return None
