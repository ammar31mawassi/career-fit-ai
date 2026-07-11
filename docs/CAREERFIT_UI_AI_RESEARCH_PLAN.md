# CareerFit UI/UX and AI-agent research plan

Date: 2026-07-08

## Executive decision

CareerFit should become an **evidence-first career workspace**, not a generic AI dashboard and not an animation-heavy portfolio site.

The recommended product direction combines:

- **Evidence Studio** for the visual system and match explanation.
- **Guided Career Coach** for onboarding and clarification questions.
- **Mission Control** only for the repeat-user job library and application pipeline.

The AI should be a bounded workflow around the existing deterministic profile parser and matcher. The score must remain reproducible and evidence-backed. Small local models can assist with classification, semantic reconciliation, and writing, but an LLM should not directly invent the match percentage.

The highest-priority technical work is not fine-tuning. It is:

1. Instrument corrections and outcomes so the product creates a reliable training set.
2. Separate lightweight job summaries from large job-detail payloads.
3. Move scans to a durable background workflow with real progress events.
4. Improve extraction and fact reconciliation with embeddings and confidence gates.
5. Add calibrated supervised models only after enough reviewed data exists.

## Research scope and limitations

The audit covered:

- **62 Awwwards sites**: two current listing pages, 31 entries per page.
- **72 Dribbble web-design shots**: three current listing pages, 24 shots per page.
- **109 structured AI-agent use cases** in the repository README.
- **All 20 runnable agent examples** in the repository's `agents/` directory.

The repository is titled “500+”, but its current README contains 109 structured use-case rows and 20 runnable examples. This plan uses the material that actually exists in the current repository rather than treating the title as a verified count.

The Dribbble review used public shot titles and image descriptions/tags. Dribbble returned an empty `202` response to direct HTML requests, so this is a card-level visual-pattern audit, not a pixel-by-pixel review of 72 full case studies. Awwwards exposed richer structured tags and metadata.

## What the design research says

### Awwwards: brand, motion, and narrative

Across the 62 entries, the most common structured tags were:

| Pattern | Count |
|---|---:|
| Animation | 34 |
| GSAP | 26 |
| Interaction design | 20 |
| Web and interactive | 19 |
| Clean | 14 |
| WebGL | 14 |
| Microinteractions | 14 |
| Storytelling | 12 |
| 3D | 12 |
| UI design | 11 |
| Colorful | 10 |
| Minimal | 9 |
| Transitions | 9 |
| Responsive design | 7 |
| Typography | 7 |

Reusable lessons for CareerFit:

- A strong product identity comes from typography, transitions, and narrative hierarchy—not from filling every surface with cards.
- Motion should communicate state changes: a source was parsed, evidence was reconciled, a blocker changed, or a scan advanced.
- One or two memorable branded interactions are more effective than continuous decorative motion.
- Editorial layouts and visible evidence create more trust than an opaque “AI score” tile.

Patterns not to copy into the core product:

- WebGL or 3D backgrounds, scroll hijacking, unusual navigation, video backgrounds, and long reveal animations.
- Portfolio-style full-screen sections that hide task density.
- Motion that delays access to saved jobs or profile facts.

### Dribbble: product shells and component patterns

The 72-shot sample repeatedly used:

- AI/SaaS landing shells with oversized headlines and one dominant action.
- Dark financial or infrastructure dashboards with high-contrast accent colors.
- Bento grids, feature cards, compact tables, and inspector-style details.
- Editorial whitespace and large typography for professional-service products.
- Guided onboarding, login, and progressive forms.
- Glass effects and 3D illustrations as accents rather than the information layer.
- Visible work states: timelines, activity, progress, status pills, and completion indicators.

Reusable lessons for CareerFit:

- Use a compact opportunity list plus a detail inspector instead of expanding every job into a large card.
- Treat the scan input as the primary command surface.
- Use a calm guided flow for first-time profile creation, then switch to a denser repeat-use workspace.
- Keep one accent system: the existing mint for evidence/success and coral for gaps/actions is already distinctive.
- Bento layouts are useful only for the overview; tables/lists are better for a growing job library.

## Four viable UI directions

### Direction A — Evidence Studio (recommended foundation)

Positioning: “See exactly why a role fits and what to do next.”

Visual language:

- Editorial typography, strong negative space, dark ink surfaces, mint evidence markers, coral gap markers.
- Fewer but larger compositional regions instead of many equally weighted cards.
- A job result reads like an evidence report: requirements on the left, candidate evidence on the right, decision in the middle.
- Thin connecting lines and source badges show where each conclusion came from.

Home:

- A compact command bar for URL/description input.
- A searchable opportunity list with role, company, fit, confidence, blockers, and status.
- Selecting a row opens a persistent right-side inspector; resume advice loads only when opened.

