# CareerFit Brooks Full Sweep remediation report

Date: 2026-07-30
Mode: Full Sweep
Scope: Entire repository, migrations, deployment configuration, operational documents, automated tests, and read-only local production-build browser flows
Baseline: `338ff36` (`docs: add full-stack production readiness audit`)
Source audit: `docs/FULL_STACK_PRODUCT_AUDIT_2026-07-28.md`

## Executive outcome

The two grouped critical findings are closed in the repository. The shipped
summary endpoint now has a real contract, and the database/privacy boundary now
has a current fresh-install schema, tested forward migrations through v22,
tenant-consistent foreign keys, service-role-only derived writes, backend-only
document storage, atomic active-scan claims, and validated durable payload/state
contracts.

The project is materially safer and more coherent, but this report does **not**
recommend an unrestricted public launch yet. The codebase is suitable for a
small, controlled beta only after the deployment gates in this report are
executed. Broad release remains blocked by external evidence and decisions:
real Supabase rollout and Storage lifecycle proof, PyMuPDF/project licensing,
accepted operational/legal owners, approved retention and privacy terms,
protected remote CI and staging-smoke evidence, scheduler/alerting readiness,
and defensible matching/dataset governance.

### Health score

| Measure | Before | After |
| --- | ---: | ---: |
| Brooks health score | 38/100 | 73/100 |
| Grouped critical findings | 2 | 0 |
| Grouped warnings | 6 | 5 |
| Grouped suggestions | 2 | 2 |

The score uses the same grouped rubric as the baseline: critical `-15`, warning
`-5`, suggestion `-1`. A mitigation remains a warning when production proof,
cross-cutting redesign, legal authority, or an operating control is still
missing. The score is intentionally not inflated by counting the large number
of individual fixes as if they removed those broader systemic risks.

### Detailed register totals

| Dimension | Fixed | Mitigated | Residual | Total |
| --- | ---: | ---: | ---: | ---: |
| API, trust boundaries, privacy | 8 | 6 | 0 | 14 |
| Supabase schema and tenant isolation | 6 | 3 | 0 | 9 |
| Frontend correctness and state | 12 | 6 | 2 | 20 |
| UX, product design, accessibility | 3 | 8 | 3 | 14 |
| Frontend minor/latent register | 14 | 3 | 3 | 20 |
| Matching and model governance | 0 | 3 | 3 | 6 |
| Dataset/evaluation governance | 0 | 0 | 7 | 7 |
| Dependencies and licensing | 2 | 3 | 1 | 6 |
| Test strategy and release controls | 0 | 6 | 1 | 7 |
| Operations and privacy program | 2 | 5 | 2 | 9 |
| Backend concurrency/data quality | 12 | 8 | 2 | 22 |
| **Total** | **59** | **51** | **24** | **134** |

“Mitigated” means the immediate defect/risk is reduced and the current path is
safer, but the complete remedy from the source audit is not yet proven.
“Residual” means the root issue still requires a separate workstream or an
authority/decision unavailable in this repository.

## Validation summary

| Check | Final result |
| --- | --- |
| Backend test suite | 285 passed |
| Backend dependency check | `pip check`: no broken requirements |
| Backend compile check | `app`, `scripts`, and `tests` compile cleanly |
| OCR worker test suite | 17 passed |
| PostgreSQL contract | Fresh install and v18→v22 upgrade path passed in PostgreSQL 16 |
| Frontend policy/contract tests | 28 passed |
| Frontend TypeScript | Passed |
| Frontend production build | Passed on Next.js 16.2.12 |
| Frontend production dependency audit | 0 vulnerabilities |
| Browser walkthrough | Protected redirects, safe deep link, public pages, auth modes, 390px and 320px layouts, requests, console, and recovery recheck passed |
| Secret guard | No findings after narrow review of non-secret false positives |
| Patch integrity | `git diff --check` passed |

The PostgreSQL harness initially caught the official image's temporary
initialization server and then lost its socket. The harness was corrected to
require three consecutive real `psql` queries; the complete fresh/upgrade test
then passed. This was test-harness startup flakiness, not a schema failure.

The real staging workflow was not executed because this workspace was not given
staging URLs or credentials. `.github/workflows/staging-smoke.yml` and the
current-contract, staging-only cleanup-verifying smoke are implemented; their
remote run remains a release gate.

## Sweep iteration history

### Round 1 — Critical correctness, authorization, privacy, and persistence

- Restored the missing summary-page return/ETag/304 contract with HTTP tests.
- Made scanned jobs private by default; added explicit public-posting
  contribution and verified-public-source rules.
- Closed fail-open deployed authentication/configuration paths.
- Added tenant-owner composite foreign keys, revoked browser writes to derived
  data, removed direct browser Storage access, and introduced real PostgreSQL
  negative tests.
- Rebuilt upload, replacement, prefix deletion, URL-fetch, application-link,
  OCR, scan-claim, and readiness boundaries.

### Round 2 — Backend warnings, recommendation integrity, and operations

- Hardened profile creation, match/advice creation, recommendation insertion,
  terminal actions, queue failures, notification attempts, and active-scan
  leases against races and partial transactions.
- Reduced recommendation query amplification and introduced deterministic
  rotation while preserving the remaining durable-work warning.
- Added exact dependency closures, pinned toolchains/images/actions, expanded
  CI, dependency inventories/SBOM, release/rollback/preflight/runbooks,
  retention inventory, and governance files.
- Added stable error contracts, cost-aware limits, no-store export behavior,
  calibrated-fallback logging, and bounded decompression.

### Round 3 — Frontend behavior, accessibility, remaining data contracts, smoke

- Split public/protected/workspace route trees and simplified the global
  provider; fixed request ordering, caches, deep links, scans, recommendation
  mutations, drafts, and recovery surfaces.
- Added runtime response decoders for durable bootstrap/summary/scan state,
  accessible tabs/modal/status/output behavior, focus/contrast/touch/bidi
  improvements, and truthful consent/provenance/score language.
- Added v22 JSON-shape/workflow-state constraints with fresh and upgrade tests.
- Replaced the stale cleanup-unsafe production smoke with an explicit
  staging-only journey and protected workflow.
- Ran the secret guard, reviewed only non-secret false positives, and recorded
  narrow allowlist rules.

No applied fix was reverted. The sweep stops after this third non-critical
iteration; the remaining items below are explicit workstreams rather than
unbounded opportunistic changes.

## Detailed closure register

