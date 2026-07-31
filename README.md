# Career Fit AI

Fresh MVP for profile-aware job matching.

Beta: https://career-fit-ai-sigma.vercel.app
API health: https://career-fit-ai-api.vercel.app/api/health

The beta does not use OpenAI, ChatGPT, or another hosted generative model. Profile extraction, job requirement classification, fit scoring, and resume About text run through versioned application-owned rules and templates in the FastAPI backend.

## Scope

- Public beta accounts through Supabase Auth, protected by atomic Postgres-backed signup/API rate limits.
- First-use onboarding plus authenticated Home and Profile pages.
- One required CV PDF.
- Optional GitHub, LinkedIn PDF/text, and manual notes.
- Editable career interests based on Goozali's public role taxonomy.
- Saved job scans with dedupe.
- Weighted fit model with hard penalties for must-have and experience mismatches.
- Versioned skill ontology, evidence strength, eligibility caps, and auditable score components.
- Twenty-four evidence-backed About templates selected by career stage and role family.
- Lead, Applied, Interview, Rejected, Withdrawn, and Offer outcome history.
- Resume advice for each job: projects, skill order, and a fitting About section.
- Cached JWKS token verification and a one-call workspace bootstrap for faster authenticated loading.
- Scanned-PDF detection with an optional private OCR fallback configured through `OCR_SERVICE_URL`.
- Browser-side OCR fallback when direct PDF text extraction is insufficient.
- Bulk profile fact confirmation/rejection with pending-first review.
- Immediate CV preview extraction, smooth progress, and early top-skill preselection while remaining sources are processed.
- A required confirm-or-skip review before onboarding completion, with evidence/confidence details for every pending fact, one priority clarification, and a career-direction preview.
- Twenty-four-hour cleanup of private sources and extracted preview data when onboarding is abandoned.
- Password recovery, private JSON export, account deletion, and a public privacy explanation.
- Abortable job scans with retained input and idempotent retry.
- Durable PGMQ-backed scan jobs with persisted progress, cancellation, stale-worker recovery, and bounded retries.
- User-reviewed job requirements that immediately recalculate the match and create privacy-safe evaluation labels.
- Opt-in community job recommendations using a cheap eligibility shortlist before full evidence scoring.
- An independent Goozali discovery beta for explicitly enrolled IL test accounts, with bounded imports, 65+ in-app suggestions, and optional 76+ email alerts.
- Cursor-paginated job summaries, ETags, explicit rematching, trace IDs, and privacy-safe extraction/onboarding-funnel metrics with no CV text, answers, or fact values.
- A replaceable scorer boundary with an optional monotonic calibration artifact; deterministic blockers and caps remain authoritative.

Out of scope for v1: broad Goozali rollout, Gmail, WhatsApp, automatic applications, multiple CVs, and LinkedIn scraping.

## Engineering records

- [Senior QA remediation](docs/QA_REMEDIATION_2026-07-13.md)
- [Senior full-stack product intelligence release](docs/SENIOR_FULLSTACK_RELEASE_2026-07-13.md)
- [Future product and engineering proposals](docs/CEO_FUTURE_IMPROVEMENTS.md)
- [UI, performance, and agent research plan](docs/CAREERFIT_UI_AI_RESEARCH_PLAN.md)
- [Goozali discovery beta operations](docs/GOOZALI_DISCOVERY_BETA.md)
- [Environment and scheduler preflight](docs/ENVIRONMENT_AND_SCHEDULER_PREFLIGHT.md)
- [Release and rollback](docs/RELEASE_AND_ROLLBACK.md)
- [Production operations and incident response](docs/OPERATIONS_RUNBOOK.md)
- [Data retention inventory](docs/DATA_RETENTION_INVENTORY.md)
- [Dependency and build policy](docs/DEPENDENCY_POLICY.md)
- [Ownership register](docs/OWNERSHIP.md)
- [Reference repository review and adaptations](docs/REFERENCE_REPOSITORY_ADAPTATION_2026-07-31.md)

