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
from app.services.goozali_reader import GOOZALI_READER_VERSION, classify_goozali_job
from app.services.job_discovery import run_goozali_discovery
from app.services.job_research import requirements_from_json


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
                    _column("language", "Language requirement", {"english": "English"}),
                    _column("education", "Education requirements"),
                    _column("experience", "Min Experience (Y)"),
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
                            "description": "Build and operate a production API used by thousands of customers. Contact recruiter@example.com or +972-50-123-4567.",
                            "requirements": "Three years of Python, FastAPI, PostgreSQL, testing and cloud experience.",
                            "field": "software",
                            "location": ["tel_aviv"],
                            "scope": "full_time",
                            "language": "english",
                            "education": "BSc in Computer Science",
                            "experience": 3,
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
    assert result.jobs[0].employment_scope == "Full Time"
    assert result.jobs[0].language_requirements == "English"
    assert result.jobs[0].education_requirements == "BSc in Computer Science"
    assert result.jobs[0].minimum_experience == "3"
    assert "Full Time" in result.jobs[0].description_text
    assert "contact@example.com" not in result.jobs[0].description_text
    assert "+972" not in result.jobs[0].description_text
    assert "recruiter@example.com" not in result.jobs[0].description_text
    assert "[contact email removed]" in result.jobs[0].description_text
    assert "[contact phone removed]" in result.jobs[0].description_text


def test_goozali_reader_uses_structured_experience_and_sr_title():
    job = GoozaliJob(
        external_id="structured-reader",
        role="API Security Sr. Product Manager",
        company="Akamai",
        career_field="Product Management",
        location="Israel",
        description_text=(
            "Own internal tools and work with API security teams.\n\n"
            "Employment scope: Full Time\nLocation: Israel\nMinimum experience: 5 years"
        ),
        source_url="https://goozali.com/#jobopenings",
        application_link="https://example.com/jobs/product",
        source_published_at=None,
        discovered_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        source_confidence=0.92,
        employment_scope="Full Time",
        minimum_experience="5",
    )

    requirements = classify_goozali_job(job)

    assert requirements.min_years_experience == 5
    assert requirements.experience_requirement_known is True
    assert requirements.seniority == "senior"
    assert requirements.availability == "full-time"
    assert requirements.reader_version == GOOZALI_READER_VERSION


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


def test_discovery_persists_goozali_reader_output_and_primary_field():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    now = datetime(2026, 7, 21, 10, tzinfo=timezone.utc)
    job = GoozaliJob(
        external_id="structured-product",
        role="API Security Sr. Product Manager",
        company="Akamai",
        career_field="Product Management",
        location="Israel",
        description_text=(
            "Own internal tools and vendor processes while partnering with engineering and security teams. "
            "Define the roadmap, success metrics, delivery priorities, and product requirements."
        ),
        source_url="https://goozali.com/#jobopenings",
        application_link="https://example.com/jobs/product",
        source_published_at=now,
        discovered_at=now,
        source_confidence=0.92,
        employment_scope="Full Time",
        minimum_experience="5",
    )
    result = GoozaliFetchResult(jobs=[job], records_seen=1, records_valid=1)
    settings = SimpleNamespace(
        goozali_enabled=True,
        goozali_embed_url="https://example.invalid/embed",
        goozali_initial_lookback_hours=72,
        goozali_max_jobs_per_run=10,
        goozali_beta_user_ids=(),
    )

    with Session(engine) as session:
        run_goozali_discovery(session, settings=settings, fetcher=lambda _url: result, now=now)
        catalog = session.exec(select(SharedJobCatalog)).one()

    requirements = requirements_from_json(catalog.requirements_json)
    assert requirements.min_years_experience == 5
    assert requirements.seniority == "senior"
    assert requirements.reader_version == GOOZALI_READER_VERSION
    assert catalog.career_fields_json == '["Product Management"]'


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
