# Production operations and incident runbook

Status: baseline procedure; execution owners/objectives/provider evidence TBD
Last reviewed: 2026-07-30

This document defines how to act safely. It does not prove that monitoring,
backup, restore, on-call, or deletion drills are configured. Those controls are
release gates until evidence is attached.

## Required assignments and decisions

Before production expansion, fill `docs/OWNERSHIP.md` and record:

- primary/backup incident commander and private contact path;
- Supabase, Vercel, OCR host, DNS/domain, email provider, and source-system
  account owners;
- service and user-journey SLOs;
- approved RPO (acceptable data-loss window) and RTO (recovery-time target);
- alert thresholds and 24/7 versus business-hours coverage;
- backup/PITR/Storage capabilities actually purchased and enabled;
- evidence retention and incident communication/legal obligations.

Values are intentionally not invented here.

## Service map

| Component | Responsibility | Sensitive dependency | Immediate containment |
| --- | --- | --- | --- |
| Frontend/BFF | Auth UI, same-origin API bridge | Supabase publishable + server secrets | Promote prior deployment or restrict traffic |
| Backend API | Authz, profiles, scans, exports/deletion | DB, Supabase secret, Storage, worker keys | Promote prior compatible deployment; pause workers |
| Supabase | Auth, PostgreSQL, RLS, Storage, Vault/Cron | Service role and user personal data | Revoke keys/sessions; restrict project access |
| OCR worker | Private PDF raster/OCR | Worker token, native parsers | Clear OCR URL/token; route no documents |
| Vercel Cron | Queue/onboarding recovery | Cron secret | Disable schedule |
| Supabase Cron/Vault | Goozali discovery | Cron secret/source contract | Disable schedule and feature flag |
| Resend | Opt-in email | API key, recipient email | Revoke key/remove configuration; suppress queue |
| Goozali/Airtable public view | Optional public job source | Undocumented source contract | `GOOZALI_DISCOVERY_ENABLED=false` |

## Incident severity

The security/privacy owner must approve final severity definitions. Use this
temporary conservative triage:

- **SEV-1:** confirmed/suspected cross-tenant or public private-data exposure,
  auth/service-role compromise, destructive corruption, or notification to
  unauthorized recipients.
- **SEV-2:** major production outage, deletion/export failure with retained
  personal data, sustained queue/storage/OCR failure, or high-impact vulnerable
  boundary with credible exploitation.
- **SEV-3:** degraded feature with safe fallback and no known data exposure.

When uncertain about exposure, triage upward until disproven.

## First 30 minutes

1. Open a private incident record; assign commander, scribe, and technical lead.
2. Record detection time, environment, symptoms, recent releases/configuration,
   and known affected data classes. Do not paste private payloads.
3. Preserve relevant deployment IDs, trace/reference codes, audit events, and
   redacted logs before they expire.
4. Contain narrowly:
   - disable discovery/email/OCR/schedulers as applicable;
   - revoke a suspected credential and sessions using the rotation map;
   - roll back only to schema-compatible artifacts;
   - restrict project/team access.
5. Verify containment with synthetic tests and provider audit logs.
6. Ask the security/privacy and legal owners to determine notification,
   regulatory, and user-communication duties. Do not improvise promises.

Never delete evidence, restore production, or run broad SQL cleanup merely to
make dashboards green.

## Investigation

- Build a UTC timeline from immutable provider/deployment/audit records.
- Compare affected release/configuration/SBOM with the prior known-good state.
- Bound users, objects, tables, time window, and external processors affected.
- Use identifiers/counts and hashes; minimize access to raw CV/profile/job text.
- Check auth/admin actions, RLS/Storage policy state, service-role use, BFF/API
  trace codes, queue claims, scheduler invocations, and provider delivery IDs.
- Validate whether backups/logs/CI artifacts contain the affected secret/data.
- Record uncertainty explicitly.

## Credential rotation

Maintain a private secret register with owner, consumers, creation/rotation
time, storage location, and last validation. Do not put values in this repo.