Profile:

- Profile strength is shown as evidence coverage, not a vague completion ring.
- Facts are grouped by skills, projects, experience, education, and preferences.
- Each fact shows source count, evidence excerpt, confidence, and approve/edit/reject controls.
- Conflicting facts are displayed together for resolution.

Strengths: trustworthy, differentiated, aligned with the current evidence model, efficient for repeat use.

Risks: evidence relationships must remain readable on mobile; the visual system requires disciplined spacing and typography.

### Direction B — Career Mission Control

Positioning: “Manage your entire job search from one operating system.”

Visual language:

- Dark data-rich shell inspired by finance and infrastructure dashboards.
- Bento summary at the top, opportunity table below, pipeline/status rail at the side.
- Compact metrics: strong matches, blockers, applications, interview conversion, stale leads.

Home:

- Scan, filters, job library, and Lead/Applied/Interview pipeline in one screen.
- Batch actions and saved searches can be added later.
- Fit components can be shown as a compact breakdown rather than a single circle.

Profile:

- Readiness dashboard by target field.
- Skills and project coverage mapped to the user's selected career interests.

Strengths: powerful for active job seekers and scales to many jobs.

Risks: can become visually noisy; weak for first-time users; should not be the onboarding experience.

### Direction C — Guided Career Coach

Positioning: “Build a reliable profile and improve it one clear step at a time.”

Visual language:

- Warmer surfaces, more whitespace, conversational copy, one dominant next action.
- Progressive disclosure and a clear journey timeline.
- Calm motion and immediate validation.

Onboarding:

1. Upload CV.
2. Watch actual parsing stages.
3. Review high-impact facts and correct errors.
4. Add optional LinkedIn/GitHub/manual context.
5. Select interests.
6. Enter the workspace.

Ongoing profile:

- Clarification questions become a focused inbox.
- Answered questions disappear immediately and the next relevant question loads.
- The coach explains why a question affects matching.

Strengths: best comprehension and trust for new users; likely to reduce bad profile data.

Risks: slower for expert repeat users; should transition into Direction A or B after onboarding.

### Direction D — Opportunity Editorial

Positioning: “A curated feed of roles that tell you why they matter.”

Visual language:

- Large role typography, company color/image accents, story-like match explanations.
- Strong Awwwards-style transitions between opportunities.
- Designed for discovery and weekly digests.

Strengths: strongest brand impression and useful for a future discovery feed.

Risks: poor density for manually tracked jobs; expensive imagery; not recommended as the primary application shell.

### Recommended composition

Use Direction A as the product system, Direction C for onboarding/clarifications, and a restrained Direction B list/pipeline inside Home. Reserve Direction D for a future “Discover” or weekly-digest experience. This provides one coherent identity while matching interface density to user intent.

## Concrete UX architecture

### Global shell

- Keep only Home and Profile in primary navigation for the MVP.
- Add a universal search/command entry that searches saved jobs and can accept a new URL.
- Show a small persistent profile-evidence state: Ready, Needs review, or Missing CV.
- Preserve the current mint/coral brand but formalize color, spacing, radius, type, elevation, and motion tokens.
- Replace the monolithic stylesheet over time with route/component styles and a small token layer.

### Home

- Initial payload contains job summaries only: ID, company, role, location, score, confidence, blockers count, status, and updated time.
- Search and filters operate immediately against the cached summaries.
- Job details, requirements, evidence, history, and resume advice load on selection.
- Use a split-view inspector on desktop and a full-screen sheet on mobile.
- Add filters for fit band, status, field/interest, location/work mode, and blocker presence.
- Show empty states with a single next action, not decorative dashboard metrics.

### Scan experience

Replace the elapsed-time animation with real persisted stages:

1. Queued.
2. Fetching source.
3. Extracting job content.
4. Classifying requirements.
5. Matching profile evidence.
6. Building resume advice.
7. Ready or Needs input.

The initial request should return a run ID quickly. Supabase Realtime or server-sent events can update the UI from persisted `agent_steps`. If extraction confidence is low, stop and ask for a pasted description instead of silently scoring weak text.

### Profile

- Use source-backed fact rows, not isolated chips.
- Merge equivalent facts while retaining all supporting source IDs and excerpts.
- Highlight contradictions separately from low-confidence facts.
- Keep approve, edit, and reject visible without opening a modal.
- Add manual facts within each section using the existing Add action.
- Make evidence coverage specific to the selected career interests.

### Motion and accessibility rules

- Animate only `transform` and `opacity` for common transitions.
- Use 120–220 ms for controls, 220–360 ms for panels, and no blocking entrance animation.
- Respect `prefers-reduced-motion`.
- Preserve focus across drawers and route transitions.
- Maintain 44 px touch targets, visible focus, semantic progress/status announcements, and WCAG AA contrast.
- Never encode match/gap state by color alone.