### Backend API, trust boundaries, and privacy

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| API-01 — Job-summary pagination returns no page | Fixed | `backend/app/api/routes.py` returns the typed page from the correct handler, supports 200/304/ETag, and removes unreachable code. `test_job_summary_route.py` covers success, empty, malformed cursor, ETag, and pagination. | Preserve the HTTP contract in route-level CI. |
| API-02 — Analyzed jobs are silently republished | Fixed | `JobCreateIn.contribute_public_posting` is explicit and false by default. Only the latest successfully fetched, verified public source can enter the shared catalog; pasted/failed/private content cannot. UI and privacy copy disclose the lifecycle. | Add formal catalog takedown/retention ownership before broad release. |
| API-03 — Upload validation is late/inconsistent | Fixed | CV and LinkedIn PDF routes stream `max+1`, share MIME/extension/PDF-magic/parser checks, parse before durable storage, and compensate failures. Boundary tests cover oversized, malformed, and inconsistent files. | Enforce equivalent body limits at the deployed proxy. |
| API-04 — Replacement/deletion can leave files | Mitigated | Replacements compensate and remove prior objects; account deletion enumerates the full canonical UUID prefix across pages, bulk deletes, and verifies empty. Storage/account tests cover failure and idempotency. | Add a durable deletion tombstone/saga, retry worker, backup proof, and retained non-content completion evidence. |
| API-05 — Environment mistakes enable dev auth | Fixed | `APP_ENV` is a closed enum with production default; dev auth is explicit and forbidden in staging/production. Startup validates secrets, PostgreSQL, HTTPS origins/URLs, sizes, and coupled settings. Key comparison is constant-time. | Exercise the startup matrix in deployed staging. |
| API-06 — Rate-limit identity trusts forwarding/tokens | Mitigated | Vercel uses its canonical signal; direct ASGI uses the socket peer. Every bearer bucket is also bounded by IP, deployed limits are distributed/fail-closed/batched, and expensive GETs have cost policies. | Move post-auth user quotas to verified subject identity and avoid database accounting before authentication where architecture permits. |
| API-07 — URL validation has DNS-rebinding window | Fixed | The fetch transport connects to the validated address while retaining original Host/SNI, disables ambient proxies, rejects mixed/private records, and re-resolves each redirect once. Network regression tests cover rebinding/redirect cases. | Add platform egress denial as defense in depth. |
| API-08 — Application links allow unsafe protocols | Fixed | Backend normalization accepts only absolute HTTP(S) host URLs; frontend repeats the defensive policy and uses `noreferrer noopener`. | Keep protocol validation on every new source adapter. |
| API-09 — OCR can be monopolized by hostile PDFs | Mitigated | Worker now streams bounded input, authenticates/validates framing first, caps pages/page pixels/aggregate pixels/concurrency, applies aggregate deadlines, and reports real language/MuPDF readiness. Seventeen tests cover limits. | Isolate native parsing/OCR in killable resource-limited subprocesses and add real adversarial native fixtures. |
| API-10 — Health does not establish readiness | Mitigated | Backend `/api/ready` checks configuration and database; OCR `/ready` verifies required languages, MuPDF, and capacity while liveness remains cheap. | Add bounded provider Auth/Storage/queue readiness and deployed alerting without mutating user data. |
| API-11 — Errors advertise nonexistent support | Mitigated | Server error copy retains a reference code without claiming a support path exists. Trace IDs remain stable/redacted. | Establish a monitored privacy-safe support channel, owner, and SLA, then link it from errors/privacy. |
| API-12 — Notification controls and disclosure disagree | Fixed | Discover exposes current discovery enrollment and notification preference independently, with save/failure feedback; privacy copy matches the controls. | Verify verified-email/unsubscribe behavior in staging. |
| API-13 — BFF lacks cancellation/error contract | Fixed | BFF forwards aborts, applies timeouts, allowlists request/response headers, maps transport/timeouts to stable no-store JSON errors, and exposes only approved metadata. Policy tests cover both directions. | Add browser tests for disconnect and timeout behavior. |
| API-14 — Signup abuse controls rely on assumptions | Mitigated | Signup enforces same-origin intent, canonical Vercel IP handling, bounded normalized inputs, stable 4xx/429/503 semantics, and distributed IP/email buckets. | Add risk-based challenge only if observed abuse warrants the accessibility/privacy cost. |

### Supabase schema, migrations, and tenant isolation

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| DB-01 — Fresh-install schema is behind the app | Fixed | `supabase/schema.sql` is the canonical disposable fresh snapshot through v22 and contains recommendation feedback, scan leases, tenant keys, Storage privileges, and data contracts. Schema-contract tests pin it. | Regenerate/compare it from a real Supabase reset in CI. |
| DB-02 — Filename order is not dependency order | Mitigated | `supabase/migrations/README.md` records the actual release order, forbids renaming applied history, and requires unique 14-digit UTC timestamps for new migrations. README/preflight no longer instruct lexical application. | Reconcile every deployed environment's historical versions with Supabase migration state before automation. |
| DB-03 — RLS does not verify parent ownership | Fixed | v19 and the snapshot add composite owner keys/FKs for every audited parent-child link. Two-tenant PostgreSQL tests attempt hostile cross-owner references and require FK rejection. | Extend the matrix whenever a new tenant-owned relation is added. |
| DB-04 — Browser can forge backend-derived data | Fixed | v19 revokes browser DML on public tables, grants only required owner reads, drops broad writable policies, and preserves service-role writes. PostgreSQL assertions inspect privileges and policies. | Prefer narrow backend/RPC actions if direct user writes are reintroduced. |
| DB-05 — Storage RLS bypasses document policy | Fixed | v21 removes all authenticated Storage policies/DML and keeps profile-document operations backend/service-role mediated. Fresh and upgrade tests prove browser denial and service-role privilege. | Run a real Supabase service-role upload/read/delete and browser-denial smoke before deploying v21. |
| DB-06 — No real migration/RLS verification | Mitigated | CI/local harness uses real PostgreSQL 16 for fresh schema, v18→v22 upgrades, privileges, RLS, hostile FKs, active uniqueness, JSON/state rejection, and Storage grants. | Add Supabase CLI reset plus real Auth, Storage, PGMQ, and multi-session concurrency tests. |
| DB-07 — `schema.sql` is unsafe/ambiguous | Fixed | It is explicitly fresh-install-only, current through v22, and existing environments must use recorded forward migrations. Policy creation is aligned with the snapshot contract. | Never use the snapshot to reconcile an existing project. |
| DB-08 — Structured durable data is unchecked text | Mitigated | v22 validates all 26 audited structured-text columns as the expected JSON object/array, failing on malformed or wrong-shaped historical/new values; the PG harness proves rejection. | Move high-value payloads to versioned `jsonb` schemas and reject unknown payload versions, not only top-level shape. |
| DB-09 — Workflow states are unconstrained | Fixed | v22 constrains agent-run states, agent-step states, positive attempts, and step output shape in both snapshot/migration; tests reject illegal states. | Add compare-and-set transition functions if these workflows become independently concurrent. |

