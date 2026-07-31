# Goozali Discovery Beta

Date: 2026-07-21
Last reviewed: 2026-07-30
Status: optional beta; disabled by default. The environment, scheduler, and
monitoring checks in `ENVIRONMENT_AND_SCHEDULER_PREFLIGHT.md` are authoritative.

## Outcome

CareerFit can independently read Goozali's public Airtable job view, ingest recent new or changed records into the shared catalog, and reuse the existing queued deterministic matcher. The beta is restricted to explicitly configured account UUIDs in the IL cohort. It never infers citizenship from a name, CV, or location.

Goozali matches scoring at least 65 with sufficient confidence and no deterministic blocker can appear in-app. Email remains stricter: it requires a Strong 76+ match, confidence of at least 0.55, no blocker, active beta membership, discovery consent, and separate email consent.

## Before / Issue / Solution / After

| Before | Issue | Solution | After |
|---|---|---|---|
| Recommendations only entered through user job scans. | New public roles could not be discovered automatically. | Added a bounded Goozali source adapter and source-run audit. | Recent public roles can enter the existing catalog and PGMQ pipeline. |
| Catalog dedupe used only a content hash. | External edits could produce duplicates or lose source identity. | Added stable `(source_name, external_id)` identity and last-seen timestamps. | Repeated runs update one catalog record and stale records can be deactivated. |
| Any opted-in profile could receive a shared recommendation. | The requested rollout is limited to three test accounts. | Added explicit `job_discovery_beta_members` enrollment and a configured UUID allowlist. | Goozali matching is limited to the IL beta cohort without identity inference. |
| Recommendation consent also implied every future notification channel. | Email is an external action with separate privacy expectations. | Added separate preferences, idempotent delivery records, Resend delivery, and signed unsubscribe. | Email cannot be enabled or sent without explicit consent and provider configuration. |
| Vercel Hobby Cron runs daily. | Discovery needs an hourly cadence. | Added a dedicated secured worker intended for Supabase Cron. | Hourly scheduling is possible without upgrading the Vercel plan. |

## Public source contract

The adapter reads these job fields only:

- Job Title
- Company
- Field
- Position Link
- Scope
- Location
- Minimum Experience
- Job Description
- Requirements
- Language and education requirements
- Posted date

The public response also contains recruiter contact fields. CareerFit does not read or persist Point of Contact, LinkedIn, Email, or Phone values.

The table currently loads through Airtable's undocumented `readSharedViewData` endpoint. The browser bootstrap supplies a short-lived access policy on each run, so no Airtable credential is stored. This remains operationally fragile: Airtable can change the contract or block access. `GOOZALI_DISCOVERY_ENABLED=false` is the immediate kill switch.

## Configuration

Backend variables:

```text
GOOZALI_DISCOVERY_ENABLED=false
GOOZALI_EMBED_URL=https://airtable.com/embed/appwewqLk7iUY4azc/shrQBuWjXd0YgPqV6?backgroundColor=cyan&viewControls=on
GOOZALI_INITIAL_LOOKBACK_HOURS=72
GOOZALI_MAX_JOBS_PER_RUN=40
GOOZALI_BETA_USER_IDS=<comma-separated Supabase Auth UUIDs>
PUBLIC_API_URL=https://career-fit-ai-api.vercel.app
FRONTEND_URL=https://career-fit-ai-sigma.vercel.app
```

Email additionally requires:

```text
RESEND_API_KEY=<backend-only secret>
NOTIFICATION_FROM_EMAIL=CareerFit Jobs <jobs@verified-domain.example>
NOTIFICATION_SIGNING_SECRET=<independent random secret>
```

Do not reuse `CRON_SECRET` as the unsubscribe-signing secret. Keep all three backend-only.

## Hourly Supabase Cron

For an existing project, apply every unapplied migration in the explicit release
order documented in `supabase/migrations/README.md` through database contract
v22; historical filenames do not sort into release order. The original Goozali
tables were introduced in `20260721_goozali_discovery_v16.sql`. Then place the
existing backend
`CRON_SECRET` in Supabase Vault as `careerfit_cron_secret`. Do not paste the
value into migration files.

Schedule the production worker:

```sql
select cron.schedule(
  'careerfit-goozali-discovery',
  '7 * * * *',
  $schedule$
  select net.http_post(
    url := 'https://career-fit-ai-api.vercel.app/api/workers/discover',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'careerfit_cron_secret'
        limit 1
      )
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 55000
  );
  $schedule$
);
```

Only enable `GOOZALI_DISCOVERY_ENABLED` after the migration, allowlist, endpoint deployment, and cron secret are ready.

The cron/Vault setup remains a manual provider operation, not fully managed
infrastructure as code. Treat the SQL above as reviewed setup intent and run the
read-only drift checks in `ENVIRONMENT_AND_SCHEDULER_PREFLIGHT.md` for every
release. Record exactly one active schedule and the presence—not the decrypted
value—of the named Vault secret.

## Operational behavior

- Initial imports use a 72-hour window and a 40-job cap by default.
- Every later run refreshes already cataloged records and imports the next recent unseen batch.
- The adapter performs one public-table fetch per run and never follows employer links.
- Missing catalog rows are deactivated only after a 48-hour grace period.
- Network response sizes and timeouts are bounded.
- Contract changes fail the source run without modifying existing recommendations.
- Email delivery is idempotent per recommendation/channel. Failed provider attempts remain retryable in PGMQ.
- Email content includes role, company, location, score, and links—not CV excerpts or raw profile evidence.

## Known risks

1. Airtable marks the shared view as non-exportable and disallows crawler access to embed paths in its robots rules. The independent adapter may stop working or create policy risk; keep the feature small, low-frequency, attributable, and easy to disable.
2. A public-table refresh currently transfers a multi-megabyte compressed response. The hourly worker parses it once and caps database writes, but source bandwidth cannot be made incremental without an official API.
3. Some Goozali records have missing descriptions or inconsistent dates. The adapter ignores underspecified rows and uses Airtable record creation time for new-record detection.
4. Outbound email cannot operate until a verified sender and provider key exist. The UI reports this state and will not allow email opt-in meanwhile.
