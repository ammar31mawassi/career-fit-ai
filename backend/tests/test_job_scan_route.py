from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes
from app.schemas import JobScanOut


USER_ID = UUID("00000000-0000-0000-0000-000000000103")


def _test_client() -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.current_user_id] = lambda: USER_ID
    app.dependency_overrides[routes.get_session] = lambda: object()
    return TestClient(app)


def test_active_job_scan_returns_null_when_the_user_has_no_active_scan(monkeypatch):
    calls = []

    def fake_latest_active_scan(session, user_id):
        calls.append((session, user_id))
        return None

    monkeypatch.setattr(routes, "latest_active_scan", fake_latest_active_scan)

    response = _test_client().get("/api/job-scans/active")

    assert response.status_code == 200
    assert response.json() is None
    assert len(calls) == 1
    assert calls[0][0] is not None
    assert calls[0][1] == USER_ID


def test_active_job_scan_route_precedes_the_dynamic_scan_id_route(monkeypatch):
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    scan = JobScanOut(
        id=42,
        status="cancel_requested",
        current_step="cancel_requested",
        progress=55,
        trace_id="trace-42",
        created_at=timestamp,
        updated_at=timestamp,
    )
    monkeypatch.setattr(routes, "latest_active_scan", lambda *args: scan)

    response = _test_client().get("/api/job-scans/active")

    assert response.status_code == 200
    assert response.json()["id"] == 42
    assert response.json()["status"] == "cancel_requested"
