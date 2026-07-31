# Release, promotion, and rollback runbook

Status: process defined; owners and production evidence unassigned
Last reviewed: 2026-07-31
Database contract: v24

This is the living release process. Dated release reports are historical
evidence and must not be used as a substitute.

## Release identity

Every release record must bind:

- immutable Git commit SHA;
- frontend and backend deployment IDs/URLs;
- OCR image digest (tag alone is insufficient);
- ordered database migrations applied, including v23 application-event context
  and v24 source-health statuses;
- frontend SBOM and Python dependency inventories;
- configuration/preflight evidence;
- approvers and rollback commander;
- release start/end timestamps and resulting status.

Do not rebuild source-identical artifacts during promotion when the platform can
promote an already-tested immutable deployment. If a provider rebuild is
unavoidable, compare toolchain, locks, environment, and artifact digest.

## Required approvals

Assignments are tracked in `docs/OWNERSHIP.md`. At minimum:

- implementation owner for each affected component;
- database owner for schema/RLS/Storage/queue changes;
- security/privacy owner for auth, personal data, processors, deletion, or
  incident controls;
- scoring-policy owner for score semantics/calibration;
- operations owner for promotion and rollback;
- legal/licensing owner for dependency/license changes that affect obligations.

Unassigned required roles block production promotion.

## Promotion stages

### 1. Change readiness

- Pull request describes behavior, failure behavior, configuration, stored data,
  migration compatibility, release order, and rollback.
- `CHANGELOG.md` is updated.
- Exact locks and inventories are reviewed for dependency changes.
- CI passes backend/OCR/frontend/PostgreSQL checks.
- Secret scan contains no broad unreviewed suppression.
- Known release gates have an owner-approved, time-bounded exception or remain
  blockers.

### 2. Staging deployment

Deploy to isolated staging using production-shaped settings and synthetic users.
Follow `docs/ENVIRONMENT_AND_SCHEDULER_PREFLIGHT.md`.
Run `.github/workflows/staging-smoke.yml` after the staging deployment and bind
the successful run URL to the release record. Environment protection must
require an accepted reviewer and staging-only variables/secrets.

Exercise affected journeys plus:

- signup/login/logout/recovery and cross-account denial;
- onboarding upload/read/review/completion;
- service-role and application Storage upload/read/delete;
- scan acceptance, duplicate submission, progress, cancellation, recovery, and
  result load;
- recommendation consent/save/dismiss/pause and notification suppression;
- export and complete synthetic account deletion;
- narrow-screen, keyboard, loading, empty, retry, and error recovery.

Store trace/reference codes and status/timing evidence only. Do not attach
private payloads.

### 3. Migration ordering

Use expand/contract compatibility:

1. deploy code that can tolerate both old and new schema;
2. apply the additive migration;
3. verify the migration and application;
4. switch behavior;
5. remove old compatibility only in a later release.

Never edit an applied migration or rerun `supabase/schema.sql` on an existing
project. Migrations are forward-only unless a reviewed down operation is proven
safe against real production state.

For v21 Storage privilege hardening, the backend service-role path must exist
and pass staging smoke before browser DML is revoked. See the rollback caveat in
the environment preflight.

For this v23/v24 change set, use the compatible schema-first sequence: apply
v23 and then v24, verify both, deploy the backend, and deploy the frontend last.
The pre-change backend tolerates the additive event columns and wider source-run
status constraint, while the new backend requires those columns/statuses and the
new frontend requires the expanded backend response. Keep the migration-to-
backend window short (or pause application-stage writes) because events written
by the old backend during that window receive safe defaults but cannot record an
accurate `previous_status`.

### 4. Production canary

Where the platforms permit it, expose the immutable release first to internal
or explicitly enrolled beta accounts. Keep discovery/email kill switches off
until their own checks pass.

Watch at least:

- readiness and 5xx/auth failure rates;
- scan queue age, stale claims, retries, and cancellations;
- upload/OCR failures and timeouts;
- database connections/latency;
- notification attempts/suppression;
- deletion/storage cleanup failures;
- frontend error/reference-code rate.

Concrete thresholds and observation duration are **TBD by the operations and
product owners**. They must be written into the release record before canary.

### 5. General promotion

Promote only the tested artifact, record the decision, enable feature flags one
at a time, and repeat critical synthetic checks. Close the release record with
deployed IDs and remaining exceptions.

## Rollback decision

The rollback commander should stop promotion and choose rollback, containment,
or forward fix when any of these occurs:

- cross-tenant access, auth bypass, service-role exposure, or private-data leak;
- uploads/deletions operate on the wrong owner or leave unexplained objects;
- migration errors or data corruption;
- material 5xx/auth/queue/OCR regression beyond the release threshold;
- notification sent without current consent;
- scoring change violates deterministic blockers/caps;
- required readiness or synthetic smoke fails.

Security containment takes precedence over availability.

## Component rollback

### Frontend

Promote the prior immutable deployment. Confirm its BFF/auth contract is still
compatible with the deployed backend/schema. Clear no user data as part of a
frontend rollback.

### Backend

Promote the prior immutable deployment only when it supports the current schema
and Storage policy. Pause cron/discovery/email first if old worker behavior is
uncertain. Re-run readiness and synthetic auth/storage/scan checks.

### OCR worker

Route to a prior digest, not a mutable tag. If no approved image exists, disable
server OCR and retain the private browser/text fallback rather than sending
documents to an unapproved public service.

### Database

Prefer a forward fix. A database restore is an incident-recovery operation, not
a routine application rollback: it can lose newer writes, does not inherently
restore Auth/Storage, and needs the approved RPO/RTO and incident process.

For v21, do not broadly re-grant authenticated Storage writes/deletes to make an
old client work. Keep uploads disabled or roll application code to a compatible
backend and issue a reviewed forward migration.

### Configuration/feature

Use narrow kill switches:

- `GOOZALI_DISCOVERY_ENABLED=false`;
- disable email preference availability by removing provider prerequisites
  while preserving user preference records;
- clear `OCR_SERVICE_URL`/token to stop server OCR;
- pause scheduler invocations when worker behavior is unsafe.

Do not rotate or delete a key without mapping every consumer first.

## Post-rollback verification

- Confirm active deployment IDs and schema version.
- Run `/api/health`, `/api/ready`, OCR readiness if enabled, and frontend smoke.
- Prove synthetic login, Storage lifecycle, scan, and deletion paths.
- Confirm scheduler state and queue age.
- Check that no partial release feature remains enabled.
- Record user/data impact, lost-work window, and follow-up owner.

## Release record template

```text
Release:
Git SHA:
Frontend deployment:
Backend deployment:
OCR digest:
Database migrations:
Change window:
Release commander / backup:
Required approvers:
CI run:
SBOM/inventories:
Staging evidence:
Storage v21 evidence:
Data-contract v22 evidence:
Application-event v23 evidence:
Source-health v24 evidence:
Canary cohort and duration:
Success/rollback thresholds:
Known exceptions and expiry:
Decision:
Production verification:
Rollback target:
Incident/follow-up links:
```

Never put secrets, CV/job bodies, auth-user IDs, emails, or signed links in the
release record.