## Local development

Use Python `3.12.13`, Node `22.16.0`, and npm `10.9.2` as recorded in the
repository toolchain files.

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`.

## Supabase setup

1. Create a Supabase project.
2. Run `supabase/schema.sql` in the Supabase SQL editor. This is the current
   fresh-install snapshot through database contract v24.
3. Create a private Storage bucket named `profile-documents`.
4. Keep email/password Auth enabled. The app signup route creates confirmed beta users and applies signup rate limits.
5. Put the project URL, anon key, service role key, backend API key, and allowed origins in Vercel/local env.
6. Set a sensitive `CRON_SECRET` on the backend deployment so Vercel Cron can recover abandoned queue work.

For an existing database, never rerun the base schema. Apply only migrations
that environment has not recorded, following the release order and naming
policy in [`supabase/migrations/README.md`](supabase/migrations/README.md).

Use the API project URL in the form `https://<project-ref>.supabase.co`, not the Supabase dashboard URL. Use a publishable key for browser/auth requests and a secret key only in backend/Vercel environment variables.

Contract v21 makes private document mutations backend/service-role mediated and
does not grant authenticated browsers direct Storage writes or deletes. Before
production, run the synthetic service-role and application Storage lifecycle
checks in the [environment preflight](docs/ENVIRONMENT_AND_SCHEDULER_PREFLIGHT.md).

The current Hobby deployment invokes recovery once per day because Hobby Cron does not support minute-level schedules. Normal scans start immediately from the authenticated client and continue in the persisted queue; move the same worker endpoint to a more frequent schedule when scan volume or the hosting plan increases.

Hourly Goozali discovery uses Supabase Cron to call the secured `/api/workers/discover` endpoint. The source is disabled by default and requires an explicit UUID allowlist. Email is a second opt-in and remains unavailable until Resend, a verified sender, and a dedicated unsubscribe-signing secret are configured. Follow the [scheduler preflight](docs/ENVIRONMENT_AND_SCHEDULER_PREFLIGHT.md) before enabling either path.

The same secured worker removes unfinished onboarding preview data after 24 hours, in batches of five per invocation. Completed profiles are never included in this cleanup.

Optional model calibration is enabled by setting `SCORE_CALIBRATION_PATH` to a JSON file with a version and monotonic score knots. If the file is absent or invalid, CareerFit safely uses the deterministic scorer.

Before training or enabling a calibration artifact, run `python scripts/label_coverage_report.py` from `backend/`. The privacy-safe report blocks the training gate when train, validation, or test labels are sparse and shows coverage by label type, fact/evidence segment, corrected requirement field, and model version.

To inspect onboarding drop-off without exporting user IDs or CV-derived content, run `python scripts/onboarding_funnel_report.py --days 30` from `backend/`. The report deduplicates stages by profile and returns aggregate conversion, choice, and drop-off counts only.

## Fit score meaning

The match percentage measures evidence alignment with a saved job posting. It is not a prediction that the user will receive an interview or offer. Confidence is reported separately and missing information creates clarification questions.

For local development without Supabase configured, the backend accepts a
development fallback user only when both `APP_ENV=development` and
`ENABLE_DEV_AUTH=true` are set. Production rejects the development-auth flag at
startup. The frontend auth screens still need Supabase environment values.

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm test
npm run typecheck
npm run build
npm audit --omit=dev --audit-level=high

cd ..\ocr-worker
..\backend\.venv\Scripts\python.exe -m pytest -q

cd ..
backend\.venv\Scripts\python.exe supabase\tests\run_postgres_security_tests.py
```

CI repeats these checks from exact locks and preserves dependency/SBOM evidence.
See [release and rollback](docs/RELEASE_AND_ROLLBACK.md) for production
promotion, migration, Storage, and rollback requirements.
