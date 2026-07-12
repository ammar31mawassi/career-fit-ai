# Unlimited OCR evaluation

Date: 2026-07-12

## Decision

Do not send production CVs to the public `baidu/Unlimited-OCR` Hugging Face Space.
Keep the private-token Tesseract worker as the free production baseline. Revisit
Unlimited OCR when CareerFit has private GPU hosting or an approved private
inference endpoint.

## What was verified

- The model and repository use the MIT license.
- The original model is 3B parameters and 6.78 GB; the BF16 weight file alone is
  6.67 GB.
- Official inference loads the model on an NVIDIA GPU with CUDA and BF16.
- Hugging Face does not currently offer this model through an Inference Provider.
- Baidu's public demo runs on shared ZeroGPU infrastructure.
- A synthetic CV image was uploaded to the public demo only. OCR completed in
  approximately 24 seconds and recovered 9/9 expected fields.
- No real CV, candidate profile, or personal data was used in the benchmark.

## Why the public Space is not a production backend

- CVs contain personal data and would leave CareerFit's private storage boundary.
- The public demo is not controlled by CareerFit and provides no uptime or data
  retention guarantee for our users.
- ZeroGPU quota is caller-scoped and too small for multi-page beta traffic:
  unauthenticated callers receive 2 GPU minutes/day and free accounts receive
  5 GPU minutes/day.
- Each page can request up to 60 seconds of GPU time, so a few multi-page CVs can
  exhaust the daily allowance.
- Queue and cold-start latency can exceed the current synchronous upload window.

## Safe activation options

1. Host a private Unlimited OCR endpoint on GPU hardware and connect it through
   the existing `OCR_SERVICE_URL`/`OCR_SERVICE_TOKEN` boundary.
2. Host a private ZeroGPU Space under a Hugging Face PRO/Team account, enforce a
   service token, and document data retention. This is not a free-account option.
3. Run the Q4 GGUF model plus its F16 vision projector on controlled hardware.
   The quantized language model is about 1.82 GiB and the projector about 774 MiB,
   but it currently requires a DeepSeek-OCR-aware llama.cpp build that has not
   landed in the standard release.

## Acceptance gate before switching

- Private endpoint with authentication and no request logging.
- Page-level timeout and document-size limits.
- At least 30 scanned CV pages covering English, Hebrew, Arabic, columns, tables,
  low contrast, and mobile-camera scans.
- Compare character/field recall against Tesseract using expected facts, not just
  visually plausible output.
- Fall back to Tesseract on quota, timeout, or model failure.
- Never lower fact confidence merely because a generative OCR model returned
  fluent text; extracted facts still require evidence and user review.