## AI system: recommended architecture

### Principle

An agent is a controlled workflow with state, tools, permissions, retries, and evaluation. It is not simply an LLM prompt. CareerFit should use a hybrid system:

```text
User sources / job URL
        ↓
Bounded ingestion tools
        ↓
Extraction + normalization + provenance
        ↓
Confidence gate / clarification
        ↓
Deterministic requirement and fit model
        ↓
Optional model-assisted explanation and resume text
        ↓
Human approval for external actions
        ↓
Feedback and outcome dataset
```

### Agents/workflows to build

#### 1. Profile reconciliation workflow — now

- Parse each source separately.
- Normalize skill/project/company/date entities.
- Use exact aliases first, then local sentence embeddings for semantic duplicate candidates.
- Merge only above a tested threshold and preserve all source evidence.
- Route conflicts and uncertain merges to user review.
- Learn from approve/edit/reject feedback.

#### 2. Job reader workflow — now

- Validate URLs and block private-network access.
- Prefer structured JSON-LD and known source adapters.
- Fall back to clean HTML extraction.
- Detect login walls, bot pages, stale jobs, and insufficient descriptions.
- Store a source snapshot and extraction completeness.
- Ask for manual text when confidence is below threshold.

#### 3. Requirement classifier — now/next

- Classify each requirement as must-have, preferred, nice-to-have, years/seniority, education, location/work mode, language, authorization, or responsibility.
- Keep the original evidence sentence.
- Start rules-first; add a small supervised classifier after reviewed labels accumulate.

#### 4. Match judge — keep deterministic

- The existing weighted evidence matcher remains the source of truth.
- Zero experience versus required professional experience remains a hard penalty/cap.
- Missing must-haves outweigh nice-to-have overlap.
- Semantic similarity can propose matches but cannot override hard requirements.
- Version every score and retain the feature/component breakdown.

#### 5. Resume advisor — next

- Select only evidenced projects and skills.
- Use the existing templates for deterministic fallback.
- A small local instruction model may later rewrite tone while constrained to supplied facts.
- Validate that generated text introduces no unsupported claims.

#### 6. Opportunity research workflow — later

- Given user interests and profile, collect jobs from sources that permit it.
- Deduplicate by canonical URL, company/role/location, and description hash.
- Rank with the same match judge.
- Never bypass site terms, logins, robots restrictions, or application controls.

#### 7. Match digest/email workflow — later

- Opt-in daily/weekly digests only.
- Queue recommendations, deduplicate them, and render a preview.
- Send through an email provider with an idempotency key and unsubscribe link.
- Log delivery and click/open/application events only with clear consent.
- Do not auto-apply or contact companies without a separate explicit approval step.

#### 8. Career coach workflow — later

- Uses gaps across repeated target jobs to recommend a prioritized learning/project plan.
- Explains which improvement changes the largest number of matches.
- Separates realistic short-term additions from experience that cannot be honestly manufactured.

#### 9. Evaluation workflow — now

- Re-run a fixed benchmark corpus on every parser, ontology, rule, or model change.
- Compare output to human-reviewed facts and requirements.
- Block releases on regression in must-have recall, false fact rate, duplicate merge precision, or score calibration.

### Workflow safety and observability

Add these records before adding autonomous behavior:

- `agent_runs`: workflow type, user, input reference, status, version, timestamps, error.
- `agent_steps`: run, step type, status, attempt, progress copy, timing, structured output.
- `model_predictions`: task, model version, input hash, output, confidence, latency.
- `review_events`: prediction/fact, original value, user decision, corrected value.
- `recommendation_events`: job/user/model version, shown, opened, saved, applied, outcome.
- `notification_preferences` and `notification_deliveries`.

Every tool call must be idempotent. External writes—email, calendar, application, or message—need an approval or an explicit standing opt-in scoped to that action.

## Fine-tuning: where it helps and where it does not

### Short answer

Fine-tuning can help later, but it will not by itself create a good agent or a reliable match score. The current bottleneck is labeled, reviewed data and evaluation—not model training.

### Good fine-tuning targets

- Requirement-type classification.
- CV/LinkedIn span classification into skill, project, experience, education, and metadata.
- Entity normalization and duplicate-pair classification.
- Career-interest taxonomy mapping.
- Resume summary tone constrained to verified facts.

For these narrow tasks, start with a small encoder/classifier. A fine-tuned BERT-style model is often cheaper and more stable than a generative LLM. Use Sentence Transformers for semantic candidate generation, then a classifier or rule gate for the final merge decision.

### Bad first fine-tuning targets

