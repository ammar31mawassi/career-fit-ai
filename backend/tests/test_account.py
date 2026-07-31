from __future__ import annotations

from types import SimpleNamespace
import io
import urllib.error
from uuid import UUID

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.responses import Response

from app.api import routes
from app.models import (
    JobRecommendation,
    Profile,
    ProfileFactFeedback,
    ProfileSource,
    RecommendationEvent,
    SharedJobCatalog,
)
from app.services import account
from app.services import storage


USER_ID = UUID("00000000-0000-0000-0000-000000000701")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def test_account_export_response_is_private_and_not_cacheable(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(routes, "export_account", lambda _session, _user_id: sentinel)
    response = Response()

    result = routes.download_account_export(response, USER_ID, object())

    assert result is sentinel
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Content-Disposition"] == 'attachment; filename="careerfit-export.json"'


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


def test_admin_account_deletion_treats_an_already_missing_user_as_success(monkeypatch):
    monkeypatch.setattr(
        account,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://project.supabase.co",
            supabase_secret_key="sb_secret_test",
        ),
    )
    monkeypatch.setattr(
        account.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError(
                "https://project.supabase.co/auth/v1/admin/users/missing",
                404,
                "Not found",
                {},
                io.BytesIO(b'{"message":"not found"}'),
            )
        ),
    )

    account._delete_supabase_auth_user(USER_ID)


def test_account_deletion_route_does_not_expose_provider_errors(monkeypatch):
    monkeypatch.setattr(
        routes,
        "delete_account",
        lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Supabase Storage deletion failed: 500 secret-provider-detail")
        ),
    )

    with pytest.raises(routes.HTTPException) as raised:
        routes.remove_account(object(), USER_ID, object())

    assert raised.value.status_code == 503
    assert raised.value.detail == "Account deletion could not be completed. Try again."
    assert "secret-provider-detail" not in raised.value.detail


def test_account_deletion_removes_full_local_user_prefix_including_orphans(monkeypatch, tmp_path):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    other_user_id = UUID("00000000-0000-0000-0000-000000000702")
    settings = SimpleNamespace(
        supabase_url=None,
        supabase_secret_key=None,
        local_upload_dir=tmp_path,
    )
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    deleted_auth_users: list[UUID] = []
    monkeypatch.setattr(account, "_delete_supabase_auth_user", deleted_auth_users.append)

    referenced_path = storage.save_private_file(USER_ID, "cv.pdf", b"referenced", "application/pdf")
    orphan_path = storage.save_private_file(USER_ID, "orphan.pdf", b"unreferenced", "application/pdf")
    other_path = storage.save_private_file(other_user_id, "cv.pdf", b"other-user", "application/pdf")

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
                storage_path=referenced_path,
            )
        )
        session.commit()

        account.delete_account(session, USER_ID)

    assert deleted_auth_users == [USER_ID]
    assert storage.load_private_file(referenced_path, expected_user_id=USER_ID) is None
    assert storage.load_private_file(orphan_path, expected_user_id=USER_ID) is None
    assert storage.load_private_file(other_path, expected_user_id=other_user_id) == b"other-user"


def test_account_deletion_stops_before_auth_when_prefix_cleanup_fails(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(
        account,
        "delete_private_user_files",
        lambda _user_id: (_ for _ in ()).throw(RuntimeError("storage unavailable")),
    )
    monkeypatch.setattr(
        account,
        "_delete_supabase_auth_user",
        lambda _user_id: pytest.fail("auth user deleted after storage cleanup failed"),
    )

    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="ready")
        session.add(profile)
        session.commit()

        with pytest.raises(RuntimeError, match="storage unavailable"):
            account.delete_account(session, USER_ID)

        persisted = session.exec(select(Profile).where(Profile.user_id == USER_ID)).one()

    assert persisted.status == "ready"
