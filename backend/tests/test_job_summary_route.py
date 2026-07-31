from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes
from app.schemas import JobSummaryPageOut


USER_ID = UUID("00000000-0000-0000-0000-000000000101")


def _test_client() -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.current_user_id] = lambda: USER_ID
    app.dependency_overrides[routes.get_session] = lambda: object()
    return TestClient(app)


def test_job_summary_page_returns_serialized_page_with_etag(monkeypatch):
    watermark = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    page = JobSummaryPageOut(items=[], next_cursor="next-page", watermark=watermark)
    calls: list[tuple[str, int, str, datetime | None]] = []

    def fake_list_job_summary_page(session, user_id, *, query, limit, cursor, watermark):
        assert session is not None
        assert user_id == USER_ID
        calls.append((query, limit, cursor, watermark))
        return page

    monkeypatch.setattr(routes, "list_job_summary_page", fake_list_job_summary_page)

    response = _test_client().get(
        "/api/jobs/summary-page",
        params={
            "query": " Python ",
            "limit": 12,
            "cursor": "cursor-1",
            "watermark": watermark.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "next_cursor": "next-page",
        "watermark": "2026-07-30T12:00:00Z",
    }
    assert response.headers["etag"].startswith('"')
    assert response.headers["etag"].endswith('"')
    assert calls == [(" Python ", 12, "cursor-1", watermark)]


def test_job_summary_page_honors_matching_if_none_match(monkeypatch):
    page = JobSummaryPageOut(
        items=[],
        next_cursor=None,
        watermark=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(routes, "list_job_summary_page", lambda *args, **kwargs: page)
    client = _test_client()
    path = "/api/jobs/summary-page?limit=12&cursor=cursor-1"

    initial = client.get(path)
    response = client.get(path, headers={"If-None-Match": initial.headers["etag"]})

    assert initial.status_code == 200
    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == initial.headers["etag"]


def test_job_summary_page_etag_changes_when_representation_changes(monkeypatch):
    watermark = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    pages = iter(
        [
            JobSummaryPageOut(items=[], next_cursor="next-page", watermark=watermark),
            JobSummaryPageOut(items=[], next_cursor=None, watermark=watermark),
        ]
    )
    monkeypatch.setattr(routes, "list_job_summary_page", lambda *args, **kwargs: next(pages))
    client = _test_client()

    first = client.get("/api/jobs/summary-page")
    second = client.get("/api/jobs/summary-page")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["etag"] != second.headers["etag"]
