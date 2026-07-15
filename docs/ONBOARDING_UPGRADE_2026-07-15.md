# CareerFit onboarding discovery upgrade

Date: 2026-07-15  
Status: implemented; verification recorded during release

## Outcome

CV work now begins immediately after file selection instead of waiting for the final form action. Candidates can continue adding context while CareerFit reads the document, see truthful stage messages and smoothly interpolated progress, and optionally confirm the strongest extracted skill signals while the authoritative profile build finishes.

## Before / issue / solution / after

| Before | Issue | Solution | After |
|---|---|---|---|
| CV upload waited for the final submit action. | Users spent form-completion time before extraction even began. | Start secure upload, text reading, local OCR when required, and a CV-only preview immediately on file selection. | CV processing overlaps with optional form work and exposes useful results earlier. |
| Progress changed directly between milestone numbers. | Large percentage jumps made the process feel stalled and then artificial. | Interpolate every target change with `requestAnimationFrame`, calm easing, and a reduced-motion fallback. | The bar and number move continuously while remaining bounded by real pipeline milestones. |
| The scan page only described system work. | Candidates received no useful feedback until the whole pipeline ended. | Show evidence-oriented messages and the top six skill signals, then offer a skippable confirmation surface during final processing. | Waiting time becomes a lightweight trust-building review without blocking completion. |
| Skill confirmation during analysis could race extraction writes. | Applying feedback against preview fact IDs could lose or misapply decisions after final re-analysis. | Store selected skill values locally, map them to authoritative final fact IDs, then submit one bulk confirmation request. | User input stays responsive and is applied only to the final evidence set. |
| Final onboarding made separate source, preference, and analysis requests. | Network latency was repeated and an unchanged CV preview was unnecessarily rebuilt. | Add one onboarding analysis endpoint and reuse the ready preview when optional source content is unchanged. Skip unchanged preference writes. | The common CV-only path avoids a second extraction and finalization uses one API round-trip. |
| Early analysis created private data before onboarding completion. | Closing the flow could leave uploaded and extracted preview data indefinitely. | The secured worker deletes unfinished onboarding sources, facts, questions, interests, and review labels after 24 hours, five accounts per invocation. | Early work has a bounded retention period; completed profiles are excluded. |

## Product and privacy contracts

- Top skills are derived from extracted evidence; the UI does not invent a candidate name or capability.
- No skill is approved by default. “Looks right” is an explicit action and “Skip for now” remains available.
- Browser OCR page images stay on the device; only recovered text and compact quality metadata reach the backend.
- Progress interpolation never advances beyond the latest real milestone supplied by the pipeline.
- Cleanup removes private preview content only when `onboarding_completed` is false and the profile has been inactive for at least 24 hours.
- A storage deletion failure preserves the database rows so cleanup can retry safely instead of creating a hidden partial deletion.

## Recommended next onboarding experiments

1. Ask one high-value clarification question during remaining processing, using the same deferred-apply pattern as skill confirmation.
2. Show confidence decomposition—document readability, evidence coverage, and optional-source coverage—behind one expandable “How sure are we?” control.
3. Offer a role-direction preview after interests are selected: “Your evidence currently aligns most with…” without producing or changing a job-match percentage.
4. Measure time-to-first-signal, skill-confirmation rate, skip rate, final completion rate, and preview cleanup count using aggregate events that contain no skill names or document text.