### Backend concurrency, transactional integrity, and data quality

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| BE-01 — Skipped clarification violates production schema | Fixed | v18/snapshot allow `open`, `answered`, and `skipped`; application and PostgreSQL contract agree and onboarding tests cover skip. | None beyond the migration rollout. |
| BE-02 — Migration history has duplicate prefixes | Mitigated | Historical files remain stable; actual order is explicit; all new migrations have unique full timestamps; fresh and representative upgrade paths are tested. | Inspect deployed migration tables and use reviewed `migration repair`; applied history cannot safely be renamed blindly. |
| BE-03 — Async upload routes block the event loop | Fixed | Async handlers perform bounded reads then move synchronous storage/parsing/database work to FastAPI's worker pool. Twenty-two focused upload/storage tests pass. | Move long OCR/analysis to durable workers as load grows. |
| BE-04 — First-profile creation is check-then-insert | Fixed | `get_or_create_profile` recovers `IntegrityError`, rolls back, and refetches the concurrent winner; race simulation passes. | Add a true two-connection PostgreSQL race test or native upsert. |
| BE-05 — Scan claiming is not atomic | Fixed | v20 adds partial unique active input and lease token. Create recovers unique races; claim/finalize/heartbeat/cancel/recovery use conditional token-aware updates with attempt ceilings. | Add real PGMQ multi-worker timing/fault tests and lease/backlog metrics. |
| BE-06 — Recommendation transaction/lease unsafe | Mitigated | Failed transactions roll back before failure recording; unique inserts use savepoints/winner reload; terminal actions are conditional; malformed/exhausted messages archive; attempts cap at three. | Add renewable claim tokens, scheduled retry/DLQ/replay/alerts, and real two-worker fault injection. |
| BE-07 — Recommendation generation is N+1/request-bound | Mitigated | Existing jobs/decisions are bulk loaded and query-count tests prevent regression. | Bulk-load candidate facts/sources and enqueue per-candidate durable scoring outside a serverless request. |
| BE-08 — Candidate/backlog starvation | Mitigated | Stable per-job candidate rotation reduces repeated first-250 bias. | Persist oldest-first/keyset coverage cursors and alert on cohort coverage/oldest unprocessed age. |
| BE-09 — Discovery is not scheduled by deployment | Residual | Endpoint, kill switch, explicit UUID cohort, and scheduler/Vault preflight exist, but no repository-owned deployed schedule evidence exists. | Choose one authoritative scheduler/IaC path, attach secret reference and health evidence, or remove unused privileged extensions. |
| BE-10 — Incomplete profiles can be scored | Fixed | A centralized matchable-profile invariant requires ready/current/readable evidence at create, scan, rematch, and recommendation entry points. | Keep all future scoring entry points behind the same invariant. |
| BE-11 — Gzip expands before its cap | Fixed | Goozali decompression streams into a bounded buffer and aborts as soon as expanded bytes exceed the limit. | Add corpus/fuzz coverage for alternate encodings. |
| BE-12 — Notifications can duplicate/strand | Mitigated | Delivery has persisted idempotency keys, stale-sending lease, five-attempt ceiling, exponential backoff, preference recheck, suppression, safe error state, and malformed-message archival. | Make claim/queue creation atomic, renew visibility, add provider reconciliation plus operational DLQ/replay/metrics. |
| BE-13 — Calibration reinforces exposure/dismissal bias | Mitigated | Logistics/preference dismissals no longer become relevance negatives; events deduplicate; refresh moved off the user action path and is rate-limited. | Build contextual exposure/outcome events, offline segmented aggregation, uncertainty, holdout/control, drift and rollback guardrails. |
| BE-14 — Search limits before filtering | Fixed | Normalized SQL predicates apply before `LIMIT`, so older matching rows are reachable. | Add the appropriate production search index/plan evidence. |
| BE-15 — Pasted jobs bypass validation | Fixed | Pasted and fetched descriptions share minimum meaningful-content validation; pasted content is explicitly ineligible for shared catalog contribution. | Add language-aware meaningful-content checks if the beta expands. |
| BE-16 — Persisted bounds/checks incomplete | Mitigated | Requirement strings are normalized, length-bounded, and case-insensitively deduplicated; v22 adds structured/state checks. | Add remaining database enum/range/source/event checks and audit every persisted free-text field. |
| BE-17 — Export is large/unstreamed/cache-unsafe | Mitigated | Export response is private/no-store attachment and UI announces completion/failure. | Generate a quota-bounded asynchronous/streamed expiring export with audit evidence. |
| BE-18 — CV-derived PII is duplicated | Residual | Storage/DB replicas are inventoried and included in export/deletion; access is backend-mediated. The product still retains original PDFs and extracted plaintext. | Approve purpose/retention for each replica and minimize/expire one where feasible, including backups/processors. |
| BE-19 — Invalid beta IDs fail silently | Fixed | UUID configuration parsing fails startup with the offending variable context; no silent discard can alter cohort state. | Move cohort membership to an audited admin workflow if it grows. |
| BE-20 — Expensive reads have no cost limit | Fixed | Export, workspace/bootstrap, jobs/summary, and recommendation reads have explicit deployed distributed policies. | Tune budgets using observed latency/cost and verified subject quotas. |
| BE-21 — Raw exceptions become persisted/UI state | Fixed | Failure paths store stable public codes/messages; restricted diagnostics remain trace-linked logs. | Apply the same pattern to every new provider integration. |
| BE-22 — Calibration fallback is silent | Fixed | Startup/runtime logs distinguish disabled/loaded/invalid, include artifact version/checksum/knots, and preserve deterministic safe fallback. Tests assert invalid visibility. | Wire these signals to the deployed alerting surface. |

### Frontend correctness, state, and workflow behavior

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| FE-01 — Protected workflow routing is client-enforced | Fixed | `(protected)/layout.tsx` authenticates before render; `(workspace)/layout.tsx` enforces onboarding before `Shell`. Public pages stay separate. Browser checks confirmed protected redirects. | Add authenticated route-guard E2E regression tests. |
| FE-02 — Provider became a hand-built server-state framework | Mitigated | `AppDataProvider` no longer owns routing, auth subscriptions, or session persistence; bootstrap is single-flight and request-versioned. | Split remaining profile/jobs/pagination/mutation state by feature or adopt a tested server-state library. |
| FE-03 — Detail prefetch can leave inspector loading forever | Fixed | Keyed promise pooling shares hover/selection, tracks per-job loading/error, releases failures, supports retry, and ignores stale results. | Add rendered failure/retry tests. |
| FE-04 — Durable scan UI duplicates/loses active work | Fixed | UI resumes `/job-scans/active`, uses exponential visibility-aware polling and abort, and blocks duplicate submission; backend v20 guarantees one active input and token claim. | Prefer server events or `Retry-After` when operationally justified. |
| FE-05 — Concurrent recommendation actions lose updates | Fixed | Functional removals compose; per-ID operation gates allow different cards while blocking duplicates; errors are item-scoped. | Add component tests for simultaneous save/dismiss. |
| FE-06 — Discovery draft, persistence, and consent conflated | Fixed | Draft/persisted interests have explicit save/discard; discovery enrollment and email notifications are separate controls and requests. | None material. |
| FE-07 — Home metrics/feedback misrepresent state | Fixed | UI distinguishes loaded vs total records, exposes profile readiness, and reports action/scan failures rather than implying success. | Keep product copy in user-journey tests. |
| FE-08 — Onboarding duplicates work and is not resumable | Residual | Progress, cancellation, disclosure, and review gates improved, but file selection/analyze and final onboarding can still repeat analysis and workflow state remains local. | Create a durable onboarding state machine/process ID, reuse artifacts, and support resume/back across devices. |
| FE-09 — Onboarding choices not faithfully reflected | Residual | Review is explicit, but an empty skill selection can still collapse to select-all, matching is not ID/canonical based, skip lacks undo, and preview uses broad matching. | Use stable fact/skill IDs, preserve explicit empty sets, add undo, and derive preview only from selected evidence. |
| FE-10 — Browser OCR heavy, silent, uncancellable | Mitigated | Page/pixel/aggregate limits, coverage/truncation disclosure, abort propagation, and render/worker/document cleanup are implemented. | Select/detect language, self-host/cache assets, and offer server fallback before the large multilingual download. |
| FE-11 — Profile source save is non-transactional | Mitigated | UI serializes the operation and reports step-specific partial failure without discarding drafts. | Add one idempotent backend orchestration endpoint with source compensation/deletion. |
| FE-12 — Profile mutations discard drafts/race snapshots | Fixed | Mutations serialize, dirty refresh is guarded, drafts survive failures, optimistic changes roll back/rethrow, and partial errors stay visible. | Move toward resource versions/patch semantics long term. |
| FE-13 — Requirement correction mutates unexpectedly | Fixed | Display case is retained, dedupe is case-insensitive, values cap at 160, cancel restores the original, and expander/control relationships are explicit. | Add edit/cancel DOM regression tests. |
| FE-14 — Cache freshness/shape/privacy unsafe | Fixed | Sensitive session-storage payload caching is removed; legacy keys are cleanup-only; detail invalidation and durable bootstrap/summary/scan decoders guard stale/malformed data. | Explicitly classify any future browser cache. |
| FE-15 — Refresh orchestration duplicated/unhandled | Fixed | Provider refreshes are awaitable/guarded and consumers no longer launch duplicate unhandled refresh paths. | None material. |
| FE-16 — Handwritten contracts lack runtime validation | Mitigated | `api-contracts.mjs` validates workspace bootstrap, profiles, summary pages, and complete/nullable scan responses. Invalid successes become redacted `502 INVALID_RESPONSE_CONTRACT`. | Extend validation to remaining profile, jobs, recommendations, notification, export, and mutation endpoints; generate from OpenAPI/schema. |
| FE-17 — Public routes ship authenticated runtime | Fixed | Route groups keep auth/provider/workspace runtime out of login, recovery, and privacy; production root design preview is not imported. | Add bundle-budget evidence in CI. |
| FE-18 — App-level recovery surfaces missing | Fixed | Branded route/global error and not-found surfaces exist; recovery submission uses exception-safe cleanup. | Add E2E coverage for thrown route, offline, expired recovery, and retry. |
| FE-19 — Logout/post-deletion cleanup unverified | Mitigated | Logout awaits Supabase sign-out and clears workspace caches. | Centralize cookie removal/session revocation server-side; deletion still mirrors cookie attributes manually. |
| FE-20 — Export memory-heavy/no announcement | Mitigated | Completion/error is announced and the backend marks a no-store attachment. | Stream or asynchronously generate the export; the browser still materializes/stringifies/blobs it. |

