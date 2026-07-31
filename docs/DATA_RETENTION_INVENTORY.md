# Data inventory and retention register

Status: partial enforcement; unapproved periods are release gates
Last reviewed: 2026-07-30

This register distinguishes implemented deletion from desired policy. `TBD`
means the data can currently remain indefinitely and requires an accountable
decision plus automated, monitored enforcement. It is not a default approval.

The privacy/legal owner must assign purpose/legal basis, notices, processor
terms, and retention periods for the actual operating jurisdiction. Engineering
must not infer legal basis from this table.

## Global rules

- Collect the minimum data needed for the user-requested feature.
- Private CV/profile evidence is tenant-owned and must not enter the shared job
  catalog, logs, notifications, analytics, CI, or test fixtures.
- Account deletion must cover database, Auth, Storage, queues/schedulers, and
  downstream processors; backup aging must be stated separately.
- Public job data and aggregate operational metrics need retention limits even
  when they are not private CV data.
- A retention policy is complete only when it has an owner, approved duration,
  query/cleanup implementation, schedule, idempotency, metrics/alerting, hold
  process, deletion test, and backup behavior.

## Inventory

| Data class / stores | Purpose and sensitivity | Current lifecycle | Approved retention / trigger | Owner and legal/consent decision | Backup/processor behavior |
| --- | --- | --- | --- | --- | --- |
| Supabase Auth user, email, auth metadata | Account/authentication; personal | Account API requests Auth deletion after private-file cleanup | Account lifetime; deletion behavior implemented but cross-service failure still needs durable verification | Security/privacy **UNASSIGNED**; legal basis/notice **TBD** | Auth backup/recovery/deletion behavior **TBD/verify provider** |
| Profile and interests (`profiles`, `profile_interests`) | User workspace/direction; personal | Cascade on Auth user deletion | Account lifetime; abandoned unfinished profile content cleanup begins after 24h | Product/privacy **UNASSIGNED**; core-account purpose **TBD approval** | Database backup aging **TBD** |
| Source metadata/text (`profile_sources`) | CV, LinkedIn PDF/text, notes, GitHub extraction; highly sensitive | Unfinished onboarding rows/text deleted after 24h; cascade on account deletion | **24h implemented only for abandoned unfinished onboarding**; completed-profile/source replacement retention **TBD** | Privacy **UNASSIGNED**; explicit user submission, legal basis/notice **TBD** | DB backups **TBD**; GitHub is optional processor/source |
| Source PDF objects (`profile-documents` Storage) | Original private documents; highly sensitive | Backend-mediated create/read/delete; abandoned cleanup and account deletion attempt object removal | 24h abandoned cleanup; completed source/replacement/account period **TBD** | Privacy/operations **UNASSIGNED** | Storage is separate from DB backup; backup/versioning/deletion behavior **TBD** |
| Profile facts/evidence and feedback (`profile_facts`, `profile_fact_feedback`) | Evidence-backed profile and correction labels; sensitive derived data | Abandoned cleanup/cascade account deletion | Account lifetime for active profile; rejected/old revisions/evaluation reuse **TBD** | Product/data/privacy **UNASSIGNED**; correction/evaluation use must be disclosed/approved | DB backup aging **TBD** |
| Clarification questions/answers/status | Fill evidence gaps; sensitive derived/user response | Abandoned cleanup/cascade account deletion | Account lifetime or earlier supersession period **TBD** | Product/privacy **UNASSIGNED** | DB backup aging **TBD** |
| User jobs and extracted descriptions (`jobs`) | User-requested fit analysis; may include pasted/private posting text | Cascade account deletion; individual source deletion is incomplete | Account lifetime or user deletion; stale/error job retention **TBD** | Product/privacy **UNASSIGNED**; pasted input remains private | DB backup aging **TBD**; fetched employer content rights **TBD** |
| Matches, resume advice, status events, requirement revisions | Fit evidence/application tracking/corrections; personal derived data | Cascade from user job/account | Account lifetime; history/rejected/withdrawn period **TBD** | Product/data/privacy **UNASSIGNED** | DB backup aging **TBD** |
| Job scans (`job_scans`) and PGMQ work | Durable async execution; contains input reference/hash/error state | Terminal messages archived; row cleanup period absent | Active until terminal; terminal success/failure/cancel retention **TBD** | Backend/operations/privacy **UNASSIGNED** | DB/queue backup behavior **TBD** |
| Agent runs/steps | Workflow progress/operational debugging; can reference user/job subjects | Cascade where related ownership applies; cleanup absent | Short diagnostic period **TBD** | Operations/privacy **UNASSIGNED** | Logs/DB backups **TBD** |
| Shared job catalog | Explicitly contributed, successfully fetched public postings only; pasted descriptions excluded | Independent of account; source user reference can null on account deletion; inactive rows not cleaned | Freshness/deactivation exists; inactive/expired deletion period **TBD** | Product/privacy/legal **UNASSIGNED**; per-scan explicit contribution consent | DB backup and source-content rights **TBD** |
| Recommendation runs/rows/events/calibration | Opt-in matching, feedback, threshold evaluation; personal/derived or aggregate | User rows cascade; operational/global rows may persist | Available/dismissed/saved/shadow/event/run periods **TBD** | Product/data/privacy/scoring **UNASSIGNED**; discovery consent required | DB backup aging **TBD** |
| Goozali source runs and imported public jobs | Auditable beta import; source metadata/errors, public job content | Feature kill switch/deactivation; cleanup absent | Run logs and inactive public jobs **TBD** | Product/legal/operations **UNASSIGNED**; public-source terms review **TBD** | Airtable is external source; DB backup aging **TBD** |
| Beta membership and notification preference | Explicit account eligibility/consent state; personal | Cascade account deletion; pause/opt-out updates | Keep current state for account lifetime; audit-history need **TBD** | Product/privacy **UNASSIGNED**; explicit discovery and separate email opt-ins | DB backup aging **TBD** |
| Notification deliveries/provider IDs/errors | Idempotency, retries, delivery audit; email-linked operational data | Suppression/max attempts implemented; cleanup absent | Delivery/error/provider metadata period **TBD** | Privacy/operations **UNASSIGNED**; Resend processor terms **TBD** | Resend retention/deletion plus DB backups **TBD** |
| Extraction metrics | Privacy-reduced strategy/version/timing/counts/status; still linkable where IDs remain | No raw document/job text intended; cleanup absent | Operational trend window **TBD**; aggregate/anonymize after | Operations/privacy/data **UNASSIGNED** | Hosted logs/DB backups **TBD** |
| Evaluation examples and correction labels | Offline quality/calibration; potentially linkable derived data | Account-owned rows cascade where modeled; exports possible; cleanup absent | Training/validation/test retention and withdrawal behavior **TBD** | Data/privacy/scoring/legal **UNASSIGNED**; evaluation use approval required | Export destinations/artifact backups **TBD** |
| Rate-limit buckets | Abuse prevention; IP/account-derived keys | Reset windows exist; row cleanup behavior not documented | Short window plus bounded cleanup **TBD** | Security/privacy **UNASSIGNED** | Private schema/backup behavior **TBD** |
| Backend/security/request logs and trace IDs | Reliability/security investigation; IP/user correlation possible | Privacy-safe logging intent; provider retention/alerts absent | Log retention **TBD** | Operations/security/privacy **UNASSIGNED** | Vercel/provider export/backup **TBD** |
| Frontend cookies/browser state | Auth session and UI continuity; device-local | Supabase/auth cookies; sensitive full workspace session cache removed | Provider session expiry/logout; any remaining local keys inventory **TBD** | Frontend/security/privacy **UNASSIGNED** | Browser/device controlled; not server backup |
| OCR request memory/logs | Temporary private PDF/text at native boundary | Worker states no disk persistence; body/text should not be logged | Request duration only; platform logs/core dumps **TBD verification** | Security/privacy/operations **UNASSIGNED**; OCR hosting processor review **TBD** | Hugging Face/platform retention and crash artifacts **TBD** |
| CI artifacts (SBOM, dependency inventories, test evidence) | Supply-chain/release evidence; should contain no user data | CI retention currently 30 days for new artifacts | 30 days configured for generated inventories; release evidence duration **TBD** | Operations/security **UNASSIGNED** | GitHub artifact controls/retention **verify** |
| Backups/PITR/restore copies | Disaster recovery; may contain all DB personal data | Provider capability and retention not yet verified | **TBD by approved RPO/RTO and deletion policy** | Operations/security/privacy/legal **UNASSIGNED** | Must document encryption/access/region/expiry; Storage/Auth separate |
| Incident records and security evidence | Investigation/accountability; may contain identifiers | Process defined, case system/contact absent | **TBD by legal/security**; minimize/redact and restrict | Security/privacy/legal **UNASSIGNED** | Approved private case system **TBD** |

