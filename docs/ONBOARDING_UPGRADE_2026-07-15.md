# CareerFit onboarding discovery upgrade

Date: 2026-07-15  
Status: implemented; verification recorded during release

## Outcome

CV work now begins immediately after file selection instead of waiting for the final form action. Candidates can continue adding context while CareerFit reads the document, see truthful stage messages and smoothly interpolated progress, and preselect the strongest extracted skill signals while the authoritative profile build finishes. Analysis now ends on a required review surface: candidates must confirm or skip both the pending facts and one priority clarification before the backend will complete onboarding.

## Before / issue / solution / after

| Before | Issue | Solution | After |
|---|---|---|---|
| CV upload waited for the final submit action. | Users spent form-completion time before extraction even began. | Start secure upload, text reading, local OCR when required, and a CV-only preview immediately on file selection. | CV processing overlaps with optional form work and exposes useful results earlier. |
| Progress changed directly between milestone numbers. | Large percentage jumps made the process feel stalled and then artificial. | Interpolate every target change with `requestAnimationFrame`, calm easing, and a reduced-motion fallback. | The bar and number move continuously while remaining bounded by real pipeline milestones. |
| The scan page only described system work. | Candidates received no useful feedback until the whole pipeline ended. | Show evidence-oriented messages and the top six skill signals, then offer a skippable confirmation surface during final processing. | Waiting time becomes a lightweight trust-building review without blocking completion. |
| Skill confirmation during analysis could race extraction writes. | Applying feedback against preview fact IDs could lose or misapply decisions after final re-analysis. | Treat the early skill choice as preselection, then apply every authoritative fact decision atomically with onboarding completion. | User input stays responsive and stale preview IDs cannot complete onboarding. |
| Final onboarding made separate source, preference, and analysis requests. | Network latency was repeated and an unchanged CV preview was unnecessarily rebuilt. | Add one onboarding analysis endpoint and reuse the ready preview when optional source content is unchanged. Skip unchanged preference writes. | The common CV-only path avoids a second extraction and finalization uses one API round-trip. |
| Early analysis created private data before onboarding completion. | Closing the flow could leave uploaded and extracted preview data indefinitely. | The secured worker deletes unfinished onboarding sources, facts, questions, interests, and review labels after 24 hours, five accounts per invocation. | Early work has a bounded retention period; completed profiles are excluded. |
| Analysis could finish without an explicit evidence review. | Pending facts and open questions could reach the workspace without the candidate making a decision. | Require a `confirmed` or `skipped` fact decision and an `answered`, `skipped`, or verified `no_question` clarification decision in the completion contract. | Both the UI and API block completion until the review is resolved. |
| Confidence was visible only as a number. | Candidates could not understand why a skill or fact was inferred. | Show the source evidence, source-support count, extraction confidence, and an animated confidence rail for every pending fact. | Confidence is inspectable without inventing a hidden model explanation. |
| Career interests had no immediate payoff. | Candidates selected fields without seeing how current evidence connected to them. | Rank up to three selected directions using explicit skill-to-direction mappings and show the supporting skill facts. | Candidates get a transparent, non-predictive direction preview before entering the workspace. |
| Onboarding drop-off was not measurable as a product funnel. | Performance work could not distinguish upload, analysis, review, and completion loss. | Record bounded server-side funnel stages and decision counts in the existing metrics store. | Aggregate analysis can compare stages without storing CV text, answers, fact values, or evidence excerpts. |

## Product and privacy contracts

- Top skills are derived from extracted evidence; the UI does not invent a candidate name or capability.
- Facts may be preselected in the interface, but none are approved until the candidate explicitly confirms the final review. Skipping keeps pending facts pending.
- Confirming the fact review approves selected pending facts and rejects unselected pending facts in the same completion transaction.
- Only one open clarification is required during onboarding; impact order prioritizes experience, location, availability, study timeline, projects, skills, then professional focus. Remaining questions stay available in Profile.
- Career directions are deterministic explanations based on selected interests and extracted skill evidence; they are not job-match scores or employment predictions.
- Funnel events contain enumerated stage names and bounded counts only—never question answers, skill names, fact values, CV text, or evidence excerpts.
- Browser OCR page images stay on the device; only recovered text and compact quality metadata reach the backend.
- Progress interpolation never advances beyond the latest real milestone supplied by the pipeline.
- Cleanup removes private preview content only when `onboarding_completed` is false and the profile has been inactive for at least 24 hours.
- A storage deletion failure preserves the database rows so cleanup can retry safely instead of creating a hidden partial deletion.

## Next measurement pass

The four follow-up experiments are now implemented. `python scripts/onboarding_funnel_report.py --days 30` returns upload-to-review conversion, fact-confirm versus skip counts, question-answer versus skip counts, review-to-completion conversion, and stage drop-off as aggregate values only. Threshold or copy changes should wait for enough beta traffic to avoid tuning from anecdotes.
