from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.services import rate_limit


def _request(
    path: str = "/api/jobs",
    method: str = "POST",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": headers or [(b"authorization", b"Bearer test-token")],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_job_scan_rate_limit_blocks_after_hourly_budget():
    rate_limit._buckets.clear()
    request = _request()

    for _ in range(10):
        assert rate_limit.check_rate_limit(request) is None

    response = rate_limit.check_rate_limit(request)

    assert response is not None
    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_health_and_cheap_reads_are_not_limited():
    rate_limit._buckets.clear()

    assert rate_limit.check_rate_limit(_request("/api/health", "GET")) is None
    assert rate_limit.check_rate_limit(_request("/api/profile", "GET")) is None
    assert [policy.key for policy in rate_limit.matching_policies(
        _request("/api/jobs/summary-page", "GET")
    )] == ["heavy-read"]
    assert [policy.key for policy in rate_limit.matching_policies(
        _request("/api/account/export", "GET")
    )] == ["account-export"]


def test_untrusted_forwarding_headers_do_not_change_direct_client_bucket(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    policy = rate_limit.POLICIES[0]
    request = _request(
        headers=[
            (b"authorization", b"Bearer test-token"),
            (b"x-forwarded-for", b"203.0.113.10"),
            (b"x-real-ip", b"203.0.113.11"),
            (b"x-vercel-forwarded-for", b"203.0.113.12"),
        ]
    )

    keys = rate_limit.rate_limit_keys(request, policy)
    expected = rate_limit.hashlib.sha256(b"127.0.0.1").hexdigest()[:24]

    assert f"{policy.key}:ip:{expected}" in keys


@pytest.mark.parametrize("app_env", ("staging", "production"))
def test_deployed_rate_limits_are_consumed_in_one_batch(monkeypatch, app_env):
    captured = []

    def consume(checks):
        captured.append(checks)
        return [{"allowed": True, "remaining": 5, "retry_after": 0} for _ in checks]

    monkeypatch.setattr(rate_limit, "get_settings", lambda: SimpleNamespace(app_env=app_env))
    monkeypatch.setattr(rate_limit, "_consume_distributed_batch", consume)

    assert rate_limit.check_rate_limit(_request("/api/jobs", "POST")) is None
    assert len(captured) == 1
    assert [policy.key for policy, _ in captured[0]] == [
        "job-scan",
        "job-scan",
        "general-write",
        "general-write",
    ]
