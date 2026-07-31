# Changelog

This file records user, security, operations, schema, and compatibility changes.
Dated engineering reports remain historical evidence; they do not replace this
living changelog.

## 2026-07-31 — Beta hardening

### Added

- CI quality gates for backend, OCR, frontend, dependency audit, and PostgreSQL
  tenant-security contracts.
- Dependabot configuration and pinned GitHub Action revisions.
- Exact Python dependency closures, explicit Python/Node/npm toolchains, a
  frontend CycloneDX SBOM artifact, and Python dependency inventory artifacts.
- Living release/rollback, environment/scheduler, operations, retention,
  ownership, security, contribution, dependency, and third-party notice
  documents.
- Database contracts v18–v22 for clarification workflow states, tenant-safe
  foreign keys, durable scan claims, backend-mediated Storage, and validated
  JSON/workflow-state shapes.
- A temporary backend-only `BACKEND_API_KEY_NEXT` overlap for coordinated,
  zero-downtime internal-key rotation.

### Changed

- OCR builds use an explicit Python patch, Debian suite, and official base-image
  digest and record Tesseract package versions during image construction.
- Local setup uses exact locks (`pip install -r ...`, `npm ci`).
- Browser database mutations and document Storage writes now flow through the
  authenticated backend; browser roles retain only owner-scoped reads.
- Protected and public Next.js routes are separated and authenticated on the
  server, with bounded BFF forwarding and runtime response validation.
- Active job-scan deduplication includes the user's public-posting contribution
  choice so changing consent always creates a distinct request.

### Unresolved release gates

- Assign accountable owners and a private security-reporting channel.
- Choose the project license and resolve PyMuPDF commercial/AGPL obligations.
- Approve retention periods, recovery objectives, backup capabilities, and
  completed restore/deletion drill evidence.
- Produce hash-complete Linux/Python 3.12 locks and an immutable OCR native
  apt-package strategy.
- Produce formal backend/OCR SBOMs and verify final container scanning.

## 2026-07-13

- Product-intelligence release details are preserved in
  `docs/SENIOR_FULLSTACK_RELEASE_2026-07-13.md`.

## Changelog rules

- Add entries under `Unreleased` in the same pull request as the change.
- Record migrations, environment variables, processors, retention, scoring
  semantics, and rollback limitations explicitly.
- At release, move entries to a dated version tied to an immutable Git SHA and
  deployment identifiers. Do not rewrite prior release entries.