- Generating the final percentage directly.
- Learning from Lead/Applied status alone; those are user workflow labels, not job-fit truth.
- Replacing fresh job retrieval; training weights do not contain current postings.
- Giving an agent permission to send emails or apply to jobs.
- Training on unreviewed parser output, which would reinforce current mistakes.

### Match-model evolution

#### Stage 0 — current deterministic baseline

Keep hard constraints, penalties, evidence coverage, and versioned explanations. Add a frozen benchmark corpus.

#### Stage 1 — semantic assistance

Run a small local embedding model for duplicate candidates and skill/requirement similarity. Treat similarity as a feature, not a decision.

#### Stage 2 — calibrated supervised fit model

After collecting reviewed pairs, train logistic regression or gradient-boosted trees on interpretable features:

- Must-have coverage and weighted missing count.
- Required versus evidenced years.
- Seniority gap.
- Preferred/nice-to-have coverage.
- Education, language, location, work-mode, authorization, and availability compatibility.
- Evidence confidence and source support.
- Project/domain similarity.
- Extraction completeness.

Calibrate the output with sigmoid/temperature scaling at first. Isotonic calibration should wait for substantially more calibration data because it can overfit small samples. The UI should call this a “match score” until outcome calibration proves it behaves like a real probability.

#### Stage 3 — job recommendation ranking

When each user has enough candidate jobs and outcomes, train a learning-to-rank model for ordering jobs. Ranking and fit scoring are related but not identical: a person can fit several roles, while ranking also reflects interests, location, freshness, and preferences.

#### Stage 4 — parameter-efficient LLM tuning

Use LoRA/QLoRA on a small open model only after the product has a clean task-specific dataset and a strong held-out evaluation. This is most useful for structured extraction or fact-constrained writing, not the core score.

### Data gates before model promotion

These are engineering gates, not promises that sample count alone guarantees quality:

- Every training record has a human-reviewed label or a clearly defined behavioral outcome.
- User-level and time-based train/test splits prevent the same person's text or near-duplicate jobs from leaking into both sets.
- Sensitive attributes such as name, age, gender, ethnicity, photo, and nationality are excluded from score features unless a legally necessary, user-controlled work-authorization field is explicitly relevant.
- Compare against the deterministic baseline and simple logistic regression.
- Track per-segment errors and calibration, not only average accuracy.
- Do not promote a model unless it improves the relevant benchmark without increasing blocker false negatives.

Suggested practical thresholds:

- Begin experiments around 1,000 reviewed extraction/classification examples.
- Do not replace score rules with supervised output until there are several thousand diverse reviewed profile-job pairs and meaningful outcomes.
- Keep the deterministic fallback even after model launch.

### Cost and deployment reality

- Small embedding and classification models can run on CPU and scale to zero.
- LoRA/QLoRA reduces training memory, but inference still consumes compute.
- “Free cloud forever” is not a reliable production assumption. Design the system so model-assisted features degrade to deterministic extraction/templates when a free tier is asleep or unavailable.
- Store model artifacts and version metadata independently from the web application deployment.

## Performance plan tailored to the current codebase

### Current findings

- `frontend/lib/api.ts` forces `cache: "no-store"` for every request.
- `AppDataProvider` caches the entire profile and full job objects in `sessionStorage` for five minutes.
- The jobs list returns descriptions, requirements, match evidence, status history, and resume advice for up to 100 jobs even when the first screen needs only summaries.
- `HomeClient.tsx`, `ProfileClient.tsx`, and `globals.css` are already large client/style surfaces.
- `job_research.py` is over 1,000 lines and scan work currently happens within a request.
- A route loading state and scan animation already exist; the problem is that scan progress is estimated rather than tied to durable backend stages.
- Profile ingestion/onboarding code is the highest-change area in the young repository, so changes there need benchmark tests and staged rollout.

### Phase P0 — measure before optimizing

- Add browser real-user monitoring for LCP, INP, and CLS.
- Track frontend route transition time, API TTFB, payload bytes, and hydration time.
- Track scan queue time and each persisted scan stage at p50/p95.
- Establish targets: p75 LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1; cached Home usable in ≤ 1 s; scan accepted in ≤ 300 ms.

### Phase P1 — reduce payload and blocking work

- Add `GET /api/jobs/summary?cursor=...` and keep `GET /api/jobs/{id}` for detail.
- Paginate summaries; fetch 20–30 initially.
- Return profile header/readiness separately from the full fact/source payload if Home only needs onboarding state.
- Select only required database columns for list queries.
- Move URL fetch, extraction, matching, and advice into a queue-backed run.
- Return `202 Accepted` plus `run_id`; persist and stream real progress.

### Phase P2 — caching and navigation