| Secret | Known consumers | Rotation order |
| --- | --- | --- |
| `BACKEND_API_KEY` | Backend and frontend BFF | Add new value to both, deploy/verify, remove old |
| Supabase secret/service-role key | Backend and frontend server signup | Inventory consumers, rotate provider key, deploy all, verify auth/Storage/deletion, revoke old |
| Supabase anon/publishable key | Browser, BFF/backend verification | Add/deploy, verify auth, then retire old per provider behavior |
| `CRON_SECRET` | Backend, Vercel/Supabase scheduler Vault | Add backend acceptance strategy or coordinated change, update schedules, verify, remove old |
| `OCR_WORKER_TOKEN`/`OCR_SERVICE_TOKEN` | OCR worker/backend | Deploy worker token and backend token in coordinated window; verify readiness/request; revoke old |
| `RESEND_API_KEY` | Backend | Rotate provider, deploy, send only to synthetic recipient, revoke old |
| `NOTIFICATION_SIGNING_SECRET` | Backend | Define signed-link overlap/expiry first; rotate with compatibility or invalidate links explicitly |
| `GITHUB_TOKEN` | Backend optional enrichment | Revoke, issue least-scope replacement, verify; omit if unused |

Emergency rotation may intentionally disable a feature. Availability is not a
reason to keep a suspected key active.

## Backup readiness

The operations owner must verify current provider documentation/plan and attach
screenshots or exported configuration showing:

- database backup/PITR coverage, frequency, retention, region, encryption, and
  restore method;
- whether Auth records/configuration are included;
- that Supabase Storage objects are not assumed to be part of a database
  backup;
- Vault, scheduler, deployment environment, DNS, and provider configuration
  recovery sources;
- access controls and audit logging for backup operators;
- how user deletion propagates to or ages out of backups.

Until verified, describe backup state as **unknown**, not “managed by Supabase.”

### Recovery-objective decision

Product/operations must choose RPO/RTO by data class and failure mode. At
minimum distinguish:

- database corruption/accidental writes;
- complete Supabase project loss;
- Storage object loss;
- Auth/configuration loss;
- application deployment regression;
- external OCR/email/source outage.

The decision must account for beta expectations, cost, privacy, and manual
reconstruction. Store accepted objectives in the release/operations system.

## Quarterly restore drill

Run only in an isolated project/account with restricted access:

1. Choose a backup point and record expected RPO/RTO.
2. Restore to a new isolated database/project; never overwrite production for a
   drill.
3. Reapply/verify required extensions, migrations through the release version,
   RLS, functions, privileges, queues, and Storage policies.
4. Restore or reconstruct Auth/configuration/Storage separately according to
   verified provider capabilities.
5. Use synthetic canaries to validate row counts/relationships, two-user tenant
   denial, login, profile read, job scan/read, service-role Storage
   upload/read/delete, export, and account deletion.
6. Measure actual data-loss window and recovery time.
7. Delete the drill environment and synthetic objects after evidence is
   captured.
8. Record failures, owner, due date, and whether release/traffic must be
   restricted.

Evidence should include provider operation IDs, timestamps, schema/migration
version, synthetic hashes/counts, and test results—not restored user content.

## Quarterly deletion drill

Use a new synthetic user and uniquely prefixed synthetic files:

1. Complete onboarding with a synthetic PDF and optional sources.
2. Create facts/questions, jobs/matches/status events, scans, recommendations,
   revisions, metrics/evaluation rows, notification preference/delivery, and
   queue work where the current product permits.
3. Export the account and compare included data classes with
   `docs/DATA_RETENTION_INVENTORY.md`.
4. Delete the account through the real API/UI.
5. Verify the Auth user is gone; owned rows are gone/cascaded; all Storage
   objects under the UUID prefix are absent across pagination; scheduled/queue
   work cannot recreate user rows; email is suppressed.
6. Verify intentionally non-user public catalog data no longer identifies the
   source user.
7. Document backup/log/provider retention separately; do not claim immediate
   physical erasure from backups without proof.
8. Re-run checks after the longest asynchronous cleanup window.

A partial Storage/auth/database failure is a failed drill. Record orphan cleanup
and durable retry needs; do not manually erase the evidence before diagnosis.

## Scheduler and queue response

For stale/failed work:

- check `/api/ready` and database connection health first;
- inspect counts/ages/statuses and attempt numbers, not payload bodies;
- verify scheduler authorization and last successful invocation;
- pause duplicate/failing schedules before manual invocation;
- use the existing idempotent worker path; do not directly mutate queue rows or
  PGMQ messages without a reviewed recovery procedure;
- alert on oldest queued/running age once thresholds are approved.

Daily Vercel recovery can lag nearly 24 hours. This is accepted only for the
current beta if product/operations explicitly record it.

## Post-incident

- Add regression tests and the smallest durable control.
- Rotate any credential that may have appeared in evidence.
- Reconcile all manually changed feature flags/schedules/configuration.
- Update runbooks, retention inventory, threat model, and release gates.
- Complete a blameless review with timeline, impact, detection/containment gaps,
  corrective owners/dates, and risk acceptance.
- Publish user/advisory communication only through the approved legal/security
  process.