### UX, product design, and accessibility

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| UX-01 — Tabs lack ARIA tabs pattern | Fixed | Inspector implements `tablist`/`tab`/`tabpanel`, roving `tabIndex`, selected/control relationships, and Arrow/Home/End keyboard behavior. | Add axe and keyboard automation. |
| UX-02 — Dynamic removal/overlays lack focus management | Mitigated | Long-task overlay is a real modal with initial/restore focus, trap, inert background, Escape, and scroll containment. | After recommendation removal, deterministically focus the next card or section heading. |
| UX-03 — Live regions are noisy and incomplete | Mitigated | Elapsed time is hidden from AT; progress announces stage/milestones; notices use status/alert semantics. | Standardize a shared Notice/announcer primitive and test frequency. |
| UX-04 — Inputs/focus states not programmatic | Fixed | Clarifications/facts have labels; mixed checkbox semantics and `focus-within` are present; recovery has username autocomplete context. | Maintain with component/axe coverage. |
| UX-05 — Contrast/typography too faint | Mitigated | Muted contrast increased and rejection no longer relies on opacity. | Replace remaining 8–10px labels with minimum accessible type tokens and verify contrast in every theme. |
| UX-06 — Touch geometry misses 44px target | Mitigated | Primary actions/navigation/logout meet the target. | Audit/expand remaining compact/icon/interest targets (roughly 30–42px). |
| UX-07 — Selection lacks durable navigation/mobile shift | Fixed | `?job=` persists selection/deep link/back context; mobile scrolls and focuses the inspector. Browser redirect preserved `/discover?job=42`. | Add back/forward history tests. |
| UX-08 — Evidence visualization duplicates/fabricates | Mitigated | Missing components display “Not scored,” gaps are explicit, and keyboard semantics improve. | Replace alias/substrings with backend evidence IDs and make the orbit one synchronized or noninteractive representation. |
| UX-09 — Coherent visual system, brittle CSS | Mitigated | Broken animation/keyframe behavior is corrected. | Extract tokens/primitives/feature styles, remove overrides/dead selectors, and add visual regression. |
| UX-10 — No multilingual rendering strategy | Mitigated | User content uses `dir="auto"` and bidi-safe rendering. | Add locale metadata, RTL tokens/layout, script-appropriate fonts, and language-aware OCR loading. |
| UX-11 — Profile too dense on mobile | Residual | Some grouping/collapse improved, but Profile remains one long mutation-heavy route. | Split into resumable sections/routes with overview and sticky section navigation. |
| UX-12 — Privacy copy is not a formal policy | Residual | Copy now honestly covers contribution, storage mediation, retention gaps, automated guidance, and beta limitations. | Legal/product must supply controller/contact, processors/regions/transfers, legal bases, periods, age/rights procedure, Terms, and versioning. |
| UX-13 — Implementation language leaks into product | Residual | Several labels are clearer, but “Agent workflow” and raw execution-step framing remain. | Rewrite as “How this match was evaluated,” limitations, evidence, and user next steps. |
| UX-14 — Smaller mobile/keyboard omissions | Mitigated | Skip link, `100dvh`, date fallback, private noindex, normal prefetch, title updates, and narrow-layout overflow checks are present. | Add system/light theme and full device-plus-keyboard E2E matrix. |

### Frontend minor/latent register

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| FE-M01 — Safe `next` ignored | Fixed | Login uses shared origin/allowlisted `safePostLoginPath`; tests reject external, scheme-relative, backslash, and relative destinations. | Keep the route allowlist current. |
| FE-M02 — Search shows stale results/no abort | Fixed | Superseded transport aborts and stale results clear with query changes. | None material. |
| FE-M03 — Pagination watermark dropped | Fixed | Bootstrap watermark remains in state and load-more sends the same snapshot watermark; policy test pins it. | None material. |
| FE-M04 — Detail cache survives refresh | Fixed | Changed summary material invalidates matching full-detail cache entries. | Extend comparison when summary fields grow. |
| FE-M05 — Weak relabeled Possible | Fixed | UI preserves backend strength vocabulary. | Calibrate vocabulary centrally later. |
| FE-M06 — Unknown provenance called Community | Fixed | Verified community/public/other sources have truthful distinct labels. | Handle new enum values explicitly. |
| FE-M07 — Durable upload called preview | Fixed | Disclosure appears before/during file operation and explains upload/storage/analysis. | Temporary-upload semantics remain preferable with backend support. |
| FE-M08 — Recovery cleanup inconsistent | Fixed | `try/catch/finally` always releases loading and gives stable failure copy. | None. |
| FE-M09 — Fact/accordion relationships incomplete | Fixed | Labels, IDs, expanded/control relationships, and panels are explicit. | Add axe coverage. |
| FE-M10 — Named score div has no role | Fixed | Score is semantic `<output>`. | None. |
| FE-M11 — OCR cleanup incomplete | Fixed | Render tasks, workers, documents, object URLs, and temporary handles clean in outer `finally`. | Stress repeated cancel/restart. |
| FE-M12 — Invalid date has no fallback | Fixed | Invalid input uses a safe fallback; locale policy is `en-IL`. | Centralize if date surfaces multiply. |
| FE-M13 — Production bundles design preview | Fixed | Root production route no longer imports/renders the fake preview. | Delete or isolate the remaining source if no longer used. |
| FE-M14 — No frontend telemetry | Residual | Browser runtime still lacks structured privacy-safe error/Web Vitals/workflow telemetry. | Select a processor/retention/redaction policy, then implement release/environment/trace correlation. |
| FE-M15 — No frontend test/lint layers | Mitigated | Twenty-eight policy/contract/concurrency tests plus CI typecheck/build now exist. | Add ESLint, DOM/component, MSW, Playwright, axe, and visual gates. |
| FE-M16 — TypeScript strictness gaps | Residual | `allowJs`/`skipLibCheck` and missing stricter optional/index checks remain. | Migrate JS and generated contracts, then enable flags incrementally. |
| FE-M17 — Dead/broad exports blur ownership | Mitigated | Provider/auth responsibilities were removed, but `api.ts` remains broad and some exports/assets are likely unused. | Run export/dependency audit and split API modules by feature. |
| FE-M18 — Navigation prefetch disabled | Fixed | Main links use normal Next prefetch. | Measure rather than globally disable. |
| FE-M19 — Metadata minimal | Mitigated | Private/auth pages have robots restrictions and route titles; auth mode updates document title. | Add public canonical/social/theme metadata and complete icons. |
| FE-M20 — Dark mode mandatory | Residual | Product remains dark-only. | Add persisted system/light/dark choice and verify contrast in every mode. |

