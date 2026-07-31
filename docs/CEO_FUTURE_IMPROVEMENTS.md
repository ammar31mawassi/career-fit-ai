# CareerFit CEO roadmap

Updated: 2026-07-13
Status: historical roadmap snapshot. Current operational requirements and
unresolved gates are maintained in `OPERATIONS_RUNBOOK.md`,
`DATA_RETENTION_INVENTORY.md`, and `RELEASE_AND_ROLLBACK.md`.

The CEO approved the original next-step, model, and recommendation strategy. The first block is now implemented. The remaining roadmap is ordered by evidence and product trigger so CareerFit does not add infrastructure or model complexity before it is useful.

## Implemented in the July 13 product intelligence release

| Approved proposal | Status | Delivered capability |
|---|---|---|
| Durable background job scans | Implemented | Persisted scan rows, Supabase PGMQ, real checkpoints, polling, cancellation, stale-lease recovery, three-attempt limit, and a secured recovery worker. |
| Extraction observability | Implemented | Privacy-safe strategy, latency, length, fallback, count, version, trace, error, and onboarding-funnel metrics without raw document/job text, answers, fact values, or evidence excerpts. |
| Correction-driven evaluation set | Implemented | Fact and requirement-review labels, stable person-grouped train/validation/test splits, and a redacted JSONL exporter. |
| Job requirement correction UI | Implemented | User-editable priority skills, experience, seniority, education, work mode, location, and domain with original/corrected history and immediate rematch. |
| Pagination and conditional fetching | Implemented | Cursor-paginated job summaries, first-page bootstrap cursor/watermark, ETags, lazy details, and Load more. |
| Error monitoring and trace IDs | Implemented foundation | Trace IDs, support codes, Server-Timing, privacy-safe structured logs, stable error codes, and extraction metrics. A hosted dashboard/alert sink is intentionally still pending. |
| Two-stage candidate-to-job recommendations | Implemented beta | Explicit consent, career-field shortlist, cheap experience/seniority/logistics checks, full scorer only for eligible candidates, and save/dismiss UI. |
| Replaceable calibrated model boundary | Implemented foundation | Deterministic scorer plus optional monotonic calibration artifact, safe fallback, offline Brier/ECE report, and blocker/cap protection. No learned artifact is enabled yet. |

Full technical record: `docs/SENIOR_FULLSTACK_RELEASE_2026-07-13.md`.

## Next: measure and harden

| Proposal | Why it is next | Start/ship gate | Suggested implementation |
|---|---|---|---|
| Extraction quality dashboard and alerts | Metrics now exist but regressions still need a visible operating surface. | Start now; keep beta-scale and low-cost. | Daily aggregates by reader strategy/version and role family. Alert on failure rate and abrupt zero-skill/zero-project changes. Never copy raw text into analytics. |
| Label coverage report | A model should not be trained on whichever users happen to review first. | Foundation implemented; expand as review data accumulates. | `label_coverage_report.py` now reports split, label type, fact/evidence segment, corrected field, and model-version coverage and blocks sparse train/validation/test gates. Add role family, career stage, source type, and outcomes when those dimensions are present in privacy-safe labels. |
| Increase queue recovery cadence | Daily Hobby recovery is safe but not a strong SLA for an abandoned scan. | When abandoned scans occur or volume exceeds roughly 100 scans/day. | Upgrade the cron cadence or invoke the same secured worker from dedicated compute. Do not redesign the queue contract. |
| Recommendation precision evaluation | Visible recommendations should earn user trust before notifications amplify mistakes. | At least 100 opt-in recommendation impressions across relevant role families. | Track privacy-safe save, dismiss, open-site, and later application outcomes. Tune threshold by validation data, not anecdote. |
| Security operations runbook | Public beta now has queues, consent, and internal evaluation rows. | Before a larger public launch. | Document key rotation, incident response, deletion verification, backup/recovery, contact channel, and periodic Supabase/Vercel advisor review. Enable Supabase leaked-password protection. |
| Automated retention cleanup | Failed scans, expired shared jobs, and old telemetry should not remain forever. | Onboarding-preview cleanup implemented; define remaining product/legal retention periods. | The worker now deletes unfinished onboarding sources, extracted facts, questions, interests, and review labels after 24 hours in bounded batches. Terminal scans, inactive catalog entries, and old metrics still require explicit retention periods. |

## Model strategy

Fine-tuning a large language model is still not the next step. CareerFit now collects trustworthy labels and has a replaceable scorer boundary. The first learned production component should be a small calibrated model over structured features such as:

- requirement priority and evidence tier;
- transfer strength and direct project evidence;
- experience gap and career stage;
- education and semester constraints;
- work-mode, location, availability, and authorization compatibility;
- domain/responsibility alignment;
- extraction and evidence confidence.

### Training gate

Do not enable a learned artifact until all of these are true:

1. User-grouped validation and test sets have adequate coverage.
2. Calibration improves out-of-sample Brier score and expected calibration error.
3. Important role-family and career-stage slices do not regress materially.
4. The artifact is monotonic where product logic expects it.
5. Deterministic eligibility caps and missing blockers remain authoritative.
6. The deterministic scorer remains a tested runtime fallback.

LLMs or small local language models may later propose canonical fact merges, classify ambiguous requirement sentences, or draft resume wording constrained to approved facts. They should not directly invent the match percentage.

## Recommendation strategy

The implemented pipeline deliberately avoids all-pairs scoring:

1. Shared jobs are categorized into career fields and logistics.
2. Only opted-in profiles in relevant interests are shortlisted.
3. Cheap seniority, experience, availability, and location checks remove obvious mismatches.
4. The full evidence scorer runs only on the remaining candidates.
5. Only strong, blocker-free matches become visible; weaker rows remain evaluation observations.

Next improvements after precision is measured:

- suppress expired, rejected, dismissed, already-saved, or already-applied postings;
- rank by calibrated relevance, freshness, and user direction;
- diversify near-duplicate roles from the same company;
- add low-frequency opt-in email notifications with unsubscribe controls;
- explain each recommendation using the same evidence contract as a normal match.

## Later differentiated value

| Proposal | Product value | Trigger/constraint |
|---|---|---|
| Semantic fact reconciliation | Propose safe merges for paraphrased duplicate facts. | Use a reviewed duplicate/non-duplicate dataset. A small embedding model proposes; confidence gates and user approval decide. |
| OCR quality routing | Improve scanned CV recovery across languages and document quality. | Benchmark multiple engines on anonymized fixtures; retain browser OCR as the free, private fallback. |
| Browser extension fallback | Capture text from career pages that block server readers. | Build only after telemetry shows a meaningful blocked-site share. Use narrow permissions and show the exact payload before upload. |
| Outcome-aware calibration | Align score meaning with consented application results. | Sufficient outcomes across role families; fairness/calibration review; deterministic caps retained. |
| Resume draft workspace | Convert trusted advice into an editable, role-specific CV draft. | Advice quality is trusted. Generate only from approved facts and preserve internal citations. |
| Opt-in matching notifications | Bring strong fresh matches back to the user. | Recommendation precision and unsubscribe behavior are measured first. |

## CEO decisions needed later

- Retention periods for failed scans, extracted metrics, evaluation examples, and inactive shared jobs.
- The traffic/latency threshold that justifies more frequent worker compute.
- The minimum data coverage and calibration improvement required to enable the first learned artifact.
- Whether recommendation notifications remain email-only or later include mobile/push channels.
- Whether the first resume workspace exports DOCX, PDF, or both.
