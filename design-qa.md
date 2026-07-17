# Design QA — CareerFit readability and evidence remediation

Date: 2026-07-17

## Sources and test state

- Defect evidence: `C:\Users\ammar\AppData\Local\Temp\codex-clipboard-f7c0a932-f600-47a1-8031-a86a77624e5a.png`
- Defect evidence: `C:\Users\ammar\AppData\Local\Temp\codex-clipboard-c29cbfd3-dee1-4bf4-8893-3ef4e753fe51.png`
- Local implementation: `http://127.0.0.1:3001/` with `NEXT_PUBLIC_DESIGN_PREVIEW=1`
- Stress fixture: Application Engineering Student, 39% Weak fit, long location/work-mode metadata, mixed component coverage, and a missing must-have skill.
- Desktop final: `C:\Users\ammar\.codex\visualizations\2026\07\17\019f7073-5050-7672-b7db-a9e074972bf9\careerfit-fix-final-desktop.png`
- Mobile final: `C:\Users\ammar\.codex\visualizations\2026\07\17\019f7073-5050-7672-b7db-a9e074972bf9\careerfit-fix-mobile-inspector-final.png`
- Interactive evidence state: `C:\Users\ammar\.codex\visualizations\2026\07\17\019f7073-5050-7672-b7db-a9e074972bf9\careerfit-fix-mobile-evidence.png`
- Before/after comparison: `C:\Users\ammar\.codex\visualizations\2026\07\17\019f7073-5050-7672-b7db-a9e074972bf9\careerfit-fix-before-after.png`
- Focused scanner comparison: `C:\Users\ammar\.codex\visualizations\2026\07\17\019f7073-5050-7672-b7db-a9e074972bf9\careerfit-fix-scan-card.png`
- Focused score comparison: `C:\Users\ammar\.codex\visualizations\2026\07\17\019f7073-5050-7672-b7db-a9e074972bf9\careerfit-fix-inspector-header.png`

## Findings and resolution

| Priority | Finding | Resolution |
| --- | --- | --- |
| P1 | The weak-fit score orb clipped the percentage and collided with header actions. | Replaced it with a contained score summary and moved score/actions into the inspector grid flow. |
| P1 | Essential evidence, navigation, and secondary copy used 8.5–10.5px text. | Raised essential supporting text to a readable 12px or greater and increased headings, tabs, and controls proportionally. |
| P1 | The orbit was decorative, static, and did not explain the result. | Converted every point into a keyboard-accessible button with hover, focus, and click selection plus a live evidence explainer. |
| P1 | Low component scores were incorrectly labeled “Strong.” | Added honest Strong, Supported, Partial, and Limited bands tied to explicit thresholds. |
| P1 | The scan connector line passed through step labels. | Stacked markers above labels and constrained the line to the marker row. |
| P2 | A gap node and “one gap” message appeared even without a returned gap. | The critical node now renders only for real blockers/gaps; otherwise the UI reports no critical gaps. |
| P2 | Saved-row score and fit could overlap in narrow columns. | Made the summary side a stable vertical grid and removed conflicting inherited pill geometry. |
| P2 | Mobile tabs displayed a native scrollbar that looked like a broken divider. | Kept horizontal swipe behavior while hiding the platform scrollbar and preserving visible focus. |

## Comparison history

### Pass 1

- Score and action geometry were repaired.
- Evidence nodes became controls and the adjacent panel exposed the reason, profile evidence, and role evidence.
- The 39% stress fixture exposed misleading component labels and narrow-column reflow issues.

### Pass 2

- Component bands were corrected, the inspector adopted container-aware evidence layout, and long metadata/role titles were verified.
- Scanner labels moved below the connector rail.

### Final pass

- Desktop, 390×844 mobile, and a 612px reflow proxy had no page-level horizontal overflow.
- Selecting “Must Have Skills” showed its 20% Limited state and the available role/profile facts.
- Selecting “Critical blocker” explained the must-have score cap without inventing profile evidence.
- A no-gap fixture rendered no gap node and showed “No critical gaps detected.”
- Overview, Requirements, and Job details tabs remained functional.

## Functional, accessibility, and release checks

- [x] Orbit points respond to hover, keyboard focus, and click/tap.
- [x] Active evidence controls expose `aria-pressed` and reference the explainer with `aria-controls`.
- [x] Evidence wording distinguishes verified profile facts from role requirements and explicitly reports missing component evidence.
- [x] Native button semantics, global visible focus, and reduced-motion behavior are preserved.
- [x] Mobile tabs remain operable by swipe and keyboard without the decorative scrollbar.
- [x] Browser console warnings/errors: none during the tested flow.
- [x] Frontend typecheck (`npm run typecheck`).
- [x] Frontend production build (`npm run build`).
- [x] Production deployment and post-deploy smoke test (`https://career-fit-ai-sigma.vercel.app`).

Production smoke result: HTTP/DOM loaded at the stable alias, the selected live role rendered a fully contained `29% Weak fit / 81% confidence` summary, seven evidence controls were present, selecting a 12% Limited component updated the explainer and `aria-pressed`, page-level horizontal overflow was absent, and browser logs were empty.

Final status: passed.
