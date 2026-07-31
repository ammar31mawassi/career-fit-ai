from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as worker


def _asgi_request(
    *,
    headers: Iterable[tuple[bytes, bytes]],
    chunks: list[bytes] | None = None,
    path: str = worker.OCR_PATH,
    method: str = "POST",
    fail_on_receive: bool = False,
    block_on_receive: bool = False,
) -> tuple[int, dict[str, str], bytes, int]:
    async def call() -> tuple[int, dict[str, str], bytes, int]:
        messages: list[dict[str, object]] = []
        request_chunks = chunks or [b""]
        chunk_index = 0
        receive_calls = 0

        async def receive() -> dict[str, object]:
            nonlocal chunk_index, receive_calls
            receive_calls += 1
            if fail_on_receive:
                raise AssertionError("request body was read during preflight")
            if block_on_receive:
                await asyncio.Event().wait()
            if chunk_index >= len(request_chunks):
                return {"type": "http.disconnect"}
            body = request_chunks[chunk_index]
            chunk_index += 1
            return {
                "type": "http.request",
                "body": body,
                "more_body": chunk_index < len(request_chunks),
            }

        async def send(message: dict[str, object]) -> None:
            messages.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": "http",
            "method": method,
            "root_path": "",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": list(headers),
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "state": {},
        }
        await worker.app(scope, receive, send)

        start = next(message for message in messages if message["type"] == "http.response.start")
        response_headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in start.get("headers", [])
        }
        body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return int(start["status"]), response_headers, body, receive_calls

    return asyncio.run(call())


def _authorized_headers(*extra: tuple[bytes, bytes]) -> list[tuple[bytes, bytes]]:
    return [
        (b"authorization", b"Bearer worker-secret"),
        (b"content-type", b"application/pdf"),
        *extra,
    ]


@pytest.mark.parametrize(
    ("headers", "status", "code"),
    [
        (
            [
                (b"content-type", b"text/plain"),
                (b"content-length", b"999999999"),
            ],
            401,
            "OCR_UNAUTHORIZED",
        ),
        (
            [
                (b"authorization", b"Bearer worker-secret"),
                (b"content-type", b"text/plain"),
            ],
            415,
            "OCR_UNSUPPORTED_MEDIA_TYPE",
        ),
        (
            _authorized_headers((b"content-length", str(worker.MAX_BYTES + 1).encode("ascii"))),
            413,
            "OCR_BODY_TOO_LARGE",
        ),
        (
            _authorized_headers((b"content-length", b"+100")),
            400,
            "OCR_INVALID_LENGTH",
        ),
        (
            _authorized_headers(
                (b"content-length", b"4"),
                (b"transfer-encoding", b"chunked"),
            ),
            400,
            "OCR_INVALID_FRAMING",
        ),
    ],
)
def test_preflight_rejections_happen_before_reading_the_body(
    monkeypatch,
    headers,
    status,
    code,
):
    monkeypatch.setenv("OCR_WORKER_TOKEN", "worker-secret")

    actual_status, response_headers, body, receive_calls = _asgi_request(
        headers=headers,
        fail_on_receive=True,
    )

    assert actual_status == status
    assert json.loads(body)["code"] == code
    assert receive_calls == 0
    assert response_headers["cache-control"] == "no-store, private"
    assert response_headers["pragma"] == "no-cache"


def test_chunked_upload_is_rejected_as_soon_as_it_crosses_the_limit(monkeypatch):
    monkeypatch.setenv("OCR_WORKER_TOKEN", "worker-secret")
    monkeypatch.setattr(worker, "MAX_BYTES", 8)

    status, headers, body, receive_calls = _asgi_request(
        headers=_authorized_headers((b"transfer-encoding", b"chunked")),
        chunks=[b"%PDF-1.", b"4-over-limit"],
    )

    assert status == 413
    assert json.loads(body)["code"] == "OCR_BODY_TOO_LARGE"
    assert receive_calls == 2
    assert headers["cache-control"] == "no-store, private"


def test_overload_response_is_immediate_and_does_not_queue_or_read(monkeypatch):
    monkeypatch.setenv("OCR_WORKER_TOKEN", "worker-secret")
    occupied_slot = threading.BoundedSemaphore(1)
    occupied_slot.acquire()
    monkeypatch.setattr(worker, "_ocr_slots", occupied_slot)

    status, headers, body, receive_calls = _asgi_request(
        headers=_authorized_headers(),
        fail_on_receive=True,
    )

    assert status == 503
    assert json.loads(body)["code"] == "OCR_OVERLOADED"
    assert headers["retry-after"] == "2"
    assert headers["cache-control"] == "no-store, private"
    assert receive_calls == 0


def test_upload_time_counts_toward_the_aggregate_request_deadline(monkeypatch):
    monkeypatch.setenv("OCR_WORKER_TOKEN", "worker-secret")
    monkeypatch.setattr(worker, "REQUEST_TIMEOUT_SECONDS", 0.01)

    status, headers, body, receive_calls = _asgi_request(
        headers=_authorized_headers(),
        block_on_receive=True,
    )

    assert status == 504
    assert json.loads(body)["code"] == "OCR_DEADLINE_EXCEEDED"
    assert headers["cache-control"] == "no-store, private"
    assert receive_calls == 1


