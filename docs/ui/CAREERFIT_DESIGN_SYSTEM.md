# CareerFit workbench design system

Status: approved and implemented on 2026-07-17.

The visual reference for this direction is [careerfit-workbench-approved.png](careerfit-workbench-approved.png). Treat it as the composition target for the opportunities experience. The interface should stay calm, direct, evidence-led, and dense enough to support real work without turning into a generic analytics dashboard.

## Product principles

1. **Clarity first.** Lead with the role, fit, evidence, gap, and next action. Decoration must never compete with those five things.
2. **Progressive disclosure.** Keep the evidence map as the default explanation, then place deeper material in the existing Overview, Requirements, and Job details tabs.
3. **Evidence before claims.** Scores are always paired with confidence, matching evidence, or an explicit gap.
4. **One primary action per region.** The scan card analyzes a role; the inspector improves the application. Secondary controls stay quiet.
5. **Calm motion.** Motion confirms state and hierarchy. It should not create a spectacle around routine work.

## Visual language

The source of truth is `frontend/app/globals.css`.

| Role | Token | Value |
| --- | --- | --- |
| Canvas | `--bg` | `#070b0d` |
| Raised canvas | `--bg-elevated` | `#0b1012` |
| Surface | `--surface` | `#0d1315` |
| Main text | `--text` | `#f7f2e8` |
| Muted text | `--muted` | `#939da0` |
| Positive / primary | `--primary` | `#83efbd` |
| Gap / warning emphasis | `--coral` | `#ff7a59` |
| Medium fit | `--amber` | `#f4c95d` |
| Resume action | `--violet` | `#9d7bff` |

Manrope is the interface face. Newsreader is reserved for the editorial second line in important headings. Do not expand the serif face into labels, navigation, controls, or data.

Corner radii are deliberately compact: 9px for controls, 13–16px for work surfaces, and 24px only for genuinely large containers. Borders carry more hierarchy than shadows. Gradients should remain low-contrast ambient light, never become a feature by themselves.

## Spatial model

- The header is a compact global layer for product identity, primary navigation, privacy state, and account actions.
- The intro row pairs a concise outcome-oriented hero with the scan workflow.
- The workbench is a narrow saved-opportunity library beside a larger inspector.
- The inspector follows this order: role identity, confidence, compact utilities, tabs, evidence, and one application action.
- Secondary statistics and recommendations remain below the workbench so they do not interrupt the main decision.

Responsive behavior:

- Above 1180px, the hero and scanner share a row and the opportunity library stays beside the inspector.
- From 981–1180px, the hero and scanner stack while the workbench remains two-column where space allows.
- At 980px and below, the workbench becomes one column.
- At 680px and below, scan controls, evidence sections, inspector actions, and resume actions stack. Tabs remain horizontally scrollable instead of wrapping into an unreadable block.

## Motion

Use the existing motion tokens:

- `--fast: 150ms` for hover, focus, and small control feedback.
- `--motion: 240ms` for tabs and ordinary state changes.
- `--slow: 460ms` for progress and evidence-map entry.
- `--ease-smooth: cubic-bezier(.16, 1, .3, 1)` for spatial transitions.

All motion must remain usable under `prefers-reduced-motion: reduce`. Do not add looping ambient animation to the workbench.

## Component contracts

### Scan workflow

The rail has three stable semantic steps: read the role, compare evidence, and build the action plan. New backend steps should map into one of these user-facing stages unless they represent a genuinely new user decision. Avoid exposing internal agent orchestration as extra UI steps.

The connector belongs to the marker row, not the text row. Keep step labels below their markers at every breakpoint so the line can never cross copy. Validate with both short and translated/long labels before release.

### Saved opportunities

Each row shows company mark, role, company/location, one signal, score, and fit. Search filters the existing list. New metadata belongs in the inspector, not in denser rows.

### Evidence map

The map visualizes up to five strongest entries from `match.component_scores`, plus one most important real gap. Additional component scores must remain available in the Overview or Job details tab instead of adding orbit nodes indefinitely.

The orbit is an interactive index, not decoration. Every core, component, and gap point is a real button that supports hover, focus, and click/tap. Selection updates an adjacent explanation with three things: why the item affects the score, the verified profile facts that support it, and the role requirements it was compared against. When no component-specific fact is returned, say so explicitly instead of inferring or inventing one.

Coverage language is fixed to these bands:

| Score | Label | Meaning |
| --- | --- | --- |
| 75–100 | Strong | Strong verified coverage that actively supports the match. |
| 50–74 | Supported | Useful evidence exists, but coverage is not complete. |
| 25–49 | Partial | Some evidence exists and the missing portion limits the score. |
| 0–24 | Limited | Little verified coverage; never present this as a strength. |

Render the critical/gap node only when `missing_blockers` or `gaps` contains a real item. A must-have blocker must explain that it can cap the overall score. A no-gap result must not manufacture urgency.

### Inspector tabs

- **Evidence map:** default explanation and next action.
- **Overview:** summary metrics, strongest evidence, gaps, and advice.
- **Requirements:** reader correction and extracted role requirements.
- **Job details:** workflow trace, score components, applied caps, and history.

Add a tab only when a future concept supports repeated, substantial work. Small additions belong inside an existing tab.

## Fitting future concepts

| Future concept | Placement | Guardrail |
| --- | --- | --- |
| More scan intelligence | Existing three-step rail | Map internal steps to user outcomes; do not lengthen the rail casually. |
| New evidence categories | Evidence list plus component score details | Keep five primary orbit nodes and move overflow to text. |
| Interview preparation | New inspector tab only when it has a complete workflow | Reuse the selected role and verified evidence. |
| Application tracking | Stage control and Job details history | Do not add a second status surface. |
| Resume variants | Resume action flow | Keep one recommended action in the inspector; manage versions after the click. |
| Salary or market context | Overview | Label external data freshness and confidence. |
| Profile completeness | My profile | Surface only a concise blocker in the scanner when it prevents analysis. |
| Cross-role recommendations | Existing section below the workbench | Do not interrupt the selected-role decision. |

## Accessibility and content guardrails

- Preserve the global mint `:focus-visible` outline.
- Keep interactive targets at least 44px high on touch layouts.
- Use real buttons, links, tabs, tab panels, labels, and status text; color is never the only fit indicator.
- Maintain warm-cream text and semantic mint/coral/amber labels at accessible contrast on dark surfaces.
- Prefer plain language: “One gap to close” is better than a model-centric error label.
- Company logos should come from trustworthy source data. Until the API supplies them, use the existing Lucide company mark rather than invented brand assets.
- Essential secondary copy must be at least 12px in the workbench; reserve 11px only for genuinely tertiary metadata. Never use 8–10px text for explanations, scores, tab labels, or evidence.
- A score must remain fully contained at 100%, 200% zoom/reflow, long role titles, and every semantic fit color. Do not use clipping or decorative geometry that can cover digits.

## Visual review harness

The production-safe reference harness lives in `frontend/components/design/OpportunityPreview.tsx` and is enabled only for local review:

```powershell
$env:NEXT_PUBLIC_DESIGN_PREVIEW='1'
npm run dev -- --port 3001
```

The middleware bypass is limited to `/` and only activates when that environment variable is explicitly set. Do not set it in deployed environments.

The default fixture deliberately uses a long title, long location/work-mode metadata, a weak 39% match, mixed component coverage, and a critical blocker. Keep this hostile state: it is the regression test for score clipping, misleading labels, evidence honesty, and narrow-container reflow. Also retain at least one no-gap fixture.
