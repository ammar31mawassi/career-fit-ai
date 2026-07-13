# CareerFit product intelligence and reliability release

Date: 2026-07-13  
Owner: Senior Full-stack Engineering  
Status: implementation complete; production verification recorded below

## Outcome

This release implements the CEO-approved next steps without replacing CareerFit's explainable matching model with an LLM. It makes long-running scans durable, turns user corrections into a privacy-safe evaluation set, exposes job-reader corrections in the product, adds consented job recommendations, removes read-time match recalculation, and fixes the remaining responsive layout failures found with real browser data.

## Before, issue, solution, after

| Before | Issue | Implemented solution | After |
|---|---|---|---|
| A scan lived inside one browser request. | Closing the tab or a serverless timeout could strand the work. | Persist `job_scans`, enqueue with Supabase PGMQ, poll saved progress, allow cancellation, reclaim an eight-minute stale lease, and fail safely after three attempts. | Scan state survives navigation and failures; active queue messages are archived only after a terminal state. |
| Progress was partially simulated by elapsed time. | Users could not tell which real stage was running. | The reader, classifier, matcher, and advice pipeline now commit named progress checkpoints. | The UI shows truthful stages, elapsed time, persisted progress, cancellation, and a support code. |
| Parser regressions were learned from user reports. | There was no privacy-safe way to compare extraction quality over time. | Store strategy, duration, input/output lengths, fallback reason, counts, version, status, error code, and trace ID without raw CV or job text. | Extraction behavior can be aggregated without creating a shadow copy of private documents. |
| Profile fact feedback existed but was difficult to use as a model dataset. | Random row-level splits could leak one person's patterns across train and test. | Create structured evaluation examples and assign a deterministic train/validation/test split by user. Add a redacted JSONL exporter. | Future evaluation is reproducible and grouped by person without exporting user IDs or evidence text. |
| A wrong experience or must-have extraction could dominate the match. | Users could not correct the job reader. | Add an extracted-requirements editor, retain original and corrected snapshots, record changed fields, and rematch immediately. | High-impact reader mistakes are visible, correctable, exportable, and useful as labels. |
| Opening a job or listing jobs could silently recalculate matches. | Read endpoints became slow, surprising, and write-heavy. | Remove recalculation from serialization; add an explicit stale-match warning and `Refresh match` action. | Reads remain reads and users decide when a changed profile should rematch a role. |
| Workspace bootstrap returned a growing job list. | Large libraries would slow every visit. | Add cursor pagination, a first-page bootstrap cursor/watermark, ETags, lazy detail fetching, and `Load more`. | Initial payload stays bounded and cached summaries remain fast to switch. |
| Shared-job scoring was an internal shadow experiment. | All-pairs scoring would be wasteful and candidate data use needed consent. | Add explicit profile consent, role-interest shortlist, seniority/experience/logistics checks, full scoring only for eligible candidates, and save/dismiss actions. | Strong relevant roles can be shown without exposing another candidate or scoring every job against everyone. |
| The scorer could only be replaced in code. | Outcome calibration could not be introduced safely later. | Add an optional monotonic piecewise calibration wrapper and offline Brier/ECE report. Keep deterministic blockers and caps authoritative; invalid artifacts fall back safely. | A small learned calibration layer can be introduced after enough labels without letting an LLM invent percentages. |
| API failures exposed generic messages. | Support could not connect a user-visible error to a request. | Add trace context, `X-Trace-ID`, `Server-Timing`, structured privacy-safe request logs, stable error codes, and support-code UI. | Failures are diagnosable without logging uploaded content. |
| The score ring placed its label with a negative margin. | `60%` and `Medium` overlapped with real job data. | Give the score and fit label explicit grid rows and line heights. | The ring remains legible at desktop and mobile sizes. |
| Inspector metrics inherited a five-column generic grid. | Labels wrapped one character per line inside the narrower inspector. | Override the inspector to a two-column metric grid and one column on small screens. | Match confidence, reader confidence, capture quality, and experience stay readable. |
| Every pending fact category opened by default. | A CV with many skills produced an unnecessarily long, overwhelming Profile page. | Open only the highest-impact pending category initially; preserve counts and all manual add/review actions. | The review page has a clear starting point and much lower initial visual load. |
| Mobile counters and long labels could shrink aggressively. | The review badge and card copy became narrow or visually collided. | Add no-shrink/nowrap counter behavior, `min-width: 0`, safe wrapping, container queries, stacked action controls, and 42px mobile targets. | No horizontal overflow was detected at 320, 390, 768, 1024, or 1440 CSS pixels. |

## Runtime architecture

### Durable scan lifecycle

1. `POST /api/job-scans` validates profile readiness, persists the normalized input, and sends a small `{scan_id, user_id}` PGMQ message.
2. The authenticated client immediately calls the process endpoint and polls the saved row. Closing the tab does not delete the row or queue message.
3. Each pipeline checkpoint commits progress so polling is independent of the processing request.
4. Cancellation changes queued work directly to `cancelled` or running work to `cancel_requested`; the next safe checkpoint stops processing.
5. The recovery worker reads with a visibility timeout. Healthy running work keeps its message; work with no heartbeat for eight minutes is reclaimed.
6. After three interrupted leases, the scan becomes safely failed with `SCAN_LEASE_EXPIRED` instead of retrying forever.
7. Terminal work is archived from PGMQ. A bounded worker invocation handles up to five queue messages and then one recommendation run within a 50-second scheduling budget.

Vercel Hobby Cron is configured for one daily recovery invocation. Interactive scans still start immediately. If traffic grows, increase the same worker endpoint's schedule on a plan that supports it or invoke it from a dedicated worker; the queue/data contract does not change.