def test_success_and_route_errors_are_never_cacheable(monkeypatch):
    monkeypatch.setenv("OCR_WORKER_TOKEN", "worker-secret")
    monkeypatch.setattr(
        worker,
        "_process_pdf",
        lambda _data, _deadline: [
            worker.OCRPage(page_number=1, text="Senior engineer", confidence=0.98, word_count=2)
        ],
    )
    client = TestClient(worker.app)

    success = client.post(
        worker.OCR_PATH,
        content=b"%PDF-1.4\n",
        headers={
            "authorization": "Bearer worker-secret",
            "content-type": "application/pdf",
        },
    )
    invalid = client.post(
        worker.OCR_PATH,
        content=b"not a pdf",
        headers={
            "authorization": "Bearer worker-secret",
            "content-type": "application/pdf",
        },
    )
    wrong_method = client.get(worker.OCR_PATH)

    assert success.status_code == 200
    assert success.json()["text"] == "Senior engineer"
    assert success.headers["cache-control"] == "no-store, private"
    assert invalid.status_code == 400
    assert invalid.headers["cache-control"] == "no-store, private"
    assert wrong_method.status_code == 405
    assert wrong_method.headers["cache-control"] == "no-store, private"


@dataclass
class _Rect:
    width: float
    height: float


class _Page:
    def __init__(self, width: float, height: float) -> None:
        self.rect = _Rect(width, height)
        self.rasterized = False

    def get_pixmap(self, **_kwargs):
        self.rasterized = True
        raise AssertionError("hostile page was rasterized")


class _Document:
    def __init__(self, pages: list[_Page]) -> None:
        self.pages = pages
        self.page_count = len(pages)
        self.closed = False

    def load_page(self, index: int) -> _Page:
        return self.pages[index]

    def close(self) -> None:
        self.closed = True


def test_page_pixel_budget_rejects_before_pixmap_allocation(monkeypatch):
    page = _Page(101, 100)
    document = _Document([page])
    monkeypatch.setattr(worker, "DPI", 72)
    monkeypatch.setattr(worker, "MAX_PAGE_PIXELS", 10_000)
    monkeypatch.setattr(worker.fitz, "open", lambda **_kwargs: document)

    with pytest.raises(HTTPException) as caught:
        worker._process_pdf(b"%PDF", time.monotonic() + 10)

    assert caught.value.status_code == 413
    assert page.rasterized is False
    assert document.closed is True


def test_aggregate_pixel_budget_is_checked_before_any_page_is_rasterized(monkeypatch):
    pages = [_Page(100, 100), _Page(100, 100)]
    document = _Document(pages)
    monkeypatch.setattr(worker, "DPI", 72)
    monkeypatch.setattr(worker, "MAX_PAGE_PIXELS", 10_000)
    monkeypatch.setattr(worker, "MAX_TOTAL_PIXELS", 15_000)
    monkeypatch.setattr(worker.fitz, "open", lambda **_kwargs: document)

    with pytest.raises(HTTPException) as caught:
        worker._process_pdf(b"%PDF", time.monotonic() + 10)

    assert caught.value.status_code == 413
    assert all(page.rasterized is False for page in pages)
    assert document.closed is True


def test_request_deadline_is_aggregate_across_pages(monkeypatch):
    document = _Document([_Page(1, 1), _Page(1, 1)])
    clock = {"now": 0.0}
    monkeypatch.setattr(worker.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(worker.fitz, "open", lambda **_kwargs: document)
    monkeypatch.setattr(worker, "_validate_render_budget", lambda _document, _deadline: [1, 1])

    def slow_page(_page, page_number, deadline, _pixel_budget):
        worker._ensure_deadline(deadline)
        clock["now"] += 3
        worker._ensure_deadline(deadline)
        return worker.OCRPage(page_number, "", 0.0, 0)

    monkeypatch.setattr(worker, "_ocr_page", slow_page)

    with pytest.raises(HTTPException) as caught:
        worker._process_pdf(b"%PDF", deadline=5)

    assert caught.value.status_code == 504
    assert document.closed is True


def test_readiness_checks_languages_and_mupdf_without_user_input(monkeypatch):
    document = _Document([])
    created_pages: list[tuple[int, int]] = []

    def new_page(*, width: int, height: int) -> None:
        created_pages.append((width, height))

    document.new_page = new_page
    monkeypatch.setattr(worker, "LANGUAGES", "eng+heb")
    monkeypatch.setattr(worker.pytesseract, "get_languages", lambda config: ["eng", "heb", "osd"])
    monkeypatch.setattr(worker.fitz, "open", lambda: document)

    response = TestClient(worker.app).get("/ready")

    assert response.status_code == 200
    assert response.json()["languages"] == ["eng", "heb"]
    assert created_pages == [(72, 72)]
    assert document.closed is True
    assert response.headers["cache-control"] == "no-store, private"


def test_readiness_fails_closed_when_a_configured_language_is_missing(monkeypatch):
    monkeypatch.setattr(worker, "LANGUAGES", "eng+heb")
    monkeypatch.setattr(worker.pytesseract, "get_languages", lambda config: ["eng"])

    response = TestClient(worker.app).get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.headers["cache-control"] == "no-store, private"