### Matching, recommendations, and model governance

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| MATCH-01 — Education/logistics scores semantically shallow | Residual | User-facing copy no longer presents the score as an employment prediction, but matcher semantics still grant education for non-empty text and use shallow unknown/authorization/availability defaults. | Introduce typed required/preferred/known/unknown/conflict degree, field, jurisdiction, sponsorship, availability, and work-mode states with domain fixtures. |
| MATCH-02 — Location/seniority heuristics have hidden assumptions | Residual | No safe repository-only adjustment could establish the missing domain policy. Fixed-year seniority defaults and a narrow Israel place list remain. | Maintain a geography/remote model; version seniority by role family; expose unresolved/cap provenance in user language. |
| MATCH-03 — 0–100 implies unsupported calibration | Mitigated | UI calls it “evidence alignment,” explicitly says it is not interview/offer probability, exposes bands/evidence, and scoring logs calibration artifact/fallback identity. | Freeze a diverse human-reviewed grouped benchmark, inter-rater protocol, uncertainty, segment reporting, and published limitations before stronger claims. |
| MATCH-04 — Explainability lacks typed provenance | Mitigated | UI no longer invents absent component numbers and labels them “Not scored.” | Backend must emit versioned component/fact/source/requirement IDs, contribution, state, uncertainty, and cap reason; remove substring reconstruction. |
| MATCH-05 — Taxonomies duplicated/uneven | Residual | Runtime decoders reduce some drift but Python/TypeScript interest taxonomies and other domain options remain hand-maintained and technology-heavy. | Establish one versioned ontology/schema and generate server/client options/types/decoders with non-tech coverage fixtures. |
| MATCH-06 — Feedback is weak/contaminated signal | Mitigated | Browser DML is revoked; contribution is explicit; unique/idempotent events recover races; logistics/preference dismissals are excluded from global relevance negatives; calibration moved off action path. | Record immutable exposure context/position/variant, separate correctness/preference/logistics labels, and require segment/holdout/uncertainty controls. |

### Dataset and evaluation governance

| ID and original finding | Status | Evidence | Required workstream |
| --- | --- | --- | --- |
| DATA-01 — Acquisition/artifact lineage not reproducible | Residual | Raw/derived data remain ignored and no checked-in machine-readable source/artifact manifest binds object IDs, checksums, license, purpose, approval, parents, and runtime. | Add validated manifests plus immutable controlled-object/DVC IDs; CI verifies every lineage edge. |
| DATA-02 — “Privacy-safe” headings can retain identifiers | Residual | Heading filter still relies on digits/URL/non-ASCII/length and a small exact blocklist. | Use approved taxonomy allowlist, PII/NER scan, k-anonymity/frequency floor, and human approval before materialization; downgrade the current claim. |
| DATA-03 — Audit sampling deterministic but biased | Residual | Script still samples leading rows from first/middle/last Parquet row groups. | Seeded stratified/reservoir sampling across source/file/role/time/stage; persist seed and row hashes; report confidence intervals. |
| DATA-04 — Dataset tools lack preflight/locks | Residual | Dataset scripts import `pyarrow`/`python-docx` without a dedicated locked tool environment or input/license/schema preflight. | Add isolated exact/hash lock and an executable manifest/checksum/schema/license/disk/tool-version preflight. |
| DATA-05 — Label/calibration gates lack representation | Residual | Aggregate split minimums exist, but empty-feature rows and missing role/source/stage/outcome/language/time segments can still pass. | Non-overridable segment floors, grouped splits, reviewer adjudication, frozen benchmark, and published limitations. |
| DATA-06 — Evaluation export trusts stored JSON | Residual | Export still emits stored feature dictionaries without unknown-key/type rejection or PII/secret approval gate. | Versioned per-example allowlist, strict typing, PII/secret scan, checksum, and explicit share approval. |
| DATA-07 — License governance is prose-only | Residual | Dataset rights remain narrative and are not bound to each source/derivative artifact. | Require SPDX/license/purpose/redistribution/attribution/reviewer/expiry in manifests; CI blocks unapproved lineage. |

### Dependencies, supply chain, and licensing

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| DEP-01 — Frontend dependencies have advisories | Fixed | Lock contains Next 16.2.12, PostCSS 8.5.25, sharp 0.35.0; production `npm audit` reports zero vulnerabilities; Dependabot/CI remain. | Regression-test upgrades and keep audit blocking. |
| DEP-02 — Pillow old at hostile boundary | Fixed | OCR locks Pillow 12.3.0 and the expanded 17-test suite passes. | Complete native adversarial OCR tests. |
| DEP-03 — PyMuPDF licensing decision absent | Residual | PyMuPDF 1.28.0 is pinned and `THIRD_PARTY_NOTICES.md` truthfully records the unresolved AGPL/commercial decision; project `LICENSE` is still absent. | Accountable legal decision, entitlement/compliance evidence, project license, notices, and backend/OCR/image SBOMs. |
| DEP-04 — Backend builds not reproducible | Mitigated | Python is 3.12-only, `.python-version` is exact, complete runtime/dev closures are exact, clean Linux installs and `pip check` passed, CI installs the lock. | Add portable reviewed hashes and enforce `--require-hashes`/equivalent; reduce dual-source drift. |
| DEP-05 — Toolchains/containers weakly pinned | Mitigated | Python/Node/npm, Actions SHAs, and OCR base digest are pinned; native versions are inventoried. | Hash pip artifacts, snapshot apt, pin PG test image digest, and add image SBOM/scan/signing/provenance. |
| DEP-06 — Governance metadata absent | Mitigated | Security, contribution, changelog, notices, Dependabot, PR template, ownership register, CI, and CODEOWNERS placeholder exist. | Assign accepted owners/handles, activate rules/protected review, private security channel, license, and non-frontend SBOMs. |

