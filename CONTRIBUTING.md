# Contributing to CareerFit

Last reviewed: 2026-07-30

CareerFit handles CV-derived personal data and authentication credentials.
Changes must preserve tenant ownership, explicit consent, evidence provenance,
and deletion behavior.

## Current contribution status

The project license and external contribution agreement are **not yet
selected**. External contributions should not be solicited or merged until the
legal/licensing owner resolves `THIRD_PARTY_NOTICES.md` and publishes the
applicable terms. Internal work may continue under the organization's existing
authorization.

## Toolchains

- Python `3.12.13` from `.python-version`
- Node `22.16.0` from `.nvmrc`
- npm `10.9.2` from `frontend/package.json`
- PostgreSQL 16 for the isolated schema/security harness
- Tesseract languages `eng`, `heb`, and `ara` for the OCR worker

Use exact checked-in lock files. Do not upgrade a package incidentally while
working on an unrelated change.

## Local verification

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend:

```powershell
cd frontend
npm ci
npm test
npm run typecheck
npm run build
npm audit --omit=dev --audit-level=high
```

OCR worker:

```powershell
cd ocr-worker
..\backend\.venv\Scripts\python.exe -m pytest -q
```

Database contract:

```powershell
backend\.venv\Scripts\python.exe supabase\tests\run_postgres_security_tests.py
```

The database harness requires the documented PostgreSQL image to be present
locally. It never targets a shared or production database.

## Pull-request expectations

- Explain user-visible behavior, failure behavior, privacy impact, and rollback.
- Add tests at the boundary changed. Authentication, ownership, uploads,
  deletion, migrations, and concurrency need hostile/negative cases.
- Keep logs free of CV text, profile facts, job-description bodies, emails,
  tokens, signed unsubscribe links, and provider response bodies.
- Never weaken a migration/RLS/Storage rule to make a SQLite test pass.
- Preserve user drafts and make destructive actions explicit and recoverable
  where the product contract allows it.
- Update `.env.example`, the preflight document, release runbook, and retention
  inventory when configuration or stored data changes.
- Complete `.github/pull_request_template.md`.

## Dependency changes

Follow `docs/DEPENDENCY_POLICY.md`. A dependency PR must include the direct
constraint change, regenerated exact locks, advisory and license review,
clean-environment tests, and updated SBOM/inventory evidence. PyMuPDF changes
also require the unresolved licensing decision to be revisited.

## Database changes

Never edit an already-applied migration. Add a new ordered migration, update the
fresh-install snapshot in the same change, test fresh and supported upgrade
paths, document deployment order, and prefer a forward fix over an unsafe down
migration. Follow `supabase/migrations/README.md`.
