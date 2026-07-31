from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Profile, ProfileSource
from app.services import profile as profile_service
from app.services.document_reader import DocumentReadResult


USER_ID = UUID("00000000-0000-0000-0000-000000000802")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def _existing_source(session: Session, source_type: str) -> tuple[Profile, ProfileSource]:
    profile = Profile(
        user_id=USER_ID,
        status="ready",
        linkedin_text="Old LinkedIn text" if source_type == "linkedin_pdf" else "",
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    source = ProfileSource(
        user_id=USER_ID,
        profile_id=profile.id or 0,
        source_type=source_type,
        title="old.pdf",
        storage_path=f"{USER_ID}/{source_type}-old.pdf",
        content_text="Old private document text",
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return profile, source


def _read_result() -> DocumentReadResult:
    return DocumentReadResult(
        text="New private document text with Python and FastAPI experience. " * 3,
        method="pypdf_layout",
        scanned_pdf_detected=False,
        ocr_attempted=False,
    )


UPLOADERS = (
    (profile_service.upload_cv_source, "cv", "resume.pdf"),
    (profile_service.upload_linkedin_pdf_source, "linkedin_pdf", "linkedin.pdf"),
)


@pytest.mark.parametrize(("uploader", "source_type", "filename"), UPLOADERS)
def test_pdf_replacement_commits_new_object_before_cleaning_old(
    monkeypatch,
    uploader,
    source_type,
    filename,
):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    saved_names: list[str] = []
    deleted: list[tuple[str, UUID | None]] = []

    def save(user_id, storage_name, data, content_type):
        assert user_id == USER_ID
        assert data == b"%PDF-valid"
        assert content_type == "application/pdf"
        saved_names.append(storage_name)
        return f"{user_id}/{storage_name}"

    monkeypatch.setattr(profile_service, "read_pdf_document", lambda _data: _read_result())
    monkeypatch.setattr(profile_service, "save_private_file", save)
    monkeypatch.setattr(
        profile_service,
        "delete_private_file",
        lambda path, *, expected_user_id=None: deleted.append((path, expected_user_id)),
    )

    with Session(engine) as session:
        _, old_source = _existing_source(session, source_type)
        old_path = old_source.storage_path

        uploader(session, USER_ID, filename, b"%PDF-valid")
        persisted = session.exec(
            select(ProfileSource).where(ProfileSource.source_type == source_type)
        ).one()

    assert len(saved_names) == 1
    assert saved_names[0].startswith(
        "linkedin-" if source_type == "linkedin_pdf" else "cv-"
    )
    assert saved_names[0].endswith(f"-{filename}")
    assert persisted.storage_path == f"{USER_ID}/{saved_names[0]}"
    assert persisted.storage_path != old_path
    assert deleted == [(old_path, USER_ID)]


@pytest.mark.parametrize(("uploader", "source_type", "filename"), UPLOADERS)
def test_invalid_or_unparseable_pdf_never_reaches_durable_storage(
    monkeypatch,
    uploader,
    source_type,
    filename,
):
    del source_type
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(
        profile_service,
        "save_private_file",
        lambda *_args, **_kwargs: pytest.fail("invalid PDF was durably saved"),
    )

    with Session(engine) as session:
        with pytest.raises(ValueError, match="valid PDF"):
            uploader(session, USER_ID, filename, b"not-a-pdf")
        assert list(session.exec(select(Profile)).all()) == []

    monkeypatch.setattr(
        profile_service,
        "read_pdf_document",
        lambda _data: (_ for _ in ()).throw(RuntimeError("broken xref")),
    )
    with Session(engine) as session:
        with pytest.raises(ValueError, match="could not be parsed"):
            uploader(session, USER_ID, filename, b"%PDF-broken")
        assert list(session.exec(select(Profile)).all()) == []


def test_database_failure_removes_new_object_and_preserves_previous_source(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    deleted: list[tuple[str, UUID | None]] = []
    new_path = f"{USER_ID}/cv-new.pdf"
    monkeypatch.setattr(profile_service, "read_pdf_document", lambda _data: _read_result())
    monkeypatch.setattr(profile_service, "save_private_file", lambda *_args: new_path)
    monkeypatch.setattr(
        profile_service,
        "delete_private_file",
        lambda path, *, expected_user_id=None: deleted.append((path, expected_user_id)),
    )

    with Session(engine) as session:
        _, old_source = _existing_source(session, "cv")
        old_path = old_source.storage_path
        real_commit = session.commit
        monkeypatch.setattr(
            session,
            "commit",
            lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            profile_service.upload_cv_source(session, USER_ID, "resume.pdf", b"%PDF-valid")

        monkeypatch.setattr(session, "commit", real_commit)
        persisted = session.exec(select(ProfileSource).where(ProfileSource.source_type == "cv")).one()

    assert persisted.storage_path == old_path
    assert persisted.content_text == "Old private document text"
    assert deleted == [(new_path, USER_ID)]


def test_staging_failure_removes_new_object_and_preserves_previous_source(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    deleted: list[tuple[str, UUID | None]] = []
    new_path = f"{USER_ID}/cv-new.pdf"
    monkeypatch.setattr(profile_service, "read_pdf_document", lambda _data: _read_result())
    monkeypatch.setattr(profile_service, "save_private_file", lambda *_args: new_path)
    monkeypatch.setattr(
        profile_service,
        "record_onboarding_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("metric write failed")),
    )
    monkeypatch.setattr(
        profile_service,
        "delete_private_file",
        lambda path, *, expected_user_id=None: deleted.append((path, expected_user_id)),
    )

    with Session(engine) as session:
        _, old_source = _existing_source(session, "cv")
        old_path = old_source.storage_path

        with pytest.raises(RuntimeError, match="metric write failed"):
            profile_service.upload_cv_source(session, USER_ID, "resume.pdf", b"%PDF-valid")

        persisted = session.exec(select(ProfileSource).where(ProfileSource.source_type == "cv")).one()

    assert persisted.storage_path == old_path
    assert persisted.content_text == "Old private document text"
    assert deleted == [(new_path, USER_ID)]


def test_compensation_cleanup_failure_still_preserves_previous_source(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    new_path = f"{USER_ID}/cv-new.pdf"
    monkeypatch.setattr(profile_service, "read_pdf_document", lambda _data: _read_result())
    monkeypatch.setattr(profile_service, "save_private_file", lambda *_args: new_path)
    monkeypatch.setattr(
        profile_service,
        "delete_private_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("storage unavailable")),
    )

    with Session(engine) as session:
        _, old_source = _existing_source(session, "cv")
        old_path = old_source.storage_path
        real_commit = session.commit
        monkeypatch.setattr(
            session,
            "commit",
            lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            profile_service.upload_cv_source(session, USER_ID, "resume.pdf", b"%PDF-valid")

        monkeypatch.setattr(session, "commit", real_commit)
        persisted = session.exec(select(ProfileSource).where(ProfileSource.source_type == "cv")).one()

    assert persisted.storage_path == old_path
    assert persisted.content_text == "Old private document text"


def test_old_object_cleanup_failure_keeps_committed_new_source(monkeypatch):
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    new_path = f"{USER_ID}/cv-new.pdf"
    monkeypatch.setattr(profile_service, "read_pdf_document", lambda _data: _read_result())
    monkeypatch.setattr(profile_service, "save_private_file", lambda *_args: new_path)
    monkeypatch.setattr(
        profile_service,
        "delete_private_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("storage unavailable")),
    )

    with Session(engine) as session:
        _existing_source(session, "cv")

        profile_service.upload_cv_source(session, USER_ID, "resume.pdf", b"%PDF-valid")
        persisted = session.exec(select(ProfileSource).where(ProfileSource.source_type == "cv")).one()

    assert persisted.storage_path == new_path
    assert persisted.content_text.startswith("New private document text")