- Cache private data only in the authenticated browser or user-scoped server layer; never shared CDN cache.
- Use ETags/`If-None-Match` for profile and job summary responses.
- Replace whole-workspace session serialization with small, versioned summary caches.
- Keep stale summaries visible while refreshing in the background.
- Let Next.js prefetch Home/Profile routes and add meaningful route/component Suspense boundaries.
- Avoid refreshing profile and jobs after mutations that can be updated optimistically from the response.

### Phase P3 — bundle and render cost

- Dynamically import the job-detail/resume-advice inspector and any future charts.
- Split client components around interactive islands; render stable shell/copy as server components where practical.
- Split `globals.css` into tokens, shared primitives, and route/component styles.
- Virtualize the job list only when measured list size justifies it; pagination is simpler first.
- Audit bundles in CI and set route-level JavaScript budgets.
- Keep animations on compositor-friendly properties and disable unnecessary work off-screen.

### Phase P4 — database and worker reliability

- Add/verify composite indexes for user + updated time/status and canonical/content hashes.
- Cache canonical job extraction globally by safe content hash where terms allow; keep each user's match private and separate.
- Use Supabase Queues/PGMQ for durable scan work and Cron for scheduled discovery/digests.
- Archive step events for debugging; retry only idempotent steps with bounded exponential backoff.

## Implementation roadmap

### Milestone 0 — benchmark and telemetry (3–5 days)

- Freeze a reviewed corpus from Ammar, Marwan, Dima, and new anonymized examples.
- Add parser/matcher regression reports.
- Add performance and scan-stage telemetry.
- Define score/model version metadata and release gates.

Exit: current quality and latency are measurable, and regressions can block a release.

### Milestone 1 — UX architecture and speed (1–2 weeks)

- Implement Evidence Studio tokens and shell.
- Build summary list + detail inspector.
- Add real skeletons/Suspense boundaries and stale-while-refresh behavior.
- Add summary/detail endpoints, pagination, ETags, and lighter profile header.
- Preserve current features and responsive behavior.

Exit: Home becomes usable quickly without downloading every job detail.

### Milestone 2 — durable scan workflow (1–2 weeks)

- Add `agent_runs`/`agent_steps` and queue-backed scans.
- Implement real progress updates and resumable failure states.
- Add extraction-confidence gates and manual-description recovery.
- Expand job-source test fixtures, especially Goozali and common ATS pages.

Exit: closing/reloading the page does not lose a scan; low-quality extraction never silently produces a confident match.

### Milestone 3 — profile trust and reconciliation (1–2 weeks)

- Add local embeddings for duplicate candidates.
- Add conflict resolution and evidence comparison UI.
- Capture all approve/edit/reject events as labeled feedback.
- Improve onboarding review before allowing entry.

Exit: duplicate merge precision and fact extraction quality improve on the frozen benchmark.

### Milestone 4 — recommendation and notification beta (2 weeks)

- Add opt-in saved search/preferences.
- Build a scheduled discovery adapter only for permitted sources.
- Rank with deterministic match + interests/freshness.
- Add previewable weekly email digest with dedupe, unsubscribe, and delivery log.

Exit: users receive only new, relevant jobs and can explain why each was selected.

### Milestone 5 — learned models (after data gates)

- Train requirement/fact classifiers first.
- Train and calibrate an interpretable fit model as a shadow model.
- Compare shadow output to rules and human reviews.
- Experiment with a small LoRA adapter only for extraction or constrained resume writing.

Exit: a model is promoted only when it beats the deterministic baseline on held-out users/time periods and maintains blocker safety.

## Success metrics

Product:

- Profile review completion rate.
- Median time from signup to first trustworthy match.
- Job-detail open, save, and apply conversion.
- Weekly return rate and digest unsubscribe rate.

Extraction:

- Fact precision/recall by type.
- False-fact rate.
- Duplicate merge precision/recall.
- Requirement classification macro-F1 and must-have recall.
- Low-confidence recovery success.

Matching:

- Human agreement on fit band and blockers.
- Brier score/reliability diagram once scores are calibrated.
- NDCG@10 for recommendations.
- Interview/positive-response rate, treated carefully because outcomes also depend on market and application quality.

Performance:

- Core Web Vitals at p75.
- Home payload size and time-to-usable.
- Scan p50/p95 by stage.
- Worker retry/failure rate.

## Full GitHub idea triage

Legend: **A** adopt in the next two milestones; **B** useful later; **P** borrow a pattern, not the domain implementation; **N** no current product fit.

### Industry use cases (24/24)

