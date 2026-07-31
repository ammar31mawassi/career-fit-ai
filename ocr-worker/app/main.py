from __future__ import annotations

import asyncio
import hmac
import math
import os
import re
import threading
import time
from dataclasses import asdict, dataclass

import fitz
import pytesseract
from fastapi import Body, FastAPI, Header, HTTPException, Request, Response
from PIL import Image
from pytesseract import Output
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(maximum, max(minimum, value))


MAX_BYTES = _bounded_env_int("OCR_MAX_BYTES", 8 * 1024 * 1024, 1, 16 * 1024 * 1024)
MAX_PAGES = _bounded_env_int("OCR_MAX_PAGES", 8, 1, 12)
DPI = _bounded_env_int("OCR_DPI", 220, 150, 300)
LANGUAGES = os.getenv("OCR_LANGUAGES", "eng+heb+ara").strip()
PAGE_TIMEOUT_SECONDS = _bounded_env_int("OCR_PAGE_TIMEOUT_SECONDS", 25, 5, 60)
REQUEST_TIMEOUT_SECONDS = _bounded_env_int("OCR_REQUEST_TIMEOUT_SECONDS", 75, 10, 180)
MAX_PAGE_PIXELS = _bounded_env_int("OCR_MAX_PAGE_PIXELS", 20_000_000, 1_000_000, 50_000_000)
MAX_TOTAL_PIXELS = _bounded_env_int("OCR_MAX_TOTAL_PIXELS", 50_000_000, 1_000_000, 200_000_000)
MAX_CONCURRENT_REQUESTS = _bounded_env_int("OCR_MAX_CONCURRENT_REQUESTS", 1, 1, 4)

OCR_PATH = "/v1/ocr/pdf"
NO_STORE_HEADERS = (
    (b"cache-control", b"no-store, private"),
    (b"pragma", b"no-cache"),
    (b"x-content-type-options", b"nosniff"),
)

_ocr_slots = threading.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)
_api = FastAPI(title="CareerFit OCR Worker", docs_url=None, redoc_url=None, openapi_url=None)


@dataclass(frozen=True)
class OCRPage:
    page_number: int
    text: str
    confidence: float
    word_count: int


class _RequestBodyTooLarge(Exception):
    pass


class _RequestDeadlineExceeded(Exception):
    pass


class _InvalidRequestBody(Exception):
    pass


