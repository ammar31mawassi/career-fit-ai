from __future__ import annotations

from types import SimpleNamespace

from starlette.requests import Request

from app.services import rate_limit


def _request(path: str = "/api/jobs", method: str = "POST") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [(b"authorization", b"Bearer test-token")],
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


def test_health_and_reads_are_not_limited():
    rate_limit._buckets.clear()

    assert rate_limit.check_rate_limit(_request("/api/health", "GET")) is None
    assert rate_limit.check_rate_limit(_request("/api/jobs/summary", "GET")) is None


def test_production_rate_limits_are_consumed_in_one_batch(monkeypatch):
    captured = []

    def consume(checks):
        captured.append(checks)
        return [{"allowed": True, "remaining": 5, "retry_after": 0} for _ in checks]

    monkeypatch.setattr(rate_limit, "get_settings", lambda: SimpleNamespace(app_env="production"))
    monkeypatch.setattr(rate_limit, "_consume_distributed_batch", consume)

    assert rate_limit.check_rate_limit(_request("/api/jobs", "POST")) is None
    assert len(captured) == 1
    assert [policy.key for policy, _ in captured[0]] == [
        "job-scan",
        "job-scan",
        "general-write",
        "general-write",
    ]