| # | Idea | Decision |
|---:|---|---|
| 1 | HIA (Health Insights Agent) | P—evidence-backed document interpretation |
| 2 | AI Health Assistant | N—medical diagnosis is unrelated/high risk |
| 3 | Automated Trading Bot | N—unrelated autonomous action |
| 4 | Agent Wallet SDK | P—permission and spend/action limits |
| 5 | Virtual AI Tutor | B—career coach and learning-plan interaction |
| 6 | 24/7 AI Chatbot | B—bounded profile/job support, not open-ended scoring |
| 7 | Product Recommendation Agent | A—job recommendation and ranking pattern |
| 8 | Self-Driving Delivery Agent | N—unrelated physical autonomy |
| 9 | Factory Process Monitoring Agent | P—workflow health and anomaly monitoring |
| 10 | Property Pricing Agent | P—calibrated prediction with interpretable features |
| 11 | Smart Farming Assistant | N—unrelated domain |
| 12 | Energy Demand Forecasting Agent | P—time-based evaluation and drift monitoring |
| 13 | Content Personalization Agent | A—personalized job ordering and digest content |
| 14 | Legal Document Review Assistant | P—source citations and clause/fact extraction |
| 15 | Recruitment Recommendation Agent | A—directly relevant, adapted candidate-side |
| 16 | Virtual Travel Assistant | P—preference-constrained planning |
| 17 | AI Game Companion Agent | N—unrelated domain |
| 18 | Real-Time Threat Detection Agent | P—URL/fetch security and abuse monitoring |
| 19 | E-commerce Personal Shopper Agent | A—preference-aware recommendation pattern |
| 20 | Logistics Optimization Agent | P—ranking under constraints |
| 21 | Vibe Hacking Agent | N—red-team domain; retain ordinary security testing only |
| 22 | Citadel | P—lifecycle hooks, postmortems, and bounded orchestration |
| 23 | MediSuite-AI-Agent | P—auditable multi-step workflow |
| 24 | Lina Egyptian Medical Chatbot | N—unrelated medical chatbot |

### CrewAI use cases (22/22)

| # | Idea | Decision |
|---:|---|---|
| 25 | Email Auto Responder Flow | B—opt-in digest/notification workflow; no auto-replies initially |
| 26 | Meeting Assistant Flow | N—out of scope |
| 27 | Self Evaluation Loop Flow | A—user review and correction feedback loop |
| 28 | Lead Score Flow | P—interpretable weighted scoring and calibration |
| 29 | Marketing Strategy Generator | N—out of scope |
| 30 | Job Posting Generator | A—reverse its requirement decomposition logic |
| 31 | Recruitment Workflow | A—stateful job/profile/match pipeline |
| 32 | Match Profile to Positions | A—direct relevance, but keep deterministic scoring |
| 33 | Instagram Post Generator | N—out of scope |
| 34 | Landing Page Generator | N—out of scope |
| 35 | Game Builder Crew | N—out of scope |
| 36 | Stock Analysis Tool | N—out of scope |
| 37 | Trip Planner | N—out of scope |
| 38 | Surprise Trip Planner | N—out of scope |
| 39 | Write a Book with Flows | P—long-form staged template workflow |
| 40 | Screenplay Writer | P—structured template generation |
| 41 | Markdown Validator | P—post-generation validation pattern |
| 42 | Meta Quest Knowledge | B—retrieval over reviewed career/profile knowledge |
| 43 | NVIDIA Models Integration | P—provider-independent local model adapter |
| 44 | Prep for a Meeting | N—out of scope |
| 45 | Starter Template | P—project structure only |
| 46 | CrewAI + LangGraph Integration | P—avoid mixing frameworks until orchestration needs justify it |

### AutoGen use cases (28/28)

| # | Idea | Decision |
|---:|---|---|
| 47 | Automated code generation/execution/debugging | N—unsafe and unrelated to user workflow |
| 48 | Code Q&A with retrieval agents | P—retrieval pattern only |
| 49 | Code Q&A with Qdrant retrieval | P—vector retrieval pattern; use existing Postgres/pgvector instead |
| 50 | Group chat with manager | P—supervisor concept, not a need for many agents |
| 51 | Data visualization by group chat | N—ordinary deterministic charts are sufficient |
| 52 | Complex task solving by six agents | N—unnecessary cost/complexity |
| 53 | Coding and planning agents | P—separate plan from execution |
| 54 | Graph transition paths | A—explicit scan/profile state machines |
| 55 | Society-of-Mind inner monologue | N—no product need and poor auditability |
| 56 | Custom speaker selection | N—no multi-agent conversation required |
| 57 | Sequential task solving | A—scan stages and retries |
| 58 | Async sequential task solving | A—background scans and scheduled discovery |
| 59 | Sequential chats with different initiators | P—event-triggered workflow starts |
| 60 | Nested chats for complex tasks | P—nested subflows only when justified |
| 61 | Sequence of nested chats | P—resume advice after successful match |
| 62 | Supply-chain nested chats | N—domain implementation unrelated |
| 63 | Conversational chess | N—unrelated |
| 64 | Web search for current information | B—company/job research with source controls |
| 65 | Tools as functions | A—typed, allow-listed tools |
| 66 | RAG group chat | P—retrieval without group-chat overhead |
| 67 | Whisper agent | B—optional accessibility/voice notes only |
| 68 | Natural-language SQL | P—internal admin analytics only; never direct user DB access |
| 69 | DALL-E/GPT-4V multimodal agent | N—out of scope |
| 70 | LLaVA multimodal agent | B—possible OCR/layout fallback for scanned CVs |
| 71 | GPT-4V multimodal agent | B—same OCR/layout use, provider-independent |
| 72 | AgentEval | A—benchmark and regression evaluation |
| 73 | AgentOps monitoring | A—step timing, errors, and model/tool telemetry |
| 74 | AgentBuilder | N—hand-designed workflows are safer here |

