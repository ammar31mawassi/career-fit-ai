# Opportunities redesign implementation — 2026-07-17

## Outcome

CareerFit now uses the approved evidence workbench direction: a compact scan workflow, saved-opportunity library, and a larger role inspector with an evidence map as the default view. The same typography, palette, surface treatment, and interaction language carry into login, onboarding, and profile surfaces through shared tokens.

## What changed

- Added Manrope and Newsreader through `next/font` and exposed them as shared CSS variables.
- Reworked the opportunities page into an intro row and two-panel workbench without changing the existing API flow.
- Made the three scan stages permanently legible while retaining real progress state and the description fallback.
- Simplified saved-opportunity rows to role, company/location, signal, score, and fit.
- Added functional Overview, Evidence map, Requirements, and Job details tabs to the inspector.
- Built the evidence map from real component scores, matching evidence, gaps, and resume advice.
- Added responsive rules for desktop, tablet, and mobile, plus reduced-motion handling.
- Added a production-safe design preview fixture for repeatable visual regression review.

## Intentional differences from the concept image

- The concept's fictional company logos were not copied. The product uses an icon-library building mark until real logo data is available.
- “Open job” and stage controls remain visible because they are working product features; they were compacted into the inspector header instead of removed.
- Content density follows actual CareerFit fields, so wording and line lengths vary from the concept while preserving its hierarchy.

## VengenceUI research boundary

VengenceUI informed the compact navigation, restrained glows, clear dark-surface hierarchy, and responsive interaction polish. No VengenceUI code or assets were copied. The reviewed repository did not expose a license file during research, so implementation was intentionally limited to independently written CareerFit components and general design principles.

## Key files

- `frontend/app/globals.css` — tokens, layout, responsive behavior, and motion.
- `frontend/app/layout.tsx` — typography.
- `frontend/components/HomeClient.tsx` — page composition.
- `frontend/components/home/JobScanner.tsx` — scan rail and input.
- `frontend/components/home/JobSummaryCard.tsx` — opportunity rows.
- `frontend/components/home/OpportunityInspector.tsx` — tabs, evidence map, role actions.
- `frontend/components/design/OpportunityPreview.tsx` — realistic local QA fixture.
- `frontend/app/page.tsx` and `frontend/proxy.ts` — guarded preview entry.

## Extension checklist

Before adding a future feature:

1. Choose an existing placement from `CAREERFIT_DESIGN_SYSTEM.md`.
2. Confirm the addition helps the selected role decision or move it below the workbench.
3. Reuse tokens and Lucide icons; do not introduce isolated colors, shadows, or radii.
4. Include loading, empty, error, keyboard, reduced-motion, and mobile states.
5. Update the realistic preview fixture if the primary workbench composition changes.
6. Capture the approved image and implementation at the same state and viewport, compare them together, and record the result in `design-qa.md`.

## Validation record

The implementation was checked at desktop (1536×1024), tablet (1024×900), and mobile (390×844) layout sizes. Inspector tabs, saved-role filtering, selection, responsive collapse, semantic roles, overflow, and browser console output were tested. Type checking and the production build are required release gates and are recorded in `design-qa.md` after completion.