class OCRRequestGuard:
    """Reject unsafe OCR requests before the framework buffers their body."""

    def __init__(self, application: ASGIApp) -> None:
        self.application = application

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if path != OCR_PATH or scope.get("method") != "POST":
            await self.application(
                scope,
                receive,
                self._no_store_send(send)
                if path in {OCR_PATH, "/health", "/ready"}
                else send,
            )
            return

        rejection = self._preflight_rejection(scope)
        if rejection is not None:
            await rejection(scope, receive, self._no_store_send(send))
            return

        if not _ocr_slots.acquire(blocking=False):
            await self._error_response(
                503,
                "OCR worker is at capacity. Retry later.",
                "OCR_OVERLOADED",
                headers={"Retry-After": "2"},
            )(scope, receive, self._no_store_send(send))
            return

        deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
        scope["careerfit.ocr_deadline"] = deadline

        try:
            body = await self._receive_bounded_body(receive, deadline)
            content_length_values = self._headers(scope, b"content-length")
            if content_length_values and int(content_length_values[0]) != len(body):
                await self._error_response(
                    400,
                    "Content-Length does not match the request body.",
                    "OCR_INVALID_LENGTH",
                )(scope, receive, self._no_store_send(send))
                return

            body_pending = True

            async def replay_receive() -> Message:
                nonlocal body_pending
                if body_pending:
                    body_pending = False
                    return {"type": "http.request", "body": body, "more_body": False}
                return {"type": "http.disconnect"}

            await self.application(scope, replay_receive, self._no_store_send(send))
        except _RequestBodyTooLarge:
            await self._error_response(
                413,
                "PDF exceeds the OCR worker size limit.",
                "OCR_BODY_TOO_LARGE",
            )(scope, receive, self._no_store_send(send))
        except _RequestDeadlineExceeded:
            await self._error_response(
                504,
                "OCR request exceeded the processing deadline.",
                "OCR_DEADLINE_EXCEEDED",
            )(scope, receive, self._no_store_send(send))
        except _InvalidRequestBody:
            await self._error_response(
                400,
                "Request body was interrupted.",
                "OCR_INVALID_BODY",
            )(scope, receive, self._no_store_send(send))
        finally:
            _ocr_slots.release()

    @staticmethod
    async def _receive_bounded_body(receive: Receive, deadline: float) -> bytes:
        body = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _RequestDeadlineExceeded
            try:
                message = await asyncio.wait_for(receive(), timeout=remaining)
            except TimeoutError as exc:
                raise _RequestDeadlineExceeded from exc
            if time.monotonic() >= deadline:
                raise _RequestDeadlineExceeded
            if message["type"] == "http.disconnect":
                raise _InvalidRequestBody
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_BYTES:
                raise _RequestBodyTooLarge
            body.extend(chunk)
            if not message.get("more_body", False):
                return bytes(body)

    @staticmethod
    def _headers(scope: Scope, name: bytes) -> list[str]:
        return [
            value.decode("latin-1")
            for key, value in scope.get("headers", [])
            if key.lower() == name
        ]

    def _preflight_rejection(self, scope: Scope) -> JSONResponse | None:
        authorization_values = self._headers(scope, b"authorization")
        authorization = authorization_values[0] if len(authorization_values) == 1 else None
        try:
            _authorize(authorization)
        except HTTPException:
            return self._error_response(401, "Unauthorized.", "OCR_UNAUTHORIZED")

        content_type_values = self._headers(scope, b"content-type")
        if len(content_type_values) != 1:
            return self._error_response(
                415,
                "Content-Type must be application/pdf.",
                "OCR_UNSUPPORTED_MEDIA_TYPE",
            )
        media_type = content_type_values[0].split(";", 1)[0].strip().lower()
        if media_type != "application/pdf":
            return self._error_response(
                415,
                "Content-Type must be application/pdf.",
                "OCR_UNSUPPORTED_MEDIA_TYPE",
            )

        content_length_values = self._headers(scope, b"content-length")
        if len(content_length_values) > 1:
            return self._error_response(400, "Invalid Content-Length header.", "OCR_INVALID_LENGTH")
        transfer_encoding_values = self._headers(scope, b"transfer-encoding")
        if (
            len(transfer_encoding_values) > 1
            or (transfer_encoding_values and transfer_encoding_values[0].strip().lower() != "chunked")
            or (transfer_encoding_values and content_length_values)
        ):
            return self._error_response(
                400,
                "Invalid request body framing.",
                "OCR_INVALID_FRAMING",
            )
        if content_length_values:
            raw_content_length = content_length_values[0]
            if not raw_content_length.isascii() or not raw_content_length.isdecimal():
                return self._error_response(400, "Invalid Content-Length header.", "OCR_INVALID_LENGTH")
            try:
                content_length = int(raw_content_length)
            except ValueError:
                return self._error_response(400, "Invalid Content-Length header.", "OCR_INVALID_LENGTH")
            if content_length > MAX_BYTES:
                return self._error_response(
                    413,
                    "PDF exceeds the OCR worker size limit.",
                    "OCR_BODY_TOO_LARGE",
                )
        return None

    @staticmethod
    def _error_response(
        status_code: int,
        detail: str,
        code: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> JSONResponse:
        return JSONResponse(
            {"detail": detail, "code": code},
            status_code=status_code,
            headers=headers,
        )

    @staticmethod
    def _no_store_send(send: Send) -> Send:
        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in {b"cache-control", b"pragma", b"x-content-type-options"}
                ]
                message = {**message, "headers": [*headers, *NO_STORE_HEADERS]}
            await send(message)

        return wrapped


@_api.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "engine": "tesseract", "max_pages": MAX_PAGES}


@_api.get("/ready", response_model=None)
def readiness() -> dict[str, object] | JSONResponse:
    try:
        return _readiness_check()
    except Exception:
        return JSONResponse(
            {
                "status": "not_ready",
                "detail": "OCR runtime dependencies are unavailable or incomplete.",
            },
            status_code=503,
        )


