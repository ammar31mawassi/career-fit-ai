# Security policy

Last reviewed: 2026-07-30

## Supported version

CareerFit is a beta and currently supports only the latest deployed revision.
Older deployments and local forks do not receive separate security updates.

## Reporting a vulnerability

**A private external security-reporting channel has not yet been assigned. This
is a release gate in `docs/OWNERSHIP.md`.**

Do not place credentials, access tokens, CVs, personal data, private job
descriptions, or exploit details in a public issue. Internal maintainers should
use an already-approved private organizational channel and contact the
security/privacy owner. If no such channel and owner exist, pause broader public
distribution until they are established.

The future published channel must:

- be monitored by a named primary and backup;
- acknowledge receipt without promising an unapproved remediation deadline;
- support encrypted or otherwise private evidence transfer;
- define severity triage, safe-harbor language, disclosure coordination, and
  reporter updates;
- be tested at least quarterly.

Response-time commitments remain **TBD by the security/privacy owner** and must
not be advertised until staffing can meet them.

## High-risk areas

Reports involving any of these areas should be treated as potentially severe:

- cross-tenant access, Supabase RLS, Storage object ownership, or service-role
  credentials;
- authentication callback, signup, password recovery, or BFF authorization;
- CV/PDF parsing, OCR resource exhaustion, SSRF, or private source disclosure;
- account deletion, export incompleteness, or retained private files;
- worker/cron authorization, queue claims, notification delivery, or
  unsubscribe signing;
- secrets committed to source, logs, CI artifacts, or deployment output.

## Maintainer handling

1. Preserve the report in the approved private case system; do not copy private
   payloads into general chat or issue trackers.
2. Assign an incident lead and severity; record timestamps and affected
   environments.
3. Contain first when exposure is plausible: disable the affected feature,
   revoke credentials, or restrict traffic.
4. Use `docs/OPERATIONS_RUNBOOK.md` for investigation, rotation, recovery, and
   evidence handling.
5. Add a regression test and release/rollback plan before promotion.
6. Publish a scoped advisory when the security/privacy and legal owners approve
   the content.

Never use a real user document as a security fixture. Use synthetic data and
redact tokens, identifiers, URLs, evidence text, and provider response bodies.