### Agno use cases (17/17)

| # | Idea | Decision |
|---:|---|---|
| 75 | Support Agent | B—product support constrained to docs and user state |
| 76 | YouTube Agent | N—out of scope |
| 77 | Finance Agent | N—out of scope |
| 78 | Study Partner | B—career learning/project plan |
| 79 | Shopping Partner | P—preference-aware recommendation pattern |
| 80 | Research Scholar | P—structured research reports with citations |
| 81 | Research Agent | B—job/company research |
| 82 | Recipe Creator | N—out of scope |
| 83 | Financial Reasoning Agent | N—out of scope |
| 84 | README Generator | N—out of scope |
| 85 | Movie Recommendation Agent | P—recommendation evaluation pattern |
| 86 | Media Trend Analysis Agent | B—job-market and skill-demand trends |
| 87 | Legal Document Analysis Agent | P—PDF extraction and cited evidence |
| 88 | DeepKnowledge | P—iterative retrieval when evidence is insufficient |
| 89 | Book Recommendation Agent | P—personalization/ranking pattern |
| 90 | MCP Airbnb Agent | N—out of scope |
| 91 | Agno Assist Agent | N—framework support bot unrelated |

### LangGraph use cases (18/18)

| # | Idea | Decision |
|---:|---|---|
| 92 | Chatbot simulation evaluation | A—simulate and regression-test interaction paths |
| 93 | Information gathering via prompting | A—clarification-question workflow |
| 94 | Code assistant | N—out of scope |
| 95 | Customer support agent | B—human escalation and bounded answers |
| 96 | Extraction with retries | A—core parser reliability pattern |
| 97 | Multi-agent supervisor | P—one orchestrator, specialized deterministic steps |
| 98 | Hierarchical agent teams | N—premature complexity |
| 99 | Multi-agent collaboration | N—premature complexity |
| 100 | Plan-and-execute agent | P—use explicit plans only for variable research tasks |
| 101 | SQL agent | P—internal read-only analytics only |
| 102 | Reflection agent | B—validate extracted requirements/advice against evidence |
| 103 | Reflexion agent | B—retry with error feedback, with strict attempt limits |
| 104 | Adaptive RAG | B—retrieve more only when confidence is low |
| 105 | Agentic RAG | B—tool choice for company/job research |
| 106 | Corrective RAG | B—reject weak sources and retry retrieval |
| 107 | Self-RAG | P—use bounded evidence sufficiency checks |
| 108 | Adaptive RAG (local) | B—preferred privacy-preserving path |
| 109 | Self-RAG (local) | B—local evidence checks after benchmarks exist |

### Runnable examples (20/20)

| Example | CareerFit takeaway |
|---|---|
| Web research agent | Bounded current-job/company research with citations |
| Code review agent | Output validation pattern, not a product feature |
| PDF Q&A agent | PDF chunking/evidence retrieval pattern |
| SQL query agent | Internal read-only analytics only |
| Email drafting agent | Draft digest copy; sending remains opt-in and idempotent |
| News summarizer agent | Market-trend digest pattern |
| GitHub issue triager | Taxonomy classification pattern |
| Data analysis agent | Offline model/evaluation reporting |
| Resume parser agent | Relevant caution: its LLM-generated fit score must not be copied |
| Meeting notes agent | No current fit |
| Stock research agent | Research-source orchestration pattern only |
| Travel planner agent | Preference-constrained planning pattern |
| Customer support agent | Retrieval plus human escalation |
| Social media agent | No current fit |
| Unit test generator | No user feature; useful development practice only |
| Documentation writer | No user feature; possible internal documentation aid |
| Recipe agent | No current fit |
| Job application agent | Tailored bullets/cover letter/interview prep, always fact-constrained |
| Competitive analysis agent | Company research and structured multi-step state |
| Multi-agent debate | Do not adopt; deterministic validators are cheaper and more auditable |

The runnable examples are educational prototypes. Most depend directly on hosted LLMs and omit production requirements such as privacy boundaries, typed schemas, idempotency, source provenance, evaluation, and user approval. They should be mined for workflow shapes, not copied as production architecture.

