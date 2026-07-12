from __future__ import annotations

from app.services import document_reader


def test_scanned_pdf_attempts_configured_ocr(monkeypatch):
    monkeypatch.setattr(document_reader, "_read_pypdf", lambda _: "")
    monkeypatch.setattr(
        document_reader,
        "_read_configured_ocr",
        lambda _: document_reader.OCRServiceResult(
            text="OCR text " * 20,
            confidence=0.91,
            engine="tesseract",
            pages=[{"page_number": 1, "confidence": 0.91}],
        ),
    )

    result = document_reader.read_pdf_document(b"scanned-pdf")

    assert result.method == "ocr_service"
    assert result.scanned_pdf_detected is True
    assert result.ocr_attempted is True
    assert result.ocr_confidence == 0.91
    assert result.page_evidence[0]["page_number"] == 1
    assert result.metadata()["parser_version"] == document_reader.PDF_PARSER_VERSION


def test_text_pdf_skips_ocr(monkeypatch):
    monkeypatch.setattr(document_reader, "_read_pypdf", lambda _: "Backend developer with Python and SQL. " * 10)
    monkeypatch.setattr(document_reader, "_read_configured_ocr", lambda _: (_ for _ in ()).throw(AssertionError("OCR should not run")))

    result = document_reader.read_pdf_document(b"text-pdf")

    assert result.method == "pypdf_layout"
    assert result.scanned_pdf_detected is False
    assert result.ocr_attempted is False


def test_ocr_page_text_is_not_duplicated_in_metadata():
    result = document_reader.DocumentReadResult(
        text="private cv text",
        method="ocr_service",
        scanned_pdf_detected=True,
        ocr_attempted=True,
        page_evidence=[{"page_number": 1, "confidence": 0.9, "word_count": 3, "text": "private cv text"}],
    )

    assert result.metadata()["ocr_pages"] == [{"page_number": 1, "confidence": 0.9, "word_count": 3}]