### Test strategy and release controls

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| TEST-01 — No CI quality gate | Mitigated | SHA-pinned `quality.yml` runs backend/OCR/frontend/PostgreSQL tests, type/build/audit, inventories/SBOM, image readiness, and contracts; `staging-smoke.yml` provides a protected environment journey. | Prove remote runs, make quality checks required, add lint/static/coverage/secret/license/image scan and immutable promotion. |
| TEST-02 — Backend tests do not cross HTTP boundary | Mitigated | TestClient coverage now includes summary pagination/ETag, active scans, health/readiness and selected upload/error boundaries. | Build authenticated/unauthenticated HTTP contract matrices for every route, ownership/failure/middleware/serialization case. |
| TEST-03 — DB tests use SQLite | Mitigated | Real PostgreSQL 16 fresh and v18→v22 upgrade harness covers tenant FKs, RLS/grants, Storage, active uniqueness, JSON/state constraints. | Add local Supabase/Auth/Storage/PGMQ and real multi-session concurrency/deletion tests. |
| TEST-04 — Frontend has no tests/lint | Mitigated | Twenty-eight Node tests cover auth/BFF/OCR/pagination/concurrency/contracts; typecheck/build run in CI. | Add ESLint, React DOM/component/MSW, Playwright, axe, visual and network-failure journeys. |
| TEST-05 — OCR tests are narrow | Mitigated | Seventeen tests cover stream size, overload, deadlines, cache, page/aggregate pixels, readiness/languages/token; CI builds/probes the image. | Add real synthetic PDF→MuPDF→Tesseract and malformed/render-bomb/fuzz/resource/subprocess-kill tests. |
| TEST-06 — Smoke stale and can orphan data | Mitigated | Smoke is staging-only, requires explicit HTTPS origins/secrets, admin-creates a marked synthetic user with known ID, uses current review/model contracts, deletes through backend, and verifies Auth absent/Storage empty. Unit tests cover safety configuration; protected workflow exists. | Execute it against isolated staging and make successful evidence a promotion requirement. |
| TEST-07 — No coverage/static-analysis discipline | Residual | TypeScript typecheck exists, but no coverage threshold, Ruff/type checker/formatter, ESLint, or changed-line ratchet. | Introduce pragmatic baselines and changed-line gates, then raise them gradually. |

### Operations, reliability, and privacy program

| ID and original finding | Status | Remediation and evidence | Remaining action |
| --- | --- | --- | --- |
| OPS-01 — Backup/restore/incident/key operations unfinished | Mitigated | Operations runbook defines triage, containment, credential rotation, restore/deletion drills, evidence and queue response. | Assign primary/backups; approve SLO/RPO/RTO; verify provider capabilities; execute/retain restore, deletion, rotation, and tabletop evidence. |
| OPS-02 — Retention partially defined | Mitigated | Retention inventory covers Auth/DB/Storage/queues/catalog/metrics/evaluations/notifications/logs/OCR/CI/backups/incidents; abandoned onboarding cleanup is implemented. | Approve every period/legal basis/owner/backup behavior and implement observable idempotent cleanup across processors. |
| OPS-03 — Observability has no operating surface | Mitigated | Health/readiness, trace IDs, timing, redacted logs, stable errors, and scan reference codes exist. | Deploy structured telemetry, dashboards, journey/service SLOs, alert sink, queue/OCR/extraction/browser correlation. |
| OPS-04 — Queue recovery can lag a day | Residual | Daily Vercel recovery remains because the repository documents a Hobby-plan constraint. | Move to minute-level managed scheduling before scale and alert on oldest queued/running age. |
| OPS-05 — Scheduling/config drift-prone | Mitigated | Environment inventory, strict startup checks, explicit UUID parsing, and Cron/Vault/staging evidence preflight exist. | Declare provider schedules/secrets in managed IaC and automate drift/status checks. |
| OPS-06 — Frontend/backend regions distant | Residual | Frontend remains `fra1`; backend remains `sin1`; user/database geography evidence is unavailable. | Measure BFF→backend/user/database latency and co-locate or record/monitor an explicit tradeoff. |
| OPS-07 — Release docs not repeatable process | Mitigated | Living release/rollback/preflight/dependency policy, release record, canary and migration compatibility process now exist. | Assign approvers/commander, define thresholds, enforce workflows, promote immutable artifacts, and execute one rehearsal. |
| OPS-08 — Secret exclusion too broad | Fixed | Broad doc exclusion is removed. Changed files pass secret-guard; false positives have narrow value/identifier rules with owner/re-review notes. | Assign the currently unassigned security/privacy owner and add explicit approval/expiry records. |
| OPS-09 — Documentation/repository drift | Fixed | OCR/config wording corrected; historical docs labeled; machine-local paths removed; ignore duplicates removed; PG README now says v18→v22; redacted audit evidence is checked in. | Continue owner/date/archive review as documents evolve. |

## Consolidated fix log

| Area | Material change | Primary evidence |
| --- | --- | --- |
| API correctness | Restored summary pagination contract, stable BFF errors, readiness, no-store export, input bounds | `backend/app/api/routes.py`, `frontend/app/backend/[...path]/route.ts`, route tests |
| Authentication/abuse | Closed environment enum/dev-auth/key/origin/IP/error fail-open paths; added startup invariants and cost limits | `backend/app/config.py`, `services/auth.py`, `services/rate_limit.py`, signup/auth/rate tests |
| Fetch/output security | Pinned validated DNS connections, redirect revalidation, no proxy, safe application URLs | `services/job_research.py`, `test_job_research_network.py`, frontend URL policy |
| Upload/OCR | Streamed `max+1`, unified PDF policy, parse-before-store, worker-pool offload, OCR body/pixel/deadline/concurrency limits | upload/storage tests; `ocr-worker/app/main.py`; 17 OCR tests |
| Privacy/catalog | Private-by-default jobs, explicit verified-public contribution, truthful disclosure/provenance | job schemas/services/UI/privacy tests |
| Storage/deletion | Full UUID-prefix enumeration, pagination defense, bulk delete, empty verification, replacement compensation, browser Storage removal | `services/storage.py`, `services/account.py`, v21, storage/account/PG tests |
| Database isolation | Composite tenant FKs, browser derived-write revoke, current snapshot, explicit release order | v19, schema-contract tests, hostile PG assertions |
| Scan durability | Partial unique active input, CAS lease claims, heartbeats, cancellation/finalization ownership, active-resume route/UI | v20, `services/job_scans.py`, scan route/product tests |
| Durable data contract | Expected JSON object/array checks, legal agent states/attempts on fresh and upgrade schemas | v22, schema-contract and PG rejection tests |
| Recommendation integrity | Rollback-safe failures, savepoint race recovery, conditional actions, attempts/archive, query reduction, rotation, reason-aware feedback | `services/recommendations.py`, `services/jobs.py`, 69 focused integration tests |
| Notification integrity | Provider idempotency key, stale lease, backoff/ceiling, suppression recheck, safe failures | `services/notifications.py`, notification tests |
| Frontend architecture | Server route guards, public/private trees, memory-only request-versioned provider, runtime durable-state decoders | route groups, `AppDataProvider`, `api-contracts.mjs`, 28 tests |
| Frontend workflows | Durable scan resume, keyed detail requests, functional recommendation updates, draft/persisted consent, serialized profile mutations | Home/Discover/Profile components and policy tests |
| Accessibility/UX | ARIA tabs, modal focus trap, reduced live noise, labels/output/skip link, contrast/touch/bidi, deep links, recovery/title fixes | components/global CSS and real-browser walkthrough |
| Supply chain | Exact Python locks, pinned Node/Python/Actions/OCR base, upgraded frontend/OCR packages, npm audit 0 | lock/manifests, dependency policy, CI |
| Release/operations | CI, staging synthetic workflow, current safe smoke, release/rollback/preflight/runbooks, retention/ownership/security/notices | `.github`, `backend/scripts/production_smoke.py`, operations docs |
| Secret hygiene | Removed broad suppression; reviewed changed files with redacted secret guard and narrow documented false-positive rules | `.secretignore`; final scan: no findings |

