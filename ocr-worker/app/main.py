from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass

import fitz
import pytesseract
from fastapi import Body, FastAPI, Header, HTTPException, Response
from PIL import Image
from pytesseract import Output


MAX_BYTES = int(os.getenv("OCR_MAX_BYTES", str(8 * 1024 * 1024)))
MAX_PAGES = min(12, max(1, int(os.getenv("OCR_MAX_PAGES", "8"))))
DPI = min(300, max(150, int(os.getenv("OCR_DPI", "220"))))
LANGUAGES = os.getenv("OCR_LANGUAGES", "eng+heb+ara")
PAGE_TIMEOUT_SECONDS = min(60, max(5, int(os.getenv("OCR_PAGE_TIMEOUT_SECONDS", "25"))))

app = FastAPI(title="CareerFit OCR Worker", docs_url=None, redoc_url=None, openapi_url=None)


@dataclass(frozen=True)
class OCRPage:
    page_number: int
    text: str
    confidence: float
    word_count: int


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "engine": "tesseract", "languages": LANGUAGES, "max_pages": MAX_PAGES}


@app.post("/v1/ocr/pdf")
def ocr_pdf(
    response: Response,
    data: bytes = Body(media_type="application/pdf"),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    _authorize(authorization)
    if not data or not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Upload a valid PDF.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the OCR worker size limit.")

    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not open PDF.") from exc
    try:
        if document.page_count > MAX_PAGES:
            raise HTTPException(status_code=413, detail=f"PDF exceeds the {MAX_PAGES}-page OCR limit.")
        pages = [_ocr_page(document.load_page(index), index + 1) for index in range(document.page_count)]
    finally:
        document.close()

    text = "\n\n".join(page.text for page in pages if page.text).strip()
    confidences = [page.confidence for page in pages if page.word_count]
    response.headers["Cache-Control"] = "no-store, private"
    return {
        "text": text,
        "confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        "engine": "tesseract",
        "languages": LANGUAGES,
        "pages": [page.__dict__ for page in pages],
    }


def _authorize(authorization: str | None) -> None:
    expected = os.getenv("OCR_WORKER_TOKEN", "")
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Unauthorized.")


def _ocr_page(page: fitz.Page, page_number: int) -> OCRPage:
    scale = DPI / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    try:
        result = pytesseract.image_to_data(
            image,
            lang=LANGUAGES,
            config="--oem 1 --psm 6",
            output_type=Output.DICT,
            timeout=PAGE_TIMEOUT_SECONDS,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=504, detail=f"OCR timed out on page {page_number}.") from exc
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

