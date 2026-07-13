# CareerFit senior QA remediation

Date: 2026-07-13

Owner: Engineering

Scope: profile extraction, matching, profile review, latency, public-account safety, failure recovery, and readability.

## Release standard

This remediation treats the QA report as a set of product contracts, not isolated visual bugs. A release is acceptable only when backend tests, frontend type-checking, the production build, secret scanning, and production smoke tests pass.

## Before / issue / solution / after

| Area | Before | Issue | Solution | After / permanent contract |
|---|---|---|---|---|
| Skill evidence | A skill found in a CV could be saved as a generic low-confidence mention. | Explicit skills such as Docker appeared weak or missing, even after the user confirmed them. When the same CV both listed and demonstrated a skill, the shortest listed line could incorrectly win. | Added an explicit `declared_skill` evidence type. Skill extraction now ranks every same-source occurrence and keeps the strongest context, including reconstructed wrapped project bullets. User approval raises listed evidence, while project and employment evidence remain stronger. | Listed skills count toward matching; confirmation materially raises their strength; demonstrated usage outranks a same-CV listing; only project/work evidence is called demonstrated. Regression tests cover all three states. |
| Project extraction | Project titles were expected to precede descriptions. | PDF layouts containing action-led project bullets produced zero projects; hard-wrapped action text could also stop at a connector such as “and,” making advice incomplete. | The project parser now accepts action-led lines inside a Projects section, joins visibly incomplete PDF wraps, retains meaningful adjacent lines, and avoids title/action duplicates. | The exact failed PDF text layout is a permanent test fixture and yields both complete projects. |
| Duplicate facts | The same fact from CV and LinkedIn could create separate rows. | Slight differences in wording made the profile noisy and reduced trust. | Existing canonical reconciliation is retained, while declared skills now merge into one canonical fact and source support raises confidence. Bulk review provides a safe correction path for residual ambiguity. | Equivalent facts should merge; multiple independent sources strengthen one fact. New normalization failures must be added as fixtures before changing fuzzy thresholds. |
| Fact review | Every extracted fact required a separate request and the entire page was expanded. | Reviewing 20–30 facts was slow and cognitively heavy. | Added selection, “select pending,” bulk confirm/reject, impact ordering, pending-first sorting, and collapsed completed sections. The backend applies a batch in one transaction and rebuilds the profile once. | One bulk decision produces one profile rebuild. Pending, high-impact facts are shown first. Completed groups stay collapsed by default. |
| Matching language | Any sub-threshold match used the same “weak or transferable” sentence. | The explanation contradicted the profile and sounded like the product ignored the CV. | Match records now retain the evidence type used for each skill. Copy is selected from that evidence type. | Explanations must describe the actual evidence state and never imply that a listed skill is absent. |
| Write latency | Each request opened fresh database connections; API ran far from the database. | Warm writes still took roughly 8–10 seconds and scans roughly 16 seconds during QA. | Replaced `NullPool` with a deliberately tiny, recyclable connection pool suited to serverless transaction pooling. API region is pinned to Singapore near the Supabase database; frontend functions are pinned near primary users while static assets remain global. | API and database must be region-co-located. Pool size stays bounded to avoid a serverless connection storm. Production latency is measured after every region or database change. |
| Scan failures | A failed synchronous scan discarded recovery context and could leave users waiting. | Users could neither stop waiting nor safely retry with the same input. | Added an abortable client request, honest “Stop waiting” behavior, retained scan input, and an idempotent retry action backed by existing URL/content deduplication. | A client stop never claims the server job was cancelled. Retry reuses the same payload and must not create a duplicate saved job. |
| Match refresh consistency | Job cards use lightweight cached summaries while the inspector loads current details. | A one-job rematch could update the inspector but leave the card’s old percentage visible until a full refresh. | Detail loading now replaces both the detail cache and its lightweight summary with the same response. | Card, inspector, fit label, and primary signal must agree after any detail fetch or rematch. |
| Account recovery | The public login supported sign-in and sign-up only. | A forgotten password permanently blocked a beta user. | Added Supabase password-reset email, a safe auth callback, and a recovery page that updates the password in an authenticated recovery session. | Password recovery remains accessible without an existing app session; redirect targets are restricted to local paths. |
| User data rights | Users could not obtain or remove their CareerFit data. | Public beta accounts lacked basic export and deletion controls. | Added an authenticated JSON export and a typed-confirmation delete flow. Private files are deleted first; the Supabase Auth user is deleted only after storage cleanup, with database rows removed by ownership cascades. | Export never leaks private storage paths. Deletion fails safely before Auth deletion if file cleanup fails. Account controls remain visible in Profile. |
| Privacy clarity | The product collected CV and profile data without an in-product explanation. | Users could not quickly understand what is stored or what the score means. | Added a public, plain-language privacy page linked from login and Profile. It documents private files, deterministic scoring, export/deletion, and beta limitations. | Privacy information must be reachable before signup and from the authenticated product. Score copy must not claim to predict hiring outcomes. |
| Authentication cache safety | User-scoped frontend data could remain in memory across navigation. | A stale cache after logout can expose the previous session’s UI state; remotely signing out after deleting the Auth identity also caused a noisy expected 403. | Existing user-scoped cache invalidation is now also used by deletion. A local SSR cookie-clear route removes the deleted identity without making a doomed network revocation request. | Every logout/account-deletion path clears client workspace caches; deletion returns to login without a console-level Auth error. |
| Login layout | The desktop login was a sparse centered form with small supporting copy. | It looked unfinished and did not explain the value or privacy model. | Added a two-column product-led login, concise evidence/matching proof points, password reset mode, and stronger hierarchy. Mobile retains a focused single-column form. | Desktop uses the available canvas; mobile removes nonessential showcase content; one semantic H1 describes the product. |
| Profile readability | Functional labels were frequently 9–11 px and all sections competed at once. | The page felt dense, long, and hard to scan. | Raised functional type sizes, improved spacing and hierarchy, moved review work earlier, and collapsed reviewed fact groups. | Decorative micro-labels may remain compact, but inputs, actions, facts, questions, and status text must remain comfortably readable. |

