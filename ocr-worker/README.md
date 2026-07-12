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

## Hugging Face Space

1. Create a Docker Space on `cpu-basic`. Hugging Face currently requires PRO for
   newly created Gradio/Docker Spaces, even when the selected hardware is
   `cpu-basic`; only Static Spaces are available to free accounts.
2. Push this directory to the Space repository.
3. Add `OCR_WORKER_TOKEN` as a Space secret.
4. Optionally set `OCR_LANGUAGES=eng+heb+ara` and `OCR_MAX_PAGES=8` as variables.
5. Set CareerFit backend `OCR_SERVICE_URL=https://<space>.hf.space/v1/ocr/pdf` and the same value as `OCR_SERVICE_TOKEN`.

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