## Audited design inventory

### Awwwards, 62 entries

Page 1: Julien Calot; Depo Luxe; MONOLOG; Hildén & Kaira; Radian; Bucks Sauce; Units; Wembi; NRG — Build Your Data Center; Meech213; IVRESS SPIN A TALE; Podium; Ten Years Away; IL CAPO PRODUCTION; Wolverine Worldwide; Sui; EverSwap; digitalists; RPA COMUNICACIÓN; Balmoral; Indigo Laboratory; Gucci: Mystery Unfolds; Fauna Robotics; Elva; sakazuki; House of Honey; What If Orwell Had a Website; Halston: Architecture template; Susie & Jay: A Journey of Love; Produx Design; Qiao.

Page 2: Grain & Mortar; Crav Burgers; Spatial Festival; Charmer Studio; Supari Studios; Acova; Pixelismo Studio; cmd+zest; duoswynwood.com; Lasala Plaza Hotel; My Web Lab; Tresmares Capital; Septiembre Arquitectura; Teka Teki Studios; D D O T T Type Foundry; ARETÈ IMMOBILIARE; Serve Robotics; Zorge 9; Hello Party; nirnor inc.; Ponder AI; Haven Constructions; Armory AI Agency; Emily Nixon; Gusta; Hubtown; Ome Duo Events; Copula Agency; Raw House; Relais Rossar; Pacôme Pertant Portfolio.

### Dribbble, 72 shots

Page 1: Atlas AI landing page; Marketplace Web Storefront; Video Production Agency Website; BNPL Pay Later; ORBITO AI Agent Platform; AI-Powered Notetaker; Digital Marketing Agency; SaaS Developer Cloud/Data Extraction; Trading Dashboard; Creative Agency; AI Travel Planner Login; SENCHA; Manufacturing Platform; AI Voice Agents; Supply Chain Authentication; Digital Wallet; Project Management Dashboard; Beverage E-commerce; Minimal Insurance; Furniture Store; Wealth Management About; BestOdds Guides/Glossary; Solar Energy; Medical Brand Illustrations.

Page 2: Neurovia 3D landing page; AI Inbox Management SaaS; SOERA Creative Studio; Music Intelligence Platform; Escape Wellness & Travel; Hero Untitled UI; Healthcare UI/UX; HR Employee Self-Service; Parco Financial Dashboard; WebGenius AI Music; Industrial Construction Service; SMILO Dental; Smart Habit Tracker; AI Finance/DeFi; VoltPay Fintech; Study Buddy AI Tutor; Web3 Wallet/DeFi; Strategic Consulting; Pinstack Agency; Nextel SaaS; DigitalCoins Trading Journal; Real Estate; Agentic AI Cloud Platform; Modern Furniture.

Page 3: Charity & Donation; Finance SaaS Dashboard; Live Sports Betting; Spindice Pricing; Healthy Bite Dental; Ponder AI Mobile Scroll; Moonstay Cabin; AeroCrop.ai; Music UI/UX; Developer Portfolio; AI Biotech; Animated AI Feature Cards; Untitled UI Header; Smart Pet Adoption; Golf Companion; Noma Creative Studio; eCommerce Cart Drawer; Bluechip26 Fintech Conference; Specter DeFi; Mosta; Umbrave Analytics; Orbita Spacecraft; Sunvora Solar; Wellness Supplement Contact.

## Sources

- [Awwwards winning websites](https://www.awwwards.com/websites/)
- [Dribbble popular web-design shots](https://dribbble.com/shots/popular/web-design)
- [500+ AI Agent Projects repository](https://github.com/ashishpatel26/500-AI-Agents-Projects)
- [ReAct paper](https://arxiv.org/abs/2210.03629)
- [Hugging Face PEFT and LoRA](https://huggingface.co/docs/peft/main/en/package_reference/lora)
- [QLoRA paper](https://arxiv.org/abs/2305.14314)
- [Sentence Transformers semantic similarity](https://sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html)
- [scikit-learn probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [XGBoost learning to rank](https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html)
- [Next.js prefetching](https://nextjs.org/docs/app/guides/prefetching)
- [Next.js fetching, streaming, and Suspense](https://nextjs.org/docs/app/getting-started/fetching-data)
- [Next.js lazy loading](https://nextjs.org/docs/app/guides/lazy-loading)
- [Core Web Vitals thresholds](https://web.dev/articles/defining-core-web-vitals-thresholds)
- [Supabase Queues](https://supabase.com/docs/guides/queues/quickstart)
- [Supabase scheduled Edge Functions](https://supabase.com/docs/guides/functions/schedule-functions)
- [Resend send-email API](https://resend.com/docs/api-reference/emails/send-email)