## Evidence model contract

CareerFit uses three human-readable evidence tiers:

1. **Listed** — explicitly present in a Skills, Technical Skills, or Tools section. It is valid profile evidence, but does not prove depth.
2. **Confirmed** — the user has approved the extracted fact. This raises confidence and can clear a weak-evidence threshold.
3. **Demonstrated** — tied to a project or professional experience statement. This receives the strongest default evidence weight.

Multiple independent sources support one canonical fact and raise confidence; they should not create duplicate facts merely to raise the score. User confirmation is valuable but must not outrank concrete professional or project evidence.

## Engineering guardrails

- Every real extraction failure becomes a sanitized regression fixture before its parser fix is merged.
- Never recalculate matches inside list/read endpoints. Recalculation belongs to an explicit write or background job.
- Batch profile review must validate ownership of every fact before updating any of them.
- Optimistic UI is appropriate only for reversible, high-success actions. It must retain a rollback path and disclose background work honestly.
- Account deletion removes private files before deleting the Auth identity. A partial failure must preserve the account so the user can retry.
- Export responses contain user-readable content and metadata, never storage object paths, service keys, or internal credentials.
- Public profile responses never expose private storage object paths; only the backend resolves them.
- Serverless database pools remain intentionally small. More function instances, not large per-instance pools, provide concurrency.
- Safe authentication redirects accept local paths only.
- Public routes for privacy and password recovery must stay outside authenticated onboarding redirects.

## Verification checklist

- Backend unit and regression suite passes.
- Frontend TypeScript check passes.
- Production frontend build passes.
- Repository secret scan passes.
- Production health endpoint responds.
- Public login, signup, password-reset request, and privacy page load.
- Authenticated workspace loads without a false incomplete-profile flash.
- Bulk fact review performs one request and reflects rollback on failure.
- A stopped scan retains inputs and can be retried without duplication.
- Export downloads JSON; deletion requires the literal confirmation `DELETE`.
- Database/API region and measured production timings are recorded in the release handoff.
