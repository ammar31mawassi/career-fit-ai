from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import (
    JobRecommendation,
    Profile,
    ProfileFactFeedback,
    ProfileSource,
    RecommendationEvent,
    SharedJobCatalog,
)
from app.services import account


USER_ID = UUID("00000000-0000-0000-0000-000000000701")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def test_account_export_contains_user_content_without_private_storage_paths():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="ready")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                storage_path=f"{USER_ID}/cv.pdf",
                content_text="B.Sc. Computer Science. Skills: Python.",
            )
        )
        session.add(
            ProfileFactFeedback(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                fact_type="skill",
                action="approved",
                original_value="python",
            )
        )
        catalog = SharedJobCatalog(content_hash="account-feedback-job", role="Backend Developer")
        session.add(catalog)
        session.flush()
        recommendation = JobRecommendation(
            user_id=USER_ID,
            catalog_job_id=catalog.id or 0,
            model_version="fit-v-test",
            score=44,
            fit_level="Weak",
            status="dismissed",
            career_fields_json='["Software Engineering"]',
        )
        session.add(recommendation)
        session.flush()
        session.add(
            RecommendationEvent(
                user_id=USER_ID,
                recommendation_id=recommendation.id or 0,
                catalog_job_id=catalog.id or 0,
                event_type="dismissed",
                dismiss_reason="too_senior",
                score=44,
                score_band="possible",
                career_field="Software Engineering",
                model_version="fit-v-test",
            )
        )
        session.commit()

        exported = account.export_account(session, USER_ID)

    payload = exported.model_dump(mode="json")
    assert payload["sources"][0]["content_text"].startswith("B.Sc.")
    assert "storage_path" not in payload["sources"][0]
    assert "storage_path" not in payload["profile"]["sources"][0]
    assert payload["fact_feedback"][0]["action"] == "approved"
    assert payload["recommendation_feedback"][0]["dismiss_reason"] == "too_senior"
    assert payload["recommendation_feedback"][0]["score_band"] == "possible"


def test_admin_account_deletion_uses_server_identity_headers(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        account,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://project.supabase.co",
            supabase_secret_key="sb_secret_test",
        ),
    )
    monkeypatch.setattr(account.urllib.request, "urlopen", urlopen)

    account._delete_supabase_auth_user(USER_ID)

    request = captured["request"]
    assert request.method == "DELETE"
    assert str(USER_ID) in request.full_url
    assert request.headers["User-agent"] == "careerfit-api/1.0"
    assert request.headers["Authorization"] == "Bearer sb_secret_test"
