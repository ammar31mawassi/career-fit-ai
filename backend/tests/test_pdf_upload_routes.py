from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api import routes


USER_ID = UUID("00000000-0000-0000-0000-000000000801")


class FakeUpload:
    def __init__(self, data: bytes, *, filename: str = "profile.pdf", content_type: str = "application/pdf"):
        self.data = data
        self.filename = filename
        self.content_type = content_type
        self.offset = 0
        self.read_sizes: list[int] = []
        self.file = self

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        assert size >= 0, "upload route attempted an unbounded read"
        chunk = self.data[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


UPLOAD_ENDPOINTS = (
    (routes.upload_cv, "upload_cv_source"),
    (routes.upload_linkedin_pdf, "upload_linkedin_pdf_source"),
)


@pytest.mark.parametrize(("endpoint", "service_name"), UPLOAD_ENDPOINTS)
@pytest.mark.parametrize(
    ("filename", "content_type", "data"),
    (
        ("profile.txt", "application/pdf", b"%PDF-valid"),
        ("profile.pdf", "text/plain", b"%PDF-valid"),
        ("profile.pdf", "application/pdf", b"not-a-pdf"),
    ),
)
def test_cv_and_linkedin_uploads_apply_identical_pdf_validation(
    monkeypatch,
    endpoint,
    service_name,
    filename,
    content_type,
    data,
):
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(max_upload_bytes=64))
    monkeypatch.setattr(
        routes,
        service_name,
        lambda *_args: pytest.fail("invalid upload reached durable profile storage"),
    )
    upload = FakeUpload(data, filename=filename, content_type=content_type)

    with pytest.raises(HTTPException) as raised:
        endpoint(upload, USER_ID, object())

    assert raised.value.status_code == 400


@pytest.mark.parametrize(("endpoint", "service_name"), UPLOAD_ENDPOINTS)
def test_uploads_buffer_at_most_limit_plus_one_byte(monkeypatch, endpoint, service_name):
    limit = 8
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(max_upload_bytes=limit))
    monkeypatch.setattr(
        routes,
        service_name,
        lambda *_args: pytest.fail("oversized upload reached durable profile storage"),
    )
    upload = FakeUpload(b"%PDF-" + b"x" * 100)

    with pytest.raises(HTTPException) as raised:
        endpoint(upload, USER_ID, object())

    assert raised.value.status_code == 413
    assert upload.offset == limit + 1
    assert all(size <= routes.UPLOAD_READ_CHUNK_BYTES for size in upload.read_sizes)


@pytest.mark.parametrize(("endpoint", "service_name"), UPLOAD_ENDPOINTS)
@pytest.mark.parametrize("content_type", ("application/pdf", "application/octet-stream"))
def test_valid_pdf_uploads_share_the_same_acceptance_policy(
    monkeypatch,
    endpoint,
    service_name,
    content_type,
):
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(max_upload_bytes=64))
    captured: dict[str, object] = {}

    def accept(session, user_id, filename, data):
        captured.update(session=session, user_id=user_id, filename=filename, data=data)
        return "accepted"

    monkeypatch.setattr(routes, service_name, accept)
    upload = FakeUpload(b"%PDF-valid", filename="PROFILE.PDF", content_type=content_type)

    result = endpoint(upload, USER_ID, object())

    assert result == "accepted"
    assert captured["user_id"] == USER_ID
    assert captured["filename"] == "PROFILE.PDF"
    assert captured["data"] == b"%PDF-valid"


@pytest.mark.parametrize(("endpoint", "service_name"), UPLOAD_ENDPOINTS)
def test_pdf_parse_errors_are_returned_as_bad_requests(monkeypatch, endpoint, service_name):
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(max_upload_bytes=64))
    monkeypatch.setattr(
        routes,
        service_name,
        lambda *_args: (_ for _ in ()).throw(ValueError("Uploaded PDF could not be parsed.")),
    )

    with pytest.raises(HTTPException) as raised:
        endpoint(FakeUpload(b"%PDF-broken"), USER_ID, object())

    assert raised.value.status_code == 400
    assert raised.value.detail == "Uploaded PDF could not be parsed."