@_api.post(OCR_PATH)
def ocr_pdf(
    request: Request,
    response: Response,
    data: bytes = Body(media_type="application/pdf"),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    # The outer ASGI guard performs this check before receiving the body; retain
    # a second check here so direct invocation cannot bypass authorization.
    _authorize(authorization)
    deadline = float(
        request.scope.get("careerfit.ocr_deadline")
        or (time.monotonic() + REQUEST_TIMEOUT_SECONDS)
    )
    _ensure_deadline(deadline)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the OCR worker size limit.")
    if not data or not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Upload a valid PDF.")

    pages = _process_pdf(data, deadline)
    text = "\n\n".join(page.text for page in pages if page.text).strip()
    confidences = [page.confidence for page in pages if page.word_count]
    response.headers["Cache-Control"] = "no-store, private"
    return {
        "text": text,
        "confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        "engine": "tesseract",
        "languages": LANGUAGES,
        "pages": [asdict(page) for page in pages],
    }


def _authorize(authorization: str | None) -> None:
    expected = os.getenv("OCR_WORKER_TOKEN", "")
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Unauthorized.")


def _readiness_check() -> dict[str, object]:
    configured_languages = tuple(language for language in LANGUAGES.split("+") if language)
    if not configured_languages:
        raise RuntimeError("No OCR languages are configured.")
    available_languages = set(pytesseract.get_languages(config=""))
    missing_languages = sorted(set(configured_languages) - available_languages)
    if missing_languages:
        raise RuntimeError("Configured OCR languages are unavailable.")
    document = fitz.open()
    try:
        document.new_page(width=72, height=72)
    finally:
        document.close()
    return {
        "status": "ready",
        "engine": "tesseract",
        "languages": list(configured_languages),
        "mupdf": str(fitz.VersionBind),
        "capacity": MAX_CONCURRENT_REQUESTS,
    }


def _process_pdf(data: bytes, deadline: float) -> list[OCRPage]:
    _ensure_deadline(deadline)
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not open PDF.") from exc
    try:
        _ensure_deadline(deadline)
        if document.page_count > MAX_PAGES:
            raise HTTPException(status_code=413, detail=f"PDF exceeds the {MAX_PAGES}-page OCR limit.")
        pixel_budgets = _validate_render_budget(document, deadline)
        pages = [
            _ocr_page(document.load_page(index), index + 1, deadline, pixel_budgets[index])
            for index in range(document.page_count)
        ]
        _ensure_deadline(deadline)
        return pages
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not process PDF.") from exc
    finally:
        document.close()


def _validate_render_budget(document: fitz.Document, deadline: float) -> list[int]:
    pixel_budgets: list[int] = []
    total_pixels = 0
    scale = DPI / 72
    for index in range(document.page_count):
        _ensure_deadline(deadline)
        page = document.load_page(index)
        width = float(page.rect.width)
        height = float(page.rect.height)
        if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
            raise HTTPException(status_code=400, detail=f"Page {index + 1} has invalid dimensions.")
        scaled_width = width * scale
        scaled_height = height * scale
        if not math.isfinite(scaled_width) or not math.isfinite(scaled_height):
            raise HTTPException(
                status_code=413,
                detail=f"Page {index + 1} exceeds the OCR raster limit.",
            )
        pixels = math.ceil(scaled_width) * math.ceil(scaled_height)
        if pixels > MAX_PAGE_PIXELS:
            raise HTTPException(
                status_code=413,
                detail=f"Page {index + 1} exceeds the OCR raster limit.",
            )
        total_pixels += pixels
        if total_pixels > MAX_TOTAL_PIXELS:
            raise HTTPException(status_code=413, detail="PDF exceeds the aggregate OCR raster limit.")
        pixel_budgets.append(pixels)
    return pixel_budgets


def _ensure_deadline(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise HTTPException(status_code=504, detail="OCR request exceeded the processing deadline.")
    return remaining


def _ocr_page(page: fitz.Page, page_number: int, deadline: float, pixel_budget: int) -> OCRPage:
    _ensure_deadline(deadline)
    scale = DPI / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
    actual_pixels = pixmap.width * pixmap.height
    if actual_pixels > pixel_budget or actual_pixels > MAX_PAGE_PIXELS:
        raise HTTPException(status_code=413, detail=f"Page {page_number} exceeds the OCR raster limit.")
    _ensure_deadline(deadline)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    del pixmap
    try:
        timeout = min(float(PAGE_TIMEOUT_SECONDS), _ensure_deadline(deadline))
        result = pytesseract.image_to_data(
            image,
            lang=LANGUAGES,
            config="--oem 1 --psm 6",
            output_type=Output.DICT,
            timeout=timeout,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=504, detail=f"OCR timed out on page {page_number}.") from exc
    finally:
        image.close()
    _ensure_deadline(deadline)
    return _page_from_tesseract(page_number, result)


def _page_from_tesseract(page_number: int, result: dict[str, list[object]]) -> OCRPage:
    lines: dict[tuple[int, int, int], list[str]] = {}
    confidences: list[float] = []
    texts = result.get("text", [])
    for index, raw in enumerate(texts):
        token = re.sub(r"\s+", " ", str(raw)).strip()
        if not token:
            continue
        try:
            confidence = float(result.get("conf", [])[index])
        except (IndexError, TypeError, ValueError):
            confidence = -1
        if confidence >= 0:
            confidences.append(confidence / 100)
        key = (
            int(result.get("block_num", [0] * len(texts))[index]),
            int(result.get("par_num", [0] * len(texts))[index]),
            int(result.get("line_num", [0] * len(texts))[index]),
        )
        lines.setdefault(key, []).append(token)
    text = "\n".join(" ".join(tokens) for tokens in lines.values()).strip()
    return OCRPage(
        page_number=page_number,
        text=text,
        confidence=round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        word_count=len(confidences),
    )


app = OCRRequestGuard(_api)
