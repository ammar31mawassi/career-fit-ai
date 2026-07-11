from __future__ import annotations

from app.services import document_reader


def test_scanned_pdf_attempts_configured_ocr(monkeypatch):
    monkeypatch.setattr(document_reader, "_read_pypdf", lambda _: "")
    monkeypatch.setattr(document_reader, "_read_configured_ocr", lambda _: "OCR text " * 20)

    result = document_reader.read_pdf_document(b"scanned-pdf")

    assert result.method == "ocr_service"
    assert result.scanned_pdf_detected is True
    assert result.ocr_attempted is True
    assert result.metadata()["parser_version"] == document_reader.PDF_PARSER_VERSION


def test_text_pdf_skips_ocr(monkeypatch):
    monkeypatch.setattr(document_reader, "_read_pypdf", lambda _: "Backend developer with Python and SQL. " * 10)
    monkeypatch.setattr(document_reader, "_read_configured_ocr", lambda _: (_ for _ in ()).throw(AssertionError("OCR should not run")))

    result = document_reader.read_pdf_document(b"text-pdf")

    assert result.method == "pypdf_layout"
    assert result.scanned_pdf_detected is False
    assert result.ocr_attempted is False
