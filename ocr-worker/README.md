---
title: CareerFit OCR Worker
emoji: 📄
colorFrom: purple
colorTo: green
sdk: docker
app_port: 7860
---

# CareerFit OCR Worker

Private-token PDF OCR service for CareerFit. It converts each PDF page to an image in memory, runs Tesseract, and returns page-level text and confidence. Uploaded documents are never written to disk or logged.

## Runtime safeguards

- Authentication, media type, request framing, and declared size are checked
  before the request body is read.
- Streamed bodies are capped even when `Content-Length` is absent or inaccurate.
- Page count, per-page raster pixels, and aggregate raster pixels are checked
  before MuPDF allocates a page bitmap.
- The request deadline covers upload, PDF inspection, every page render, and
  Tesseract work. The per-page Tesseract timeout still applies as a tighter cap.
- OCR concurrency is bounded without an unbounded in-process queue. Saturated
  workers return `503 OCR_OVERLOADED` with `Retry-After`.
- OCR, health, readiness, and OCR-route error responses are marked `no-store`.

The image keeps its existing non-root runtime user. The supplied container
starts one Uvicorn process, so the concurrency limit is also the container-wide
limit.

## Health checks

- `GET /health` is a cheap liveness check.
- `GET /ready` verifies that every configured Tesseract language is installed
  and that MuPDF can create a blank document. It does not process user data.

Use `/ready` for deployment readiness and `/health` for liveness.

## Limits

| Variable | Default | Enforced range |
| --- | ---: | ---: |
| `OCR_MAX_BYTES` | 8 MiB | 1 byte–16 MiB |
| `OCR_MAX_PAGES` | 8 | 1–12 |
| `OCR_DPI` | 220 | 150–300 |
| `OCR_MAX_PAGE_PIXELS` | 20,000,000 | 1,000,000–50,000,000 |
| `OCR_MAX_TOTAL_PIXELS` | 50,000,000 | 1,000,000–200,000,000 |
| `OCR_PAGE_TIMEOUT_SECONDS` | 25 | 5–60 seconds |
| `OCR_REQUEST_TIMEOUT_SECONDS` | 75 | 10–180 seconds |
| `OCR_MAX_CONCURRENT_REQUESTS` | 1 | 1–4 |

Invalid or out-of-range numeric environment values fall back to the default or
are clamped to the documented hard limit.

## Hugging Face Space

1. Create a Docker Space on `cpu-basic`. Hugging Face currently requires PRO for
   newly created Gradio/Docker Spaces, even when the selected hardware is
   `cpu-basic`; only Static Spaces are available to free accounts.
2. Push this directory to the Space repository.
3. Add `OCR_WORKER_TOKEN` as a Space secret.
4. Optionally set `OCR_LANGUAGES=eng+heb+ara` and `OCR_MAX_PAGES=8` as variables.
5. Set CareerFit backend
   `OCR_SERVICE_URL=https://<space>.hf.space/v1/ocr/pdf`. Set
   `OCR_SERVICE_TOKEN` to the worker's `OCR_WORKER_TOKEN`; the token is a
   separate secret and must never be set to the URL.

CPU Basic Spaces sleep after inactivity, so the first scanned CV after a sleep can be slower. CareerFit only calls this worker when normal PDF text extraction is insufficient.

## Unlimited OCR evaluation

`baidu/Unlimited-OCR` was tested successfully on a synthetic CV, but its public
ZeroGPU demo is not used for production documents. It has shared daily quota and
would send private CV data to a third-party public Space. See
[`docs/UNLIMITED_OCR_EVALUATION.md`](../docs/UNLIMITED_OCR_EVALUATION.md) for the
benchmark and the requirements for a private GPU deployment.

## Local

```bash
docker build -t careerfit-ocr .
docker run --rm -p 7860:7860 -e OCR_WORKER_TOKEN=local-secret careerfit-ocr
```
