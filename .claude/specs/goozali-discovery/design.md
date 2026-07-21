# Goozali Discovery Beta Design

## Architecture

Goozali public embed -> bounded shared-view adapter -> source run -> shared job catalog -> PGMQ recommendation queue -> cohort shortlist -> deterministic scorer -> in-app recommendation -> optional email queue -> Resend

## Components

### Goozali adapter

- Reads the public embed bootstrap and its short-lived shared-view access policy.
- Calls the same read-only shared-view endpoint used by the browser.
- Maps only job fields and deliberately discards recruiter contact fields.
- Returns typed records with stable Airtable record IDs.
- Enforces response limits, timeouts, contract validation, lookback, and per-run limits.

### Discovery service

- Records each source run and its outcome.
- Upserts catalog jobs by `(source_name, external_id)` with a stable content hash.
- Reclassifies and enqueues only new or materially changed jobs.
- Refreshes `last_seen_at` and deactivates stale source records after a grace period.
- Synchronizes beta membership from an explicit UUID allowlist; names are never used as identity rules.

### Recommendation service

- Preserves the existing community threshold.
- For Goozali jobs, joins the IL beta-membership table before full scoring.
- Uses 65+ for in-app suggestions and 76+ for email eligibility.
- Queues email only after the recommendation transaction has produced a high-confidence available result.

### Notification service

- Stores explicit email preference separately from discovery consent.
- Creates one delivery per recommendation/channel using a database unique constraint.
- Resolves the verified Supabase Auth email only at delivery time.
- Sends through Resend with an idempotency key and one-click unsubscribe headers.
- Uses signed unsubscribe tokens and never logs message content or email addresses.

## Data model additions

- `shared_job_catalog`: source name, external ID, source publication time, last-seen time.
- `job_source_runs`: bounded operational audit for source executions.
- `job_discovery_beta_members`: explicit user/market enrollment.
- `job_notification_preferences`: separate email consent.
- `notification_deliveries`: idempotent delivery state and provider reference.

## Scheduling

- A dedicated protected worker endpoint performs one Goozali sync and drains bounded recommendation/email work.
- Production hourly scheduling uses Supabase Cron because the current Vercel Hobby cron cannot run hourly.
- Existing daily recovery remains valid and may also process queued work.

## Security and privacy

- The shared Airtable endpoint is undocumented and can change; a disabled-by-default feature flag and fast failure provide a kill switch.
- Only public job content required for matching is persisted.
- Contact details present in the table are excluded before persistence.
- Beta eligibility is explicit, not inferred from names, profile locations, or CV content.
- Email requires separate affirmative consent and supports revocation without authentication.

## Alternatives considered

- Headless browser in the hourly worker: rejected because it adds large serverless/runtime cost and more fragile DOM coupling.
- Employer-site rescanning: rejected because Goozali already supplies descriptions and requirements.
- Name- or location-based citizenship detection: rejected because it is inaccurate and inappropriate for access control.
- Email during the scoring transaction: rejected because a provider failure could corrupt or roll back recommendation generation.