### Recommendation pipeline

Recommendations are disabled by default. When a user opts in:

1. A scanned job is normalized into the shared catalog.
2. Candidate profiles are shortlisted by selected career field.
3. Cheap checks reject obvious seniority, experience, availability, and location mismatches.
4. Only the shortlist runs through the full evidence matcher.
5. Strong matches with no blocker become `available`; weaker rows stay internal observations for calibration.
6. Dismiss is optimistic and reversible on request failure. Save clones the catalog job into the user's private library and creates a normal evidence-backed match.

The catalog stores job content, never candidate facts. Candidate scores and evidence remain user-owned.

### Model boundary

The default scorer is still `DeterministicMatchScorer`. An optional `PiecewiseCalibratedScorer` may map the raw score through monotonic knots loaded from `SCORE_CALIBRATION_PATH`. Calibration cannot raise a score when deterministic blockers or eligibility caps exist. The artifact version is appended to the model version and the pre-calibration score remains in the feature snapshot.

Training is intentionally not automated. The release adds:

- `backend/scripts/export_evaluation_dataset.py` for privacy-safe JSONL features and labels;
- `backend/scripts/calibration_report.py` for Brier score, expected calibration error, coverage, and bin statistics;
- stable user-grouped splits;
- correction labels from fact review and job-requirement review.

The next model should be trained only after label coverage is adequate across role families and career stages.

## Security and privacy decisions

- RLS is enabled on all new user-owned tables.
- Extraction metrics and evaluation rows have client-deny policies and are backend-only.
- No raw CV, LinkedIn text, GitHub content, job description, fact value, evidence sentence, email, URL, or user ID is written into telemetry feature JSON.
- User account export includes original/corrected requirement history so corrections are not hidden from the data subject.
- PGMQ payloads contain only internal IDs.
- Worker access uses a sensitive `CRON_SECRET` and constant-time comparison.
- Request logs include method, normalized path, status, duration, response size, and trace ID—not bodies or authorization headers.
- The changed-file secret scan completed with no findings.

Supabase's security advisor reported no new RLS or exposed-table failure. The remaining project-level warning is that leaked-password protection is disabled in Auth; enabling it is an account-console setting, not an application migration.

## Visual and interaction verification

The audit used an isolated confirmed QA account, a real CV analysis, a controlled intern job, and rendered browser checks rather than static CSS inspection.

Verified widths: 320, 390, 768, 1024, and 1440 CSS pixels.

Verified states:

- login and first-use onboarding;
- narrow onboarding form and interest taxonomy;
- empty Home and controlled scan input;
- persisted scan progress at a real pipeline checkpoint;
- populated job library and evidence inspector;
- score ring, metrics, status control, reader correction form, evidence, gaps, score components, and resume advice;
- populated Profile summary, fact review, questions, sources, career direction, recommendation consent, and account controls.

The app retains its non-generic aubergine, warm-ivory, mint, coral, violet, and amber identity. Motion uses short entrance/progress transitions and respects `prefers-reduced-motion`.

## External guidance used

- Supabase Queues and PGMQ durability/visibility behavior: https://supabase.com/docs/guides/queues and https://supabase.com/docs/guides/queues/pgmq
- Vercel Cron authentication and Hobby schedule constraints: https://vercel.com/docs/cron-jobs/manage-cron-jobs and https://vercel.com/docs/cron-jobs/usage-and-pricing
- WCAG 2.2 reflow and focus visibility constraints: https://www.w3.org/TR/WCAG22/
- Component-level responsive design: https://web.dev/articles/new-responsive
- Stable layout and layout-shift prevention: https://web.dev/articles/optimize-cls
- Product identity direction is based on the project's earlier 62-design Awwwards and 72-design Dribbble audit in `docs/CAREERFIT_UI_AI_RESEARCH_PLAN.md`, not a copied template.

## Verification record

| Check | Result |
|---|---|
| Backend tests | 118 passed |
| Frontend production build | Passed; 13 routes compiled |
| Responsive horizontal overflow | None at 320/390/768/1024/1440 |
| Supabase v14 migration | Applied |
| Supabase v15 index migration | Applied |
| PGMQ queue | `careerfit_job_scans` present |
| Supabase new-table security advisor | Clean; only existing/project-level informational items remain |
| Changed-file secret scan | No findings |
| Production frontend | READY: https://career-fit-ai-sigma.vercel.app (`dpl_7er64rn2w5ALHUQy4KvtjvN7SQAw`) |
| Production API | READY: https://career-fit-ai-api.vercel.app (`dpl_779BMH9FdY1R6tp3N466D9bhFAeV`) |
| Live authenticated smoke test | Passed: saved job, score, Profile, responsive layout, queue/dedupe round-trip, and account deletion |
| Vercel runtime errors after release | None on frontend or backend |

Release code commit: `43d0f85` (`Implement durable scans and product intelligence`).

The isolated QA account, uploaded file, profile rows, jobs, scan rows, and two queue messages were removed after the production test; database verification returned zero remaining rows/objects/messages for that account.

## Operating notes

- Check `extraction_metrics` aggregates for abrupt changes in zero-skill, zero-project, reader failure, or fallback rates. Do not add raw text to these rows.
- Export evaluation data only into an access-controlled analysis environment and preserve the grouped split.
- Do not enable a calibration artifact merely because it improves training accuracy. Require validation/test calibration improvement and inspect role-family bins.
- Increase worker cadence before promoting background recommendations beyond the small beta.
- Rotate `CRON_SECRET` if it is ever copied outside the backend deployment settings.
