from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import JobDiscoveryBetaMember, JobSourceRun, SharedJobCatalog
from app.services.goozali import (
    GoozaliFetchResult,
    GoozaliJob,
    GoozaliSourceError,
    parse_shared_view,
)
from app.services.job_discovery import run_goozali_discovery


BETA_USER = UUID("00000000-0000-0000-0000-000000000301")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _column(column_id: str, name: str, choices: dict[str, str] | None = None) -> dict:
    payload = {"id": column_id, "name": name, "type": "text"}
    if choices:
        payload["typeOptions"] = {
            "choices": {
                choice_id: {"id": choice_id, "name": label}
                for choice_id, label in choices.items()
            }
        }
    return payload


def test_shared_view_parser_maps_job_fields_and_ignores_contact_fields():
    payload = {
        "data": {
            "table": {
                "columns": [
                    _column("title", "Job Title"),
                    _column("company", "Company"),
                    _column("description", "Job Description"),
                    _column("requirements", "Requirements"),
                    _column("field", "Field", {"software": "Software Engineering"}),
                    _column("location", "Location", {"tel_aviv": "Tel Aviv"}),
                    _column("scope", "Scope", {"full_time": "Full Time"}),
                    _column("link", "Position Link"),
                    _column("posted", "Posted"),
                    _column("email", "Email"),
                    _column("phone", "Phone"),
                ],
                "views": [{"rowOrder": [{"rowId": "rec-one", "visibility": True}]}],
                "rows": [
                    {
                        "id": "rec-one",
                        "createdTime": "2026-07-21T08:00:00.000Z",
                        "cellValuesByColumnId": {
                            "title": "Backend Engineer",
                            "company": "Example",
                            "description": "Build and operate a production API used by thousands of customers.",
                            "requirements": "Three years of Python, FastAPI, PostgreSQL, testing and cloud experience.",
                            "field": "software",
                            "location": ["tel_aviv"],
                            "scope": "full_time",
                            "link": "https://example.com/jobs/1",
                            "posted": "2026-07-21T00:00:00.000Z",
                            "email": "contact@example.com",
                            "phone": "+972-00-000-0000",
                        },
                    }
                ],
            }
        }
    }

    result = parse_shared_view(payload)

    assert result.records_seen == 1
    assert result.records_valid == 1
    assert result.jobs[0].career_field == "Software Engineering"
    assert result.jobs[0].location == "Tel Aviv"
    assert "Full Time" in result.jobs[0].description_text
    assert "contact@example.com" not in result.jobs[0].description_text
    assert "+972" not in result.jobs[0].description_text


def test_shared_view_parser_fails_closed_when_required_columns_change():
    payload = {"data": {"table": {"columns": [], "views": [{}], "rows": []}}}
    with pytest.raises(GoozaliSourceError, match="columns changed"):
        parse_shared_view(payload)


def test_discovery_is_recent_bounded_idempotent_and_enrolls_only_configured_users():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    now = datetime(2026, 7, 21, 10, tzinfo=timezone.utc)
    fresh = _job("fresh", now - timedelta(hours=1))
    second_fresh = _job("second", now - timedelta(hours=2))
    old = _job("old", now - timedelta(days=20))
    result = GoozaliFetchResult(jobs=[fresh, second_fresh, old], records_seen=3, records_valid=3)
    settings = SimpleNamespace(
        goozali_enabled=True,
        goozali_embed_url="https://example.invalid/embed",
        goozali_initial_lookback_hours=72,
        goozali_max_jobs_per_run=1,
        goozali_beta_user_ids=(BETA_USER,),
    )
    with Session(engine) as session:
        first = run_goozali_discovery(
            session,
            settings=settings,
            fetcher=lambda _url: result,
            now=now,
        )
        second = run_goozali_discovery(
            session,
            settings=settings,
            fetcher=lambda _url: result,
            now=now + timedelta(hours=1),
        )
        catalogs = list(session.exec(select(SharedJobCatalog)).all())
        member = session.get(JobDiscoveryBetaMember, BETA_USER)
        runs = list(session.exec(select(JobSourceRun)).all())

    assert first.created == 1
    assert first.ignored == 2
    assert second.created == 1
    assert {item.external_id for item in catalogs} == {"fresh", "second"}
    assert all(item.source_name == "goozali" for item in catalogs)
    assert member is not None and member.active and member.market_code == "IL"
    assert [run.status for run in runs] == ["completed", "completed"]


def test_disabled_discovery_does_not_call_the_external_source():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    settings = SimpleNamespace(
        goozali_enabled=False,
        goozali_embed_url="https://example.invalid/embed",
        goozali_initial_lookback_hours=72,
        goozali_max_jobs_per_run=1,
        goozali_beta_user_ids=(),
    )
    called = False

    def fetcher(_url):
        nonlocal called
        called = True
        raise AssertionError("disabled discovery fetched the source")

    with Session(engine) as session:
        outcome = run_goozali_discovery(session, settings=settings, fetcher=fetcher)

    assert outcome.status == "disabled"
    assert not called


def _job(external_id: str, discovered_at: datetime) -> GoozaliJob:
    return GoozaliJob(
        external_id=external_id,
        role="Backend Engineer",
        company="Example",
        career_field="Software Engineering",
        location="Tel Aviv",
        description_text=(
            "Build and operate production services. Requirements: Python, FastAPI, PostgreSQL, "
            "automated tests, cloud deployment, observability and collaborative delivery."
        ),
        source_url=f"https://goozali.com/jobs/{external_id}",
        application_link=f"https://example.com/jobs/{external_id}",
        source_published_at=discovered_at,
        discovered_at=discovered_at,
        source_confidence=0.92,
    )