## Residual Iron Law register

These are not vague backlog notes. Each entry states the observable remaining
condition, its source, consequence, complete remedy, and why the sweep did not
pretend to close it.

### RIL-01 — Live migration, Storage, and deletion proof is still external

- **Symptom:** v19–v22 and the full deletion lifecycle are proven against stock
  PostgreSQL/stubs, not the actual Supabase Auth/Storage/PGMQ project. Historical
  migration IDs also require environment-specific reconciliation.
- **Source:** `supabase/tests`, `supabase/migrations/README.md`,
  `docs/ENVIRONMENT_AND_SCHEDULER_PREFLIGHT.md`.
- **Consequence:** Provider-specific grants, policies, extensions, object
  pagination, or applied-history state can differ from the local proof.
- **Remedy:** Restore production into isolated staging, run v22 data preflight,
  reconcile migration history, apply v19–v22, run service-role and browser-denial
  Storage checks, application upload/replace/read/delete/account-delete, active
  scan duplicate preflight, and retain redacted evidence plus rollback decision.
- **Why not applied:** This requires real staging credentials, provider state,
  an approved change window, and rollback authority that were not supplied.

### RIL-02 — Deletion and retention are not yet a durable privacy program

- **Symptom:** Request-time deletion is comprehensive/idempotent but has no
  persisted tombstone/saga/retry worker; most retention, backup, processor, and
  legal-basis fields remain unapproved.
- **Source:** `backend/app/services/account.py`, `services/storage.py`,
  `docs/DATA_RETENTION_INVENTORY.md`.
- **Consequence:** A provider outage can leave deletion incomplete, backups and
  public catalog copies have unresolved periods, and compliance cannot be proven.
- **Remedy:** Durable deletion workflow with step state/retry/reconciliation,
  non-content audit evidence, approved data-class periods/bases/owners, monitored
  cleanup, backup/processor verification, export parity, and takedown procedure.
- **Why not applied:** Retention periods, legal basis, controller obligations,
  provider backup capabilities, and audit retention require accountable
  privacy/legal/operations decisions.

### RIL-03 — Licensing and accountability have no accepted owner

- **Symptom:** PyMuPDF's AGPL/commercial path, the project license, real
  CODEOWNERS, private security channel, legal contact, and primary/backups remain
  explicitly unassigned.
- **Source:** `THIRD_PARTY_NOTICES.md`, `SECURITY.md`,
  `docs/OWNERSHIP.md`, `.github/CODEOWNERS`.
- **Consequence:** Distribution obligations, approval authority, incident
  response, privacy requests, and change review cannot be demonstrated.
- **Remedy:** Obtain the license/legal decisions, add required license/notices,
  accept named primary/backups and GitHub handles, activate CODEOWNER/protected
  review, and establish a monitored private channel with SLA.
- **Why not applied:** Inventing people, legal identities, contact routes, or
  license entitlement would be false and unsafe.

### RIL-04 — Supply chain is versioned but not integrity-hermetic

- **Symptom:** Python artifacts lack hashes; apt repositories/packages and the
  PostgreSQL test image remain mutable; final images lack complete SBOM,
  vulnerability scan, signature, and provenance.
- **Source:** `backend/requirements*.txt`, `ocr-worker/requirements*.txt`,
  `ocr-worker/Dockerfile`, `.github/workflows/quality.yml`.
- **Consequence:** A source-identical build can still consume changed/substituted
  artifacts without a blocking signal.
- **Remedy:** Portable hash-complete Python locks, snapshot/digest native and PG
  inputs, backend/OCR/image SBOMs, vulnerability policy, signing, provenance,
  and immutable promotion.
- **Why not applied:** Native snapshot/signing registries and release identity
  require selected infrastructure and credentials; generating nonportable local
  hashes would provide misleading assurance.

### RIL-05 — CI exists but enforcement and boundary coverage are selective

- **Symptom:** Workflows are not proven required on the remote protected branch;
  lint/static/coverage gates are absent; many API routes and rendered frontend
  journeys lack boundary tests.
- **Source:** `.github/workflows/quality.yml`,
  `.github/workflows/staging-smoke.yml`, backend/frontend test inventories.
- **Consequence:** Changes may bypass checks and auth/middleware/serialization,
  focus/accessibility/component/provider regressions can escape green helpers.
- **Remedy:** Required protected checks, remote run evidence, Ruff/type/format/
  ESLint/coverage ratchets, full HTTP ownership/failure matrix, DOM/MSW,
  Playwright/axe/visual journeys, and provider-shaped integration tier.
- **Why not applied:** Branch protection and environment approvals require
  remote repository authority; adding every test layer is a dedicated quality
  program beyond the bounded third sweep iteration.

### RIL-06 — Onboarding and client contracts still need structural redesign

- **Symptom:** Onboarding can duplicate analysis, cannot durably resume, and does
  not preserve every empty/skip/selection meaning; many API responses remain
  handwritten and unchecked. The provider and `api.ts` still span domains.
- **Source:** `frontend/components/OnboardingClient.tsx`,
  `onboarding/useCvPreview.ts`, `AppDataProvider.tsx`, `frontend/lib/api.ts`,
  `api-contracts.mjs`.
- **Consequence:** Users can repeat expensive work or see a preview inconsistent
  with decisions; unvalidated response drift and cross-domain invalidation remain.
- **Remedy:** Durable onboarding process/state machine with artifact reuse and
  undo/resume, stable fact/skill IDs, feature-sliced stores/API modules, and
  generated OpenAPI types plus runtime validators for every durable boundary.
- **Why not applied:** This changes the workflow/data contract across backend and
  frontend and needs an explicit product migration plan, not another local patch.

### RIL-07 — Accessibility/product polish is improved, not complete

- **Symptom:** Recommendation removal focus, compact touch targets, tiny labels,
  Profile mobile density, light/system theme, full RTL/localization, and
  implementation-oriented “Agent workflow” language remain.
- **Source:** `frontend/components`, `frontend/app/globals.css`, Profile and
  Opportunity Inspector surfaces.
- **Consequence:** Keyboard, low-vision, mobile, multilingual, and glare-sensitive
  users still encounter friction; technical concepts weaken product trust.
- **Remedy:** Shared focus/notice primitives, 44px audit, minimum type tokens,
  Profile information architecture, system/light/dark tokens, locale/RTL/font
  strategy, user-centered evaluation copy, and automated axe/device/visual tests.
- **Why not applied:** Profile IA, theme, localization, and terminology need a
  coordinated design/content decision and authenticated user testing.

### RIL-08 — Matching semantics, provenance, and calibration remain implicit

- **Symptom:** Education, sponsorship, availability, place, work mode, and
  seniority use shallow/narrow heuristics; the UI reconstructs evidence links;
  0–100 remains more precise than the validation evidence.
- **Source:** `backend/app/services/matcher.py`, `backend/app/schemas.py`,
  `frontend/components/home/OpportunityInspector.tsx`,
  `backend/tests/test_calibration.py`.
- **Consequence:** Missing evidence may receive favorable defaults, geography/
  role assumptions can exclude users, evidence can be misattributed, and small
  score differences can be overread.
- **Remedy:** Typed known/unknown/conflict/required/preferred domain states,
  maintained geography and role-family policies, versioned exact provenance,
  frozen human-reviewed grouped benchmark, inter-rater agreement, uncertainty,
  segment results, and published limitations.
