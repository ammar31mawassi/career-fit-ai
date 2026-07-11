from __future__ import annotations

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
