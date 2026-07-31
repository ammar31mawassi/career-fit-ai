# Environment and scheduler preflight

Status: required checklist; environment evidence not yet attached
Last reviewed: 2026-07-31
Database contract: v24

Run this checklist in staging before production. Store pass/fail evidence with
the release; never copy secret values into the evidence.

## Environment separation

Development, test, staging, and production must use separate Supabase projects,
Storage buckets, auth users, scheduler secrets, Resend configuration, and
deployment variables. A staging smoke must never point at production through a
copied `DATABASE_URL`, `SUPABASE_URL`, `BACKEND_API_URL`, or `PUBLIC_API_URL`.

Production must set:

- `APP_ENV=production`
- `ENABLE_DEV_AUTH=false`
- a unique `BACKEND_API_KEY` of at least 32 characters
- production Supabase URL, anon/publishable key, and backend-only secret key
- exact frontend/backend origins and public URLs
- a unique `CRON_SECRET`

Startup rejects the most important missing production auth values. The preflight
still needs to catch cross-environment values, provider state, schedules, and
feature dependencies that syntax validation cannot prove.

## Synthetic application smoke

`backend/scripts/production_smoke.py` is deliberately staging-only despite its
historical filename. It refuses any `SMOKE_TARGET_ENV` other than `staging`,
requires explicit HTTPS frontend/backend/Supabase origins, and never loads
implicit local or production defaults. Configure only the `SMOKE_*` variables
listed in `.env.example`, then run:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\production_smoke.py
```

The journey creates a confirmed, marked synthetic Auth user through the staging
admin API, uploads and analyzes a synthetic PDF, completes the current review
contract, checks the repository's current scorer version, updates and searches
a job, and deletes the account through the backend. Promotion fails unless the
Auth user is absent and the complete Storage prefix lists empty afterward. A
cleanup failure prints only the synthetic user ID needed for an immediate
retry; do not continue promotion.

## Configuration inventory

| Variable | Scope | Secret | Required/condition | Preflight |
| --- | --- | --- | --- | --- |
| `APP_ENV` | Backend | No | Always; production must be explicit | Equals intended environment |
| `ENABLE_DEV_AUTH` | Backend | No | Development/test only | False or absent outside development/test |
| `BACKEND_API_KEY` | Backend + frontend server | Yes | Production | Same value on BFF/backend; unique, 32+ chars |
| `BACKEND_API_KEY_NEXT` | Backend only | Yes | Key rotation only | Strong temporary overlap; remove after frontend and backend use the new primary key |
| `DATABASE_URL` | Backend | Yes | Always | Correct project/region; TLS/provider settings verified |
| `DATABASE_POOL_SIZE` | Backend | No | Optional integer, minimum 1 | Fits serverless/provider connection budget |
| `DATABASE_MAX_OVERFLOW` | Backend | No | Optional integer, minimum 0 | Fits serverless/provider connection budget |
| `ALLOWED_ORIGINS` | Backend | No | Production | Exact HTTPS frontend origins only; no wildcard |
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend | No | Auth | Correct project API URL, not dashboard URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend | Publishable | Auth | Publishable/anon key only |
| `SUPABASE_URL` | Backend | No | Production | Same intended project as auth/database |
| `SUPABASE_ANON_KEY` | Backend | Publishable | Token verification fallback | Correct project |
| `SUPABASE_SECRET_KEY` | Backend/frontend server signup | Yes | Production operations | Server-only; never `NEXT_PUBLIC_*` |
| `SUPABASE_STORAGE_BUCKET` | Backend | No | Uploads | Private `profile-documents` unless deliberately changed |
| `LOCAL_UPLOAD_DIR` | Local backend | No | Local fallback only | Not relied on in production serverless |
| `MAX_UPLOAD_BYTES` | Backend | No | Optional integer | At or below upstream/request limits |
| `OCR_SERVICE_URL` | Backend | No | Optional OCR | Full endpoint ending `/v1/ocr/pdf`, not only host |
| `OCR_SERVICE_TOKEN` | Backend | Yes | When OCR URL set | Equals worker `OCR_WORKER_TOKEN`; not the URL |
| `GITHUB_TOKEN` | Backend | Yes | Optional GitHub enrichment | Least scope; omit when unused |
| `CRON_SECRET` | Backend + scheduler Vault | Yes | Worker endpoints | Unique; same value at scheduler/backend |
| `SCORE_CALIBRATION_PATH` | Backend | No | Optional calibration | Immutable reviewed artifact exists in deployment |
| `FRONTEND_URL` | Backend | No | Links/notifications | Canonical HTTPS frontend origin |
| `PUBLIC_API_URL` | Backend | No | Unsubscribe links | Canonical HTTPS backend origin |
| `BACKEND_API_URL` | Frontend server | No | BFF | Private/canonical backend base URL |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend | No | Optional | Normally same-origin `/backend` |
| `NEXT_PUBLIC_SITE_URL` | Frontend | No | Auth redirects | Exact canonical HTTPS site origin |
| `GOOZALI_DISCOVERY_ENABLED` | Backend | No | Optional beta | False until every dependency below passes |
| `GOOZALI_EMBED_URL` | Backend | No | Goozali beta | Reviewed public source URL |
| `GOOZALI_INITIAL_LOOKBACK_HOURS` | Backend | No | Goozali beta | Positive integer |
| `GOOZALI_MAX_JOBS_PER_RUN` | Backend | No | Goozali beta | Positive bounded integer |
| `GOOZALI_BETA_USER_IDS` | Backend | Sensitive IDs | Goozali beta | Explicit valid UUID allowlist; no inferred membership |
| `RESEND_API_KEY` | Backend | Yes | Email alerts | Server-only provider key |
| `NOTIFICATION_FROM_EMAIL` | Backend | No | Email alerts | Verified sender/domain |
| `NOTIFICATION_SIGNING_SECRET` | Backend | Yes | Email alerts | Independent random secret; never reuse cron/API key |

`SUPABASE_SERVICE_ROLE_KEY` remains a supported compatibility alias for
`SUPABASE_SECRET_KEY`, but new environments should use one documented name
consistently.

OCR worker variables and enforced ranges are documented in
`ocr-worker/README.md`. The worker token is always required for OCR requests.

## Database and Storage v21

For a fresh project, apply `supabase/schema.sql`, currently through v24. For an
existing project, apply only unapplied migrations in the recorded release order and follow
`supabase/migrations/README.md`.

Before applying v21 in production:

1. deploy/configure the backend path that writes Storage with the service role;
2. verify the bucket is private and the backend secret is not browser-visible;
3. run the service-role smoke below in staging;
4. apply v21, which keeps browser reads governed by ownership while revoking
   direct authenticated browser writes/deletes;
5. rerun the service-role smoke and an application upload/read/delete journey;
6. verify a direct authenticated browser upload/delete is denied.

### Real service-role Storage smoke

Run from a protected staging job that masks secrets and disables command
tracing. Use a unique synthetic object such as
`preflight/<release-id>/<random-id>.pdf`; never use a real CV.

1. Create a minimal synthetic PDF and record its SHA-256.
2. Upload it to
   `POST {SUPABASE_URL}/storage/v1/object/{bucket}/{object}` with both `apikey`
   and `Authorization: Bearer ...` set to the staging service-role/secret key.
3. Read it from
   `GET {SUPABASE_URL}/storage/v1/object/{bucket}/{object}` with the same
   backend-only authorization. Require HTTP 200, PDF content type, exact byte
   length, and matching SHA-256.
4. Delete it through
   `DELETE {SUPABASE_URL}/storage/v1/object/{bucket}/{object}` with the same
   authorization.
5. Read it again and require a not-found response. Query Storage metadata and
   confirm no object with the unique path remains.
6. Preserve only timestamps, status codes, object prefix/random identifier, and
   hashes. Do not preserve the key or response headers containing credentials.

Then execute the real application path with a synthetic beta account: upload,
analyze/read, replace if supported, and delete the account. Confirm that the
entire user UUID prefix is gone, including multi-page listings.

**Rollback caveat:** do not undo v21 by restoring broad authenticated Storage
write/delete privileges merely to roll back application code. That would reopen
the browser write boundary. Roll back only to a backend version that still uses
the service-role-mediated path; otherwise stop uploads and issue a reviewed
forward migration. Database restores also do not automatically prove Storage
object restoration or deletion.

### Data-contract v22 preflight

Before applying v22, restore the latest production backup into an isolated
PostgreSQL environment and apply the migration there. The migration validates
every existing structured-text payload as the expected JSON object or array and
rejects unknown `agent_runs`/`agent_steps` states. A failure is a release stop:
identify and quarantine or transform the incompatible rows, record the approved
mapping, then repeat the restore-and-migrate rehearsal. Do not weaken the
constraints or coerce malformed values to empty JSON merely to make deployment
pass.

After applying v22, run the repository PostgreSQL harness and one real staging
job-analysis/scan/recommendation journey. Roll back application code only to a
version that writes the same JSON shapes and workflow states; the schema change
is forward-only.

### Application-event v23 preflight

Before applying v23, inspect `job_status_events` for statuses outside the
current application-stage enum and notes longer than 500 characters. Rehearse
the migration against a restored staging database: existing events must receive
their previous status in audit order, `occurred_at` must backfill from
`created_at`, and their source must be `legacy`. A failed constraint or
unexpected row count is a release stop.

After applying v23, record one synthetic backdated stage transition through the
API. Confirm that the current match changes, the append-only event retains both
the observed time and database creation time, another tenant cannot read it,
and repeating the same target stage does not append a duplicate event. Roll
back application code only to a version that tolerates the new non-null event
columns; the migration itself is forward-only.

Apply v23 and v24 before deploying this backend, then deploy the frontend only
after the expanded backend contract is healthy. Minimize the interval between
migration and backend deployment, or pause stage-change writes during it: the
older backend remains schema-compatible, but it cannot populate the new
`previous_status` context for events created in that interval.

### Source-health v24 preflight

Before applying v24, confirm existing `job_source_runs.status` values are within
`running`, `completed`, `failed`, or `disabled`, and rehearse the constraint
replacement on the same restored staging database used for v23. After applying
v24, both `degraded` and `inconclusive` must be accepted while an unknown value
must still be rejected.

Run one synthetic zero-yield discovery and one low-valid-ratio discovery in
staging. Confirm the corresponding health status and reason code are persisted,
safe rows may still be ingested, and no previously active catalog job is
deactivated. Then run a healthy positive control and confirm the existing
48-hour stale rule still works. Record counts and identifiers only; do not put
job bodies, URLs, or candidate data in release evidence.

## Non-secret health checks

Use a release-specific evidence timestamp:

```powershell
Invoke-RestMethod https://<backend>/api/health
Invoke-RestMethod https://<backend>/api/ready
Invoke-RestMethod https://<ocr-worker>/health
Invoke-RestMethod https://<ocr-worker>/ready
```

Expected backend readiness is `{"status":"ready"}` and proves a database query,
not complete application readiness. OCR readiness proves configured language
data and a basic MuPDF operation. Also request the frontend login page and
confirm the expected canonical host/security headers.

Do not add secrets to health URLs, query strings, screenshots, or shared logs.

## Scheduler preflight

### Vercel recovery worker

`backend/vercel.json` currently declares `/api/workers/process` at `0 2 * * *`
(daily). Confirm in the deployed project that:

- the cron exists once and targets the expected production deployment;
- `CRON_SECRET` is present and differs from other secrets;
- recent invocations return success;
- oldest queued/running work and abandoned onboarding age stay within the
  accepted beta limit.

Daily recovery is not a strong user-facing SLA. The operations/product owners
must approve a faster cadence and alert threshold before scan volume grows.

### Supabase Goozali discovery

Before setting `GOOZALI_DISCOVERY_ENABLED=true`, verify v21, the explicit UUID
allowlist, source contract, endpoint deployment, Vault secret, scheduler, and
monitoring.

Read-only SQL inventory (column availability can vary by extension version):

```sql
select jobid, jobname, schedule, active
from cron.job
where jobname = 'careerfit-goozali-discovery';

select name, created_at, updated_at
from vault.secrets
where name = 'careerfit_cron_secret';
```

Require exactly one active hourly schedule and exactly one named Vault secret.
Never select from `vault.decrypted_secrets` for status evidence. Inspect the
scheduled command and confirm it calls the canonical HTTPS backend endpoint
without embedding a plaintext secret.

In staging only, an authorized manual invocation may be used to prove the full
path. Record source-run status/counts and bounded duration, not imported job
text or recruiter/contact fields. Confirm the feature kill switch stops future
imports.

### Email notifications

Before enabling email:

- verified sender/domain exists;
- Resend, notification signing, and public URL settings pass;
- discovery and email consents are separately enabled on a synthetic account;
- one delivery is idempotent under retry;
- unsubscribe disables future delivery;
- no CV/profile evidence appears in content/provider metadata;
- paused discovery suppresses pending delivery.

## Release evidence

Attach to the release record:

- environment name and deployment/Git identifiers;
- checklist results with timestamps;
- migration versions through v24, including application-event and source-health rehearsals;
- redacted health/readiness and scheduler status;
- Storage and application synthetic-smoke evidence;
- unresolved exceptions, accountable approver, expiry, and rollback trigger.

A checked box without attached, redacted evidence is not a completed preflight.
