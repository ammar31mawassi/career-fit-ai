# CareerFit ownership register

Status: assignments required before a wider public launch
Last reviewed: 2026-07-30

This register defines the roles that must approve or operate sensitive changes.
It does not assign people who have not accepted the responsibility.

| Role | Accountable scope | Assigned identity | Required before release |
| --- | --- | --- | --- |
| Product owner | User promises, launch scope, risk acceptance, retention decisions | **UNASSIGNED** | Approve release scope and unresolved product risks |
| Security and privacy owner | Incident command, threat review, security reports, deletion and privacy controls | **UNASSIGNED** | Publish a private reporting channel and approve the incident/deletion procedures |
| Production operations owner | Deployments, alerts, on-call escalation, backup/restore evidence, rollback command | **UNASSIGNED** | Accept the release runbook and recovery objectives |
| Backend owner | API/authentication/storage/worker changes | **UNASSIGNED** | Review affected backend and worker changes |
| Frontend owner | Authentication UI, BFF, accessibility, browser privacy | **UNASSIGNED** | Review affected frontend changes |
| Database and migration owner | Supabase schema, RLS, Storage policies, queues, migrations | **UNASSIGNED** | Review migration order, compatibility, and production evidence |
| Scoring policy owner | Match semantics, deterministic blockers/caps, calibration promotion | **UNASSIGNED** | Approve any score-policy or calibration change |
| Data and evaluation owner | Dataset provenance, evaluation examples, model artifacts, deletion coverage | **UNASSIGNED** | Approve data use and evaluation retention |
| Legal/licensing owner | Project license, third-party obligations, privacy terms, PyMuPDF entitlement | **UNASSIGNED** | Resolve the licensing gates in `THIRD_PARTY_NOTICES.md` |

## Decision rules

- A person is not an owner until their name, durable contact, backup, and
  acceptance date are recorded here.
- The production operations owner has rollback authority during an incident.
  The security/privacy owner has containment authority for suspected data
  exposure. Product approval cannot waive a legal or security release gate
  without a written, time-bounded exception from the accountable role.
- Database migrations, authentication changes, deletion changes, scoring-policy
  changes, and new external data processors require review by both the
  implementation owner and the accountable specialist role above.
- Every assigned role needs a named backup. A chat room or team alias may be a
  contact path, but it is not itself an accountable person.

## CODEOWNERS activation

`.github/CODEOWNERS` intentionally contains no ownership patterns yet. After
real GitHub handles accept the roles:

1. add the narrowest applicable patterns;
2. require CODEOWNER review in branch protection;
3. test the rules with a pull request that touches frontend, backend, database,
   operations, scoring, and privacy paths;
4. record the protection evidence in the release record.

Until then, CODEOWNERS enforcement is an explicit governance gap, not a control.
