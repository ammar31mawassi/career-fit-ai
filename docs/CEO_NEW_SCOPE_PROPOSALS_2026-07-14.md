# CareerFit new-scope proposals

Date: 2026-07-14  
Status: discovery only; no expansion is approved by this document

## Decision summary

The strongest near-term differentiation is not “more AI.” It is making evidence, uncertainty, and improvement pathways more legible while safely learning from shared job data. The best five are: evidence-bound resume verification, confidence decomposition, requirement commonness, recurring-gap plans, and correction-derived parser quality. These rank highest on candidate trust, reuse of existing structured data, and low conflict with CareerFit's privacy model.

| Rank | Idea | Impact | Confidence | Effort | Risk | Recommendation |
|---|---|---:|---:|---:|---:|---|
| 1 | Evidence-bound resume claim checker | 5 | 5 | 2 | 2 | Now |
| 2 | Confidence decomposition and “what would change this” | 5 | 4 | 2 | 2 | Now |
| 3 | Requirement commonness by role family and region | 5 | 4 | 3 | 3 | Next experiment |
| 4 | Recurring-gap learning and portfolio plan | 4 | 4 | 3 | 2 | Next experiment |
| 5 | Safe correction-derived parser quality | 4 | 4 | 3 | 2 | Next |

## Proposals

### 1. Evidence-bound resume claim checker — now

- User problem: tailored resume advice can accidentally become a stronger claim than the candidate's approved evidence supports.
- Experience: every suggested bullet shows its supporting facts; unsupported, contradictory, or overly broad wording is blocked before copy/export.
- Required data: approved facts, evidence tier, source count, suggested text, and a structured claim-to-fact mapping.
- Privacy/security: process inside the candidate boundary; never send raw evidence to telemetry or shared datasets.
- Complexity: medium-low; deterministic entity/number/skill checks cover the first useful version.
- Runtime/cost: low and synchronous; cache by profile version plus draft hash.
- Validation: run the checker against existing advice and a red-team fixture set with invented metrics, employers, dates, and skills.
- Success metric: unsupported-claim escape rate below 1%; fewer user edits caused by factual overreach.
- Main failure mode: rejecting legitimate paraphrases and making drafts bland.

### 2. Confidence decomposition and counterfactuals — now

- User problem: one confidence number does not explain whether uncertainty comes from document extraction, missing evidence, or ambiguous job language.
- Experience: disclose three compact contributors—profile evidence, job capture, and requirement interpretation—and one actionable “the score could change if…” statement.
- Required data: existing extraction confidence, evidence coverage, reader confidence, blockers, and score components.
- Privacy/security: derived values only; keep evidence excerpts private and user-owned.
- Complexity: low; no new model is required.
- Runtime/cost: negligible and synchronous.
- Validation: A/B test the decomposed card against the current single metric after users correct a fact or requirement.
- Success metric: higher correct understanding of score limits and fewer corrections motivated by misunderstanding.
- Main failure mode: adding too much explanation to already-long pages; use progressive disclosure.

### 3. Requirement commonness by role family and region — next experiment

- User problem: candidates cannot tell whether a blocker is industry-standard or peculiar to one posting.
- Experience: label requirements as common, emerging, or unusual for a selected role family/region and show sample size/freshness.
- Required data: deduplicated shared jobs, canonical requirements, role family, region, posting dates, and expiry state.
- Privacy/security: job-only aggregates; enforce minimum cohort sizes and never join candidate profiles.
- Complexity: medium; taxonomy normalization, dedupe, expiry, and time-windowed aggregates are needed.
- Runtime/cost: batch/precompute daily; cheap reads.
- Validation: launch for one well-covered role family and compare user decisions with/without the benchmark.
- Success metric: benchmark usefulness rating, repeat visits, and gap-plan starts; monitor misleading low-sample labels.
- Main failure mode: biased or stale catalog coverage presented as market truth.

### 4. Recurring-gap learning and portfolio plan — next experiment

- User problem: isolated job gaps do not tell candidates which improvement will unlock the most roles.
- Experience: aggregate gaps across saved jobs, rank by role coverage, and propose evidence-producing learning or portfolio steps with a user-selected time budget.
- Required data: private saved-job gaps, interests, approved facts, job freshness, and optionally user completion state.
- Privacy/security: candidate-only computation; external learning links must not receive profile context.
- Complexity: medium; needs gap canonicalization and benefit estimation, not generative prose.
- Runtime/cost: recompute asynchronously after job/profile changes; cache the plan.
- Validation: offer a two-week plan to users with at least five jobs and measure accepted/completed steps.
- Success metric: completed steps that produce newly approved evidence and increase coverage across fresh jobs.
- Main failure mode: optimizing for keyword accumulation rather than credible capability.

### 5. Safe correction-derived parser quality — next

- User problem: many users can correct the same extraction pattern, but the improvement currently remains only an evaluation label.
- Experience: aggregate redacted error signatures by reader version and field, promote only reviewed deterministic rules/fixtures, and show operators the highest-impact regressions.
- Required data: structured original/corrected fields, parser version, source strategy, and coarse role/language segments.
- Privacy/security: no descriptions, URLs, evidence, or stable user identifiers; minimum aggregation thresholds.
- Complexity: medium; signature generation, fixture review workflow, and release comparison.
- Runtime/cost: daily batch plus lightweight dashboard.
- Validation: manually review the top 20 signatures and implement only those reproducible with sanitized fixtures.
- Success metric: lower correction rate on later reader versions without segment regressions.
- Main failure mode: recommendation poisoning or overfitting to coordinated corrections.

### 6. Career evidence timeline — later

