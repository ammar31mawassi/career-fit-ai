## What changed

Describe the user-visible and system behavior changed by this pull request.

## Risk and privacy review

- [ ] I reviewed authentication, authorization, tenant ownership, and sensitive-data handling.
- [ ] I documented any migration, rollout, rollback, retention, or compatibility impact.
- [ ] I did not add secrets, CV text, job descriptions, access tokens, or user identifiers to logs or fixtures.
- [ ] Required roles in `docs/OWNERSHIP.md` reviewed the change, or the unassigned-owner gate is explicit.
- [ ] Any new table, object prefix, queue, log, processor, or analytics event is in the retention inventory.

## Dependencies and configuration

- [ ] Direct constraints and exact locks changed together; clean resolution, advisories, licenses, and SBOM/inventory diff were reviewed.
- [ ] New/changed environment variables are in `.env.example` and the environment preflight.
- [ ] External actions/images/tools use reviewed immutable references where supported.

## Verification

- [ ] Backend tests pass.
- [ ] OCR worker tests pass when the OCR boundary changed.
- [ ] PostgreSQL fresh-install and upgrade security contracts pass when persistence changed.
- [ ] Frontend unit tests, type-check, production build, and production dependency audit pass.
- [ ] I tested the affected user journey, including loading, empty, failure, retry, keyboard, and narrow-screen states.
- [ ] Staging health/readiness, scheduler, and synthetic Storage lifecycle checks pass when deployment/configuration changed.

## Release notes

State whether this needs environment changes, a database migration, a scheduled
worker, a staged rollout, a retention cleanup, or a forward-fix plan. Name the
immutable rollback target and any schema/Storage caveat.
