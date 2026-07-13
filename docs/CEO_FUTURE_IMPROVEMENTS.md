# CareerFit future product and engineering proposals

Date: 2026-07-13

These are deliberately not hidden inside the current QA patch. Each proposal has a product trigger so the company does not add infrastructure before it earns its complexity.

## Next: highest leverage

| Proposal | Why it matters | Start when | Suggested implementation |
|---|---|---|---|
| Durable background job scans | Closing a tab or exceeding a serverless timeout should not lose a job scan. It also enables truthful progress and cancellation. | Scan p95 exceeds 12 seconds or scan volume exceeds roughly 100/day. | Persist a scan job with queued/running/succeeded/failed/cancel-requested states. Process it through Supabase Queues or a small worker. Poll initially; add server-sent events only if polling feels insufficient. |
| Extraction observability | Parser regressions are currently found by people rather than dashboards. | Before expanding the beta. | Record reader strategy, duration, text length, fallback reasons, fact counts, requirement counts, and structured error codes. Alert on abrupt zero-project/zero-skill rates without logging raw CV text. |
| Correction-driven evaluation set | User confirm/reject actions are the most valuable proprietary dataset. | Immediately collect; model only after enough labels. | Export anonymized feature/label snapshots, keep train/test splits by user, and run offline extraction and calibration reports on every model version. |
| Job requirement correction UI | A wrong “2+ years” interpretation can dominate the entire score. | After profile review metrics are stable. | Show extracted must-haves, years, seniority, and work mode in a compact review drawer. Let users correct them and store the original plus reviewed value. |
| Pagination and conditional fetching | Large job libraries will make bootstrap and exports increasingly expensive. | A typical user approaches 50–100 saved jobs. | Cursor-paginate job summaries; use ETags or `updated_at` watermarks; load details only when a card opens. |
| Error monitoring and trace IDs | Public users need supportable failures. | Before public traffic is actively promoted. | Add privacy-safe exception monitoring, request/trace IDs, endpoint latency histograms, and a support-friendly error code shown in UI. Never send CV contents to telemetry. |

## Later: differentiated product value

| Proposal | Why it matters | Trigger / constraint |
|---|---|---|
| Candidate-to-job recommendations | Reuse a scanned job across relevant candidates, reducing discovery work and increasing network value. | Categorize each job into role families and locations, shortlist candidates by interests/domain/logistics, then score only the shortlist asynchronously. Require opt-in and never expose another candidate’s data. Start with daily batches, not all-pairs matching. |
| Opt-in matching notifications | Strong recommendations are only useful if users see them. | Add only after recommendation precision is measured. Email at a low frequency with unsubscribe controls and a minimum calibrated threshold. |
| Browser extension fallback | Some career sites block server-side readers but render correctly in the user’s browser. | Build after reader telemetry identifies a meaningful blocked-site share. Capture user-authorized page text and URL, show the exact payload before upload, and request the narrowest browser permissions. |
| Semantic fact reconciliation | Rule-based normalization cannot merge every paraphrase safely. | Use only when a reviewed duplicate dataset exists. A small embedding model can propose merges; confidence gates and user approval protect against false merges. |
| OCR quality routing | One OCR engine will not dominate every scanned CV. | Benchmark against anonymized scanned fixtures. Route by document quality/language and keep browser OCR as the private, free fallback. |
| Outcome-aware score calibration | “Match” should become better calibrated using real application results while remaining explainable. | Do not train until there are enough consented outcomes across role families. Use a small monotonic model over existing features, evaluate fairness and calibration, and retain deterministic hard blockers. |
| Resume draft workspace | Current advice tells users what to add but does not produce an editable, verified draft. | Add after advice quality is trusted. Generate only from approved facts, cite source facts internally, and never invent achievements. |

## Model strategy

Fine-tuning a large language model is not the next step. CareerFit first needs trustworthy labels and reproducible evaluation. The replaceable scorer boundary should remain, but the likely first learned component is a small calibrated classifier or ranking model over structured features such as requirement priority, evidence tier, transfer strength, experience gap, education, logistics, and domain alignment.

LLMs or small local language models can later assist with:

- proposing canonical fact merges;
- classifying ambiguous requirement sentences;
- producing resume wording constrained to approved facts;
- drafting opt-in notifications.

They should not directly invent the percentage. Eligibility caps, evidence citations, model versioning, and a deterministic fallback remain essential.

## Recommendation engine design

Do not run every new job against every candidate. Use a two-stage pipeline:

1. **Cheap eligibility shortlist:** role family/interests, location/work mode, availability, career stage, and a coarse skill-domain index.
2. **Full evidence score:** run the existing matcher for only the eligible shortlist and save recommendations above a calibrated threshold.

This keeps cost close to the number of relevant candidates rather than total candidates. Add per-user recommendation consent, suppress already rejected/applied jobs, expire old postings, and expose why a job was recommended.

## Security and privacy maturity

- Publish a formal retention schedule and automate cleanup of abandoned uploads and expired job snapshots.
- Add service-key rotation and recovery procedures.
- Add a security response address and incident runbook.
- Consider a regional data strategy if the user base expands beyond the current geography.
- Perform a dependency and authorization audit before adding third-party email, analytics, or browser-extension services.
