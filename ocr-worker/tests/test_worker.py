from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import _authorize, _page_from_tesseract, app


def test_worker_requires_constant_time_bearer_secret(monkeypatch):
    monkeypatch.setenv("OCR_WORKER_TOKEN", "worker-secret")
    _authorize("Bearer worker-secret")

    with pytest.raises(HTTPException) as caught:
        _authorize("Bearer wrong")

    assert caught.value.status_code == 401


def test_pdf_endpoint_rejects_unauthenticated_requests(monkeypatch):
    monkeypatch.setenv("OCR_WORKER_TOKEN", "worker-secret")
    response = TestClient(app).post(
        "/v1/ocr/pdf",
        content=b"%PDF-1.4\n",
        headers={"content-type": "application/pdf"},
    )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")


def test_tesseract_tokens_are_grouped_by_page_line():
    page = _page_from_tesseract(
        2,
        {
            "text": ["Python", "FastAPI", "", "PostgreSQL"],
            "conf": ["96", "88", "-1", "91"],
            "block_num": [1, 1, 1, 1],
            "par_num": [1, 1, 1, 1],
            "line_num": [1, 1, 1, 2],
        },
    )

    assert page.page_number == 2
    assert page.text == "Python FastAPI\nPostgreSQL"
    assert page.word_count == 3
    assert page.confidence == pytest.approx(0.917, abs=0.001)