- User problem: candidates cannot see whether their profile is becoming more credible over time.
- Experience: private snapshots show new approved evidence, recurring gaps closed, and coverage change without implying hiring probability.
- Required data: versioned fact changes and aggregate match components; avoid retaining raw documents beyond policy.
- Privacy/security: exportable/deletable user-owned history with a clear retention control.
- Complexity: medium-high because snapshots and correction semantics must be defined.
- Runtime/cost: event-driven snapshots, cheap reads.
- Validation: prototype a monthly summary with users actively applying.
- Success metric: return rate and verified evidence additions, not score-chasing.
- Main failure mode: anxiety or gaming caused by turning career progress into a vanity score.

### 7. Privacy-safe shareable match report — later

- User problem: candidates want feedback from mentors without sharing their CV or account.
- Experience: expiring, revocable report containing user-selected score components and gaps, with evidence hidden by default.
- Required data: a frozen report snapshot, disclosure choices, expiry, and revocation token.
- Privacy/security: high sensitivity; unguessable tokens, no indexing, short expiry, access log, and explicit preview.
- Complexity: medium-high.
- Runtime/cost: low storage/read cost; abuse controls required.
- Validation: clickable prototype with career coaches before storing share tokens.
- Success metric: useful mentor feedback per share and rapid revocation success.
- Main failure mode: links forwarded to employers or search engines.

### 8. Language-fair evidence normalization — next experiment

- User problem: non-native English, Arabic, or Hebrew resumes may use phrasing that deterministic English extraction undervalues.
- Experience: detect likely extraction uncertainty, offer language-aware review, and compare equivalent evidence fixtures across languages.
- Required data: consented/synthetic multilingual fixtures, language tag, extraction result, and human-reviewed equivalence labels.
- Privacy/security: avoid third-party translation of private CVs by default; browser/local processing is preferable.
- Complexity: high because RTL UI, tokenization, and benchmark quality all matter.
- Runtime/cost: benchmark first; production routing only after measured benefit.
- Validation: parallel sanitized fixture suite in English, Arabic, and Hebrew.
- Success metric: parity in fact recall and evidence-tier assignment across equivalent resumes.
- Main failure mode: translation changing the strength or meaning of claims.

### 9. Job freshness and duplicate lineage — next

- User problem: duplicates and expired roles waste attention and poison market/recommendation statistics.
- Experience: merge canonical listings, retain source lineage, show “updated/likely expired,” and suppress stale recommendations.
- Required data: normalized company/role/location, canonical URL/content hashes, first/last seen, source state, and expiry signals.
- Privacy/security: job-only; URL fetching remains SSRF-protected and rate-limited.
- Complexity: medium.
- Runtime/cost: asynchronous refresh with domain budgets and deduplicated fetches.
- Validation: sample 200 catalog jobs and measure precision of duplicate/expiry decisions.
- Success metric: lower duplicate recommendation rate and expired-link opens.
- Main failure mode: merging genuinely different requisitions or marking live roles expired.

### 10. Adversarial document and URL quarantine — next

- User problem: public uploads and URLs can contain prompt-like text, decompression bombs, malicious redirects, or parser abuse.
- Experience: risky inputs fail fast with a safe explanation; suspicious content is isolated from downstream optional AI components.
- Required data: byte/page/redirect limits, MIME signatures, parse timings, and coarse security reason codes.
- Privacy/security: strengthens boundaries; never log content or attacker-controlled URLs verbatim.
- Complexity: medium; existing SSRF and size controls are a foundation.
- Runtime/cost: small synchronous checks, bounded isolated parsing for expensive files.
- Validation: security fixture suite for oversized PDFs, redirect chains, private IPs, malformed objects, and instruction injection.
- Success metric: zero boundary escapes and bounded worst-case CPU/memory.
- Main failure mode: false positives blocking unusual but valid CVs or job boards.

### 11. Workflow simplification mode — now experiment

- User problem: users perform extensive fact review before they understand which decisions affect a match.
- Experience: default to “review high-impact facts,” defer low-impact metadata, and reveal deeper controls only when relevant.
- Required data: existing fact impact ordering, pending status, and anonymous interaction counts only.
- Privacy/security: no additional private data required.
- Complexity: low frontend change after usability validation.
- Runtime/cost: none.
- Validation: moderated mobile test comparing completion time and missed high-impact errors.
- Success metric: faster first trustworthy match with no increase in later corrections.
- Main failure mode: hidden low-impact facts later become high-impact for a different role.

### 12. Institution/coaching workspace — assess later, do not build

- User problem: universities and coaches need cohort support, but recruiter-style oversight could conflict with candidate trust.
- Experience: candidate-controlled invitations to view selected plans/reports; no default institutional access and no raw CV export.
- Required data: organization membership, explicit grants, scoped report snapshots, coach actions, and audit logs.
- Privacy/security: very high; consent revocation, separation of duties, data-processing agreements, and conflict-of-interest policy are prerequisites.
- Complexity: very high multi-tenant authorization and commercial operations.
- Runtime/cost: moderate infrastructure plus substantial support/compliance cost.
- Validation: interview 10 candidates and 5 career-service teams using a non-functional prototype.
- Success metric: candidate willingness to grant access and measurable coaching throughput without lower trust.
- Main failure mode: surveillance dynamics or pressure to expose private candidate data; reject recruiter resale of candidate profiles.

## Portfolio recommendation

- Quick wins: 1, 2, and the usability experiment in 11.
- Experiments: 3, 4, 8, and 12.
- Platform investments: 5, 9, and 10.
- Major bets: 6 and 7 only after trust and retention policies are explicit.
- Rejected direction: selling or exposing identifiable candidate profiles to recruiters; it conflicts with the product's candidate-first trust position.