- **Why not applied:** Correct values require domain research, representative
  labeled evidence, reviewer policy, and product approval; arbitrary heuristic
  changes could create new unfairness.

### RIL-09 — Feedback and recommendation work are not a durable fair work graph

- **Symptom:** Scoring remains a capped request-bound per-profile loop with fixed
  visibility, no renewable claim/DLQ/replay, no persisted coverage cursor, and
  observational global calibration. Notification claim creation also has
  remaining atomicity/reconciliation gaps.
- **Source:** `backend/app/services/recommendations.py`,
  `services/notifications.py`, `services/job_discovery.py`,
  worker routes.
- **Consequence:** Slow/crashed work can redeliver, cost scales linearly, users/
  jobs can starve, unknown provider outcomes can strand/duplicate mail, and
  exposure bias can alter global thresholds.
- **Remedy:** Per-candidate idempotent tasks, token claims with renewable
  heartbeat, retry schedule/DLQ/replay/metrics, bulk snapshots, persisted
  oldest-first cursors, provider reconciliation, contextual append-only events,
  offline segmented calibration with uncertainty/holdout/rollback.
- **Why not applied:** This is a queue/data-model/worker topology migration that
  needs the selected production queue, scheduler, SLOs, and staged load tests.

### RIL-10 — Dataset lineage, privacy, sampling, and rights are unenforced

- **Symptom:** No machine-readable artifact lineage/rights manifest or locked
  tool environment exists; heading privacy is heuristic; sampling is biased;
  evaluation export trusts arbitrary stored feature JSON; representation gates
  are aggregate-only.
- **Source:** `datasets`, `datasets/scripts`, evaluation export and label
  coverage code.
- **Consequence:** Results are not independently reproducible, identifiers can
  enter “privacy-safe” artifacts, rights detach from derivatives, and green
  evaluation can hide segment failure.
- **Remedy:** Immutable manifest/object IDs/checksums/runtime/SPDX/purpose/
  approval, isolated lock/preflight, allowlist+NER+k-anonymity+review, seeded
  stratified samples with row hashes/CIs, strict export schemas/PII scan, and
  non-overridable grouped segment floors.
- **Why not applied:** Source artifacts, rights records, representative data,
  reviewers, and acceptable segment policy were not available. Fabricating a
  manifest or benchmark would be worse than an explicit gate.

### RIL-11 — Operations procedures are not yet operating controls

- **Symptom:** Runbooks exist, but SLO/RPO/RTO, dashboards/alerts, backup/restore
  capability, drill evidence, minute-level recovery, declarative discovery
  scheduling, and region locality decision remain missing.
- **Source:** operations/release/preflight docs, `backend/vercel.json`,
  `frontend/vercel.json`.
- **Consequence:** Incidents, queue backlog, restoration, deletion verification,
  scheduler drift, and cross-region latency remain assumptions.
- **Remedy:** Assign owners, approve objectives, configure telemetry/alerts and
  managed schedules/IaC, execute restore/deletion/rotation/tabletop drills, and
  measure/co-locate or formally accept region tradeoffs.
- **Why not applied:** These require provider plans, production telemetry,
  organization contacts, schedules, and deployment authority.

### RIL-12 — Data minimization and large export remain incomplete

- **Symptom:** Original PDFs and extracted plaintext coexist; account export
  still materializes a large response in backend/browser memory.
- **Source:** `backend/app/services/profile.py`, `services/account.py`,
  `frontend/components/profile/AccountControls.tsx`.
- **Consequence:** More PII replicas expand breach/deletion/retention scope and
  large users can exhaust request/browser memory.
- **Remedy:** Approve the purpose/period for each replica, expire/minimize where
  feasible, include backups/processors, and generate a quota-bounded
  asynchronous/streamed encrypted expiring export with audit evidence.
- **Why not applied:** Retention purpose and export format/security require legal
  and product decisions plus durable object/job infrastructure.

### RIL-13 — Rate identity, provider readiness, and support loop are partial

- **Symptom:** Rate limiting still runs before full auth and uses bearer digest
  plus IP rather than a verified-subject quota; readiness does not prove every
  Supabase/queue dependency; no support channel accepts trace IDs.
- **Source:** `backend/app/services/rate_limit.py`, health/readiness routes,
  error/privacy UI.
- **Consequence:** Invalid requests still consume distributed accounting,
  provider outages can pass partial readiness, and blocked users cannot close
  the trace-ID feedback loop.
- **Remedy:** Post-auth verified-subject cost accounting, bounded provider
  readiness/circuit signals, and an owned privacy-safe support channel with SLA.
- **Why not applied:** Middleware reordering affects the global request path;
  provider probes and support ownership/contact policy require deployment and
  organizational decisions.

## Required release gates, in order

1. **Database rehearsal:** restore production to isolated staging, preflight
   v22 data/state, reconcile historical migration IDs, apply v19–v22, and attach
   fresh/upgrade/rollback evidence.
2. **Storage/deletion proof:** real service-role upload/read/replace/delete,
   direct browser denial, multi-page UUID-prefix deletion, Auth absence, and
   backup/deletion policy evidence.
3. **Legal/accountability:** resolve PyMuPDF/project licensing; assign owners,
   security/privacy contact, controller identity, processors/regions/legal
   bases/retention/takedown/Terms.
4. **Remote quality enforcement:** run and require `quality.yml`; configure the
   protected `staging` environment; execute `staging-smoke.yml`; retain run and
   immutable deployment/artifact identities.
5. **Operations:** configure minute-level queue recovery and discovery schedule,
   dashboards/SLOs/alerts, restore/deletion/rotation drills, and make the measured
   region decision.
6. **Model/data gate:** preserve “evidence alignment” limitations; do not make
   predictive/fairness claims or train from feedback until typed provenance,
   lineage/rights/privacy, representative grouped evaluation, uncertainty, and
   holdout controls exist.

## Architecture direction

Keep a modular monolith. The current risk is ambiguous ownership and
cross-feature state, not insufficient services.

- Organize backend/frontend by feature slices: profile/onboarding, jobs/scans,
  recommendations/notifications, account/privacy, and operations.
- Put Storage, public-job fetch, OCR, email, queue, and Supabase behind explicit
  ports/adapters so provider failures and tests share one contract.
- Model onboarding, scans, recommendation work, notification delivery, and
  deletion as explicit state machines with legal transitions, idempotency keys,
  token claims/heartbeats, retries, and terminal audit state.
- Use an outbox/durable-work pattern for cross-system side effects; never rely
  on a database transaction plus untracked provider call.
- Generate client contracts from an authoritative API schema and validate every
  durable response at runtime.
- Separate server state by domain and make invalidation/resource versions
  explicit; avoid expanding the global provider.
- Treat scoring policy, ontology, provenance, and evaluation artifacts as
  versioned domain contracts, not presentation helpers.
- Do not split into microservices until measured scaling/isolation needs and
  operational ownership justify the added failure surface.

## Final decision

Repository-level remediation is complete for this sweep: 59 detailed findings
are fixed and 51 are materially mitigated. The remaining 24 are explicit,
owned-by-decision workstreams, not silently ignored defects.

The code should remain **no-go for broad public launch** until the six release
gates above have evidence. A tightly controlled beta can proceed only after
gates 1–4, with discovery/email/model-claim kill switches kept off unless their
specific gates also pass.

The remediation worktree is intentionally uncommitted. The requested
pre-remediation baseline was committed first as `338ff36`; no remediation
commit or push was performed.