## Implemented retention control

Abandoned, incomplete onboarding private source data is selected after 24 hours
and deleted in bounded worker batches. The drill must prove database rows and
every Storage object are removed and failures are observable. Completed
profiles are intentionally excluded.

This is the only broad time-based personal-data retention policy currently
documented as implemented. Account deletion is a user-triggered lifecycle, not
a substitute for time-based cleanup.

## Decisions required

The accountable owners must approve explicit periods for:

1. terminal scans and queue artifacts;
2. replaced/old source documents and extracted source text;
3. inactive/expired shared jobs and source-run history;
4. recommendation impressions/events/shadow observations/calibration evidence;
5. extraction metrics and evaluation examples;
6. notification delivery/provider metadata and failed attempts;
7. rate-limit rows, request/security logs, and incident evidence;
8. database/Auth/Storage backups and restore copies.

For each, record purpose, data subjects, legal basis/consent, processors/region,
maximum period, deletion/withdrawal trigger, hold exception, backup aging, and
approved owner/date.

## Cleanup implementation standard

Every new cleanup must:

- use indexed time/status predicates and bounded batches;
- be idempotent and safe under concurrent workers;
- delete child/external objects in a documented order;
- retry durable cross-service failures without exposing payloads;
- emit counts, duration, oldest age, and stable error codes;
- alert on failures/backlog against an approved threshold;
- have unit, PostgreSQL, cross-tenant, and synthetic end-to-end deletion tests;
- support dry-run counts where practical;
- never silently convert a failed deletion into success.

## Retention review

Review this file whenever a table, Storage prefix, queue, log sink, external
processor, analytics event, model artifact, export field, or backup mechanism
changes, and at least quarterly. The review is incomplete without named
approvers and evidence from the restore and deletion drills in
`docs/OPERATIONS_RUNBOOK.md`.
