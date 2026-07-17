# Design QA — CareerFit evidence workbench

Date: 2026-07-17

## Sources

- Approved reference: `docs/ui/careerfit-workbench-approved.png`
- Live implementation: `http://127.0.0.1:3001/` with `NEXT_PUBLIC_DESIGN_PREVIEW=1`
- Primary comparison state: 1536×1024, Northstar Labs selected, Evidence map tab selected.
- Final implementation capture: `C:\Users\ammar\.codex\visualizations\2026\07\17\019f7073-5050-7672-b7db-a9e074972bf9\careerfit-workbench-pass3.png`
- Combined final comparison: `C:\Users\ammar\.codex\visualizations\2026\07\17\019f7073-5050-7672-b7db-a9e074972bf9\careerfit-qa-comparison-pass3.png`

## Comparison history

### Pass 1

- P2: the intro was too tall and the hero wrapped earlier than the reference.
- P2: scanner fallback and inspector utilities consumed too much vertical space.
- Fix: widened the hero column, constrained the heading, tightened scanner spacing, and moved compact utilities out of the primary content flow.

### Pass 2

- P2: the workbench still began lower than the approved composition.
- Fix: reduced scanner padding and gaps while retaining the readable three-step rail.

### Pass 3

- Result: composition, hierarchy, palette, density, evidence map, and primary action closely match the approved direction.
- Accepted P3 differences: real product utilities remain visible; icon-library company marks replace fictional concept logos; live data creates slightly different line lengths.

## Functional and responsive checks

- [x] Overview tab selects and exposes metrics, evidence, gaps, and advice.
- [x] Evidence map tab is the default and restores on role change.
- [x] Requirements tab exposes correction controls and extracted requirements.
- [x] Job details tab exposes agent workflow, score components, and history.
- [x] Saved-opportunity search filters roles and restores the full list.
- [x] Selecting a role updates the active row, role heading, score, and fit.
- [x] Mobile 390×844 has no horizontal overflow; workbench, map, evidence, and resume action stack cleanly.
- [x] Tablet 1024×900 has no horizontal overflow and preserves the intended breakpoint behavior.
- [x] Login desktop and mobile use the same typography, palette, and surface system.
- [x] Semantic banner, navigation, headings, form labels, tabs, tab panels, complementary inspector, and evidence regions are present.
- [x] Global visible-focus and reduced-motion rules remain in place.
- [x] Browser console warnings/errors: none during the tested flow.

## Release gates

- [x] Frontend typecheck (`npm run typecheck`)
- [x] Frontend production build (`npm run build`)
- [x] Commit contains only the intended frontend and documentation files
- [x] Production deployment returns successfully (`https://career-fit-ai-sigma.vercel.app`)
- [x] Deployed URL smoke-tested: HTTP 200, production DOM complete, no horizontal overflow, and no browser warnings/errors.

Final status: passed.
