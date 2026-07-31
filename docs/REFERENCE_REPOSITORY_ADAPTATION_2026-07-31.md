# Reference Repository Review and CareerFit Adaptation Plan

**Review date:** 2026-07-31

**CareerFit baseline at draft time:** main at [2876447](https://github.com/ammar31mawassi/career-fit-ai/commit/2876447afee013d680c32635a01693fbd4e63105), with the adaptations described below present in the working tree

**Database contract described:** v24 (v23 application-event context plus v24 source-health statuses)

**Status:** automated local gates are complete; remaining P0 manual/beta checks, beta migration, deployment, and deployed smoke testing remain pending

## Purpose and scope

This report evaluates five public repositories as design references for CareerFit:

1. [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search)
2. [santifer/career-ops](https://github.com/santifer/career-ops)
3. [surapuramakhil-org/Job_search_agent](https://github.com/surapuramakhil-org/Job_search_agent)
4. [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop)
5. [intergalacticalvariable/reader](https://github.com/intergalacticalvariable/reader)

The review covered each repository's checked-out source, configuration, documentation, tests, license, and Git history. The goal was not to merge another project into CareerFit. It was to identify sound engineering ideas, reject unsafe or unsuitable ideas, and implement a small set of CareerFit-native improvements.

All CareerFit changes discussed here were independently designed for CareerFit's existing FastAPI, SQLModel, PostgreSQL/Supabase, Next.js, and deterministic matching architecture. This review does **not** claim that source code or prompt prose was copied from any reference repository.

## Executive decision

The five repositories are not interchangeable:

- **ai-job-search** is the strongest reference for safety boundaries, evidence-grounded application material, source health, bounded retries, and outcome feedback.
- **career-ops** is the strongest reference for an application event ledger, provider contracts, deduplication/provenance, funnel analytics, and local-first operational discipline.
- **no-ai-slop** is useful as a narrow writing-quality reference: named, explainable findings; minimal edits; and a post-generation check. It is not a hiring, scoring, or authorship-detection system.
- **reader** contributes one useful architectural idea: record extraction strategy and provenance, and consider a controlled rendered-page fallback only when static extraction cannot work. Its service is not safe to deploy as-is.
- **Job_search_agent** demonstrates provider and search strategy abstractions, structured model output, and fixture-backed portal tests. Its license, credential exposure, automatic submission behavior, fabricated-answer prompts, fail-open paths, and weak test posture make it unsuitable for code reuse or operational adoption.

The current CareerFit work therefore adopts four bounded ideas:

1. an evidence-and-clarity postcondition for resume advice;
2. richer append-only application status events;
3. extraction provenance exposed to the user;
4. a degraded/inconclusive source-health circuit breaker that prevents destructive deactivation after suspicious source runs.

It deliberately does not add a browser automation service, automatic application submission, an LLM gateway, a Markdown database, or AGPL-derived implementation code.

## Cross-cutting engineering lessons

The useful lessons extend beyond job-search software:

- **Validate meaning, not only syntax.** A 200 response or valid JSON can still represent parser failure. Contract validity, usable-yield ratios, historical baselines, and provenance are stronger checks.
- **Make destructive behavior require positive evidence.** Unknown, empty, or degraded input should preserve existing state. Deletion and deactivation should happen only after a healthy observation.
- **Separate event time from audit time.** Business analytics need when something happened; incident analysis needs when the system recorded it. Keep both.
- **Prefer append-only history over mutable summaries.** A materialized current state is useful, but the transition ledger is what makes corrections, analytics, and investigations possible.
- **Version derived output.** Reader, model, ontology, template, and output-policy versions determine whether a cached result is still trustworthy.
- **Put a deterministic postcondition after probabilistic or heuristic work.** Generation and extraction can be flexible; persisted output must satisfy explicit, testable invariants.
- **Keep high-stakes decisions typed and executable.** Authorization, eligibility, scoring caps, state transitions, and tenant isolation should not live only in prompts or prose.
- **Use provider adapters at the unstable edge.** Source-specific parsing belongs behind a small contract with offline fixtures, while the core domain consumes normalized values.
- **Expose provenance to the user.** Confidence is more meaningful when users can see what source and extraction path produced it.
- **Design network code with budgets.** Timeouts, bounded retries, jitter, redirect checks, response-size limits, and structured failure codes are part of correctness.
- **Preserve user agency.** Advice can be drafted and checked automatically; consequential submissions, representations, and corrections require explicit user review.
- **Treat license and supply-chain evidence as architecture inputs.** A useful idea does not make an implementation, dependency tree, fixture archive, or deployment model safe to adopt.

## Review snapshot and license ledger

The commit identifiers below make the review reproducible. They are immutable review snapshots, not claims that the repositories will remain unchanged.

| Repository | Reviewed head | License posture | Maturity signal | CareerFit decision |
| --- | --- | --- | --- | --- |
| [ai-job-search](https://github.com/MadsLorentzen/ai-job-search/tree/2c41210019f4a4134fe38f87a5e17243950a9a97) | [2c41210019f4a4134fe38f87a5e17243950a9a97](https://github.com/MadsLorentzen/ai-job-search/commit/2c41210019f4a4134fe38f87a5e17243950a9a97), 2026-07-31 | [MIT](https://github.com/MadsLorentzen/ai-job-search/blob/2c41210019f4a4134fe38f87a5e17243950a9a97/LICENSE) | Young and fast-moving; 138 commits, broad recent contribution, solid Python and TypeScript fixture tests | Adopt selected safety, evidence, health, and feedback concepts independently |
| [career-ops](https://github.com/santifer/career-ops/tree/37a5184ba0bbcb590f5e17cfbf6a718db1527460) | [37a5184ba0bbcb590f5e17cfbf6a718db1527460](https://github.com/santifer/career-ops/commit/37a5184ba0bbcb590f5e17cfbf6a718db1527460), 2026-07-31 | [MIT](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/LICENSE), plus [trademark restrictions](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/TRADEMARK.md) | Approximately four months old and highly active; 1,045 commits; large quick-test suite, but several monoliths | Adopt event, provenance, provider-contract, and analytics concepts independently |
| [Job_search_agent](https://github.com/surapuramakhil-org/Job_search_agent/tree/9229e64eb1696ae2eb385c56c4f93e0be6892ab3) | [9229e64eb1696ae2eb385c56c4f93e0be6892ab3](https://github.com/surapuramakhil-org/Job_search_agent/commit/9229e64eb1696ae2eb385c56c4f93e0be6892ab3), 2026-05-22 | Code: [AGPL-3.0](https://github.com/surapuramakhil-org/Job_search_agent/blob/9229e64eb1696ae2eb385c56c4f93e0be6892ab3/LICENSE); docs: [CC BY 4.0](https://github.com/surapuramakhil-org/Job_search_agent/blob/9229e64eb1696ae2eb385c56c4f93e0be6892ab3/docs/LICENSE) | Human bus factor one; functional CI disabled; only Dependabot active recently | Concept-only clean-room reference; no code, prompts, fixtures, or assets reused |
| [no-ai-slop](https://github.com/petergyang/no-ai-slop/tree/e81170dcaefa76b4cb2672532e13042f4e132b32) | [e81170dcaefa76b4cb2672532e13042f4e132b32](https://github.com/petergyang/no-ai-slop/commit/e81170dcaefa76b4cb2672532e13042f4e132b32), 2026-07-26 | [MIT](https://github.com/petergyang/no-ai-slop/blob/e81170dcaefa76b4cb2672532e13042f4e132b32/LICENSE) | Narrow 14-commit, one-maintainer skill package; packaging check but no behavioral detector suite | Adopt explainable writing checks as deterministic CareerFit postconditions |
| [reader](https://github.com/intergalacticalvariable/reader/tree/d259179f7a6adc308f6c94e843837a1b95383e2d) | [d259179f7a6adc308f6c94e843837a1b95383e2d](https://github.com/intergalacticalvariable/reader/commit/d259179f7a6adc308f6c94e843837a1b95383e2d), 2025-07-18 | Root [Apache-2.0](https://github.com/intergalacticalvariable/reader/blob/d259179f7a6adc308f6c94e843837a1b95383e2d/LICENSE); a package-level ISC declaration conflicts, so Apache was treated as controlling | Archived; no meaningful test/CI safety net; broken lockfile and substantial dependency risk | Adopt provenance concept only; do not adopt service or dependencies |

## What CareerFit implemented now

### 1. Evidence and clarity postcondition for resume advice

**Primary references:** ai-job-search and no-ai-slop.

CareerFit now applies a deterministic validation boundary after the matcher generates resume advice and before advice is persisted or returned. The implementation lives in [advice_quality.py](../backend/app/services/advice_quality.py), is integrated by [jobs.py](../backend/app/services/jobs.py), and is covered by [test_output_quality.py](../backend/tests/test_output_quality.py).

The boundary is intentionally separate from fit scoring. It can reject or repair unsafe writing, but it cannot change a score, eligibility conclusion, blocker, confidence value, or requirement classification.

The current policy:

- rejects suggested projects that are not in the verified candidate profile;
- rejects suggested skills that are not in the verified candidate profile;
- rejects evidence anchors that are not drawn from approved profile evidence;
- rejects unsupported numbers introduced by the generated summary;
- rejects empty or implausibly long summaries;
- rejects unresolved template placeholders, markup, control characters, and consecutive duplicate words;
- warns on a limited set of vague claims and formulaic phrasing;
- repairs hard failures using CareerFit-owned, evidence-limited fallbacks;
- fails closed if even the final fallback cannot satisfy the policy;
- strips private excerpts from persisted public findings;
- records policy version, template version, repair status, evidence count, warning codes, and safe findings;
- refuses to reuse a cached match unless its reader, template, and output-policy versions are current and the saved quality report passed.

The about-template set was raised to **about-v1.1.0** in [about_templates.py](../backend/app/services/about_templates.py). All T01–T24 templates received a factual-language pass: claims about experience, impact, ownership, reliability, leadership-like traits, strength, and measurable quality were replaced with narrower statements that explicitly point to verified profile evidence. Template selection also gained explicit signals for availability, internships, open source, product/platform roles, broad skill profiles, aligned senior experience, and domain transitions. Product/platform matching uses word boundaries rather than substring matching, and the no-project recommendation is one canonical evidence prompt shared by the matcher and policy boundary.

A deterministic, production-shaped reachability matrix now exercises T01 through T24. The final consolidated backend run selected every intended template, retained evidence, and passed the output policy with zero findings. The matrix pins three important distinctions:

- T04 recognizes an explicit internship/student role without misclassifying unrelated phrases such as “Internal Tools”;
- T21 requires both at least seven evidenced skills and an explicit generalist, versatile, or multidisciplinary role signal;
- T24 requires explicit career-change language from the candidate and a domain mismatch; a domain mismatch alone cannot label a person as changing careers.

The T24 stage signal is restricted to non-rejected About-me facts, uses explicit transition phrasing, and ignores negated statements. Project names such as “career transition dashboard” cannot activate it.

The API contract in [schemas.py](../backend/app/schemas.py) and [api.ts](../frontend/lib/api.ts) now exposes:

- template version;
- quality-policy version;
- whether the output was checked;
- whether it was repaired;
- safe, explainable quality findings;
- the evidence anchors behind the suggested summary.

The Opportunity Inspector in [OpportunityInspector.tsx](../frontend/components/home/OpportunityInspector.tsx) displays an evidence-check badge, repair state, evidence anchors, and clarity notes. Older saved advice is explicitly labeled as legacy and connects to the existing Refresh Match action instead of presenting unverified historical output as current.

This is a CareerFit-specific implementation. It does not embed the no-ai-slop prompt, its banned-word list, or its prose. It also does not use writing style to infer whether text was written by AI.

### 2. Append-only application event context

**Primary reference:** career-ops.

CareerFit already stored status events. The current work strengthens them into a more useful audit and analytics record:

- **previous_status** records the transition origin;
- **status** records the transition destination;
- **occurred_at** records when the business event happened;
- **source** distinguishes system, user, correction, backfill, and legacy events;
- **note** stores optional normalized context;
- **created_at** remains the database audit timestamp.

The model and API changes are in [models.py](../backend/app/models.py), [schemas.py](../backend/app/schemas.py), [routes.py](../backend/app/api/routes.py), and [jobs.py](../backend/app/services/jobs.py). The data contract is advanced to v23 by [20260731190000_application_event_context_v23.sql](../supabase/migrations/20260731190000_application_event_context_v23.sql) and the matching fresh-install snapshot in [schema.sql](../supabase/schema.sql).

Important behaviors:

- a user can supply the real occurrence date instead of losing it to the database insertion time;
- the API rejects dates more than five minutes in the future;
- notes are whitespace-normalized, limited to 500 characters, and reject unsafe control characters;
- same-status updates are true no-ops: they do not append history, change updated_at, or validate event metadata that will not be stored;
- PostgreSQL row locking protects concurrent status transitions, including reacquiring the lock after the missing-match creation path commits;
- initial status creation is attributed to the system;
- existing rows are backfilled in stable event order and labeled legacy, while new rows default to system unless the service supplies a more specific source;
- database checks restrict allowed previous states and event sources;
- the event index follows user, match, occurred time, audit time, and identifier.

Implementation review caught and fixed upgrade-only issues before release: the v18 fixture now removes newer constraints before replay, v23 changes the post-backfill source default to system, and v23 drops the obsolete created-time index before installing the occurred-time index. These fixes are why both fresh and upgraded database paths remain mandatory release gates.

The frontend now supplies an optimistic event with rollback on request failure, provides a detailed stage-change form, and renders a transition timeline with the actual event date, source, and note. Frontend types and runtime validators were updated together in [api.ts](../frontend/lib/api.ts), [api-contracts.mjs](../frontend/lib/api-contracts.mjs), and [api-contracts.test.mjs](../frontend/tests/api-contracts.test.mjs).

The implementation keeps PostgreSQL as the canonical data store. It does not adopt career-ops' Markdown files as a database.

### 3. Extraction provenance

**Primary reference:** reader, reinforced by career-ops.

The job extraction workflow now persists the reader strategy and reader version in the extraction step output. The Opportunity Inspector exposes:

- extraction strategy, such as JSON-LD, Workday structured data, focused HTML, visible page text, or pasted content;
- source title;
- reader version;
- source confidence;
- requirements completeness.

The backend integration is in [jobs.py](../backend/app/services/jobs.py); the UI is in [OpportunityInspector.tsx](../frontend/components/home/OpportunityInspector.tsx). Cached analyses create a new provenance step that explicitly says stored extraction was reused and no remote page was fetched, while carrying forward the last known extraction strategy/version where available.

This makes an important distinction visible: CareerFit's result is an interpretation of a particular source through a particular extraction path. A user or operator can now diagnose a low-quality result without assuming that the matcher itself failed.

No browser service, Puppeteer dependency, proxy support, arbitrary cookies, screenshot endpoint, or reader source code was adopted.

### 4. Source-health circuit breaker

**Primary reference:** ai-job-search, with career-ops' tri-state liveness model as a supporting concept.

Before this change, a syntactically successful source request could yield zero usable jobs, appear successful, and eventually allow old catalog rows to be deactivated. That is a dangerous failure mode when an upstream payload silently changes.

[job_discovery.py](../backend/app/services/job_discovery.py) now classifies a source run before allowing deactivation:

| Condition | Run status | Deactivate missing jobs? |
| --- | --- | --- |
| Counts are internally inconsistent | degraded | No |
| Source yields zero rows | inconclusive | No |
| Source reports rows but yields no usable jobs | degraded | No |
| At least four rows are seen and fewer than half are valid | degraded | No |
| Valid yield collapses sharply below a five-run healthy median | degraded | No |
| Current result satisfies the source contract | completed | Yes, under the existing stale-age rule |

Safe rows from a partially degraded run can still be ingested, but destructive deactivation is suppressed. The run records a stable reason code and operator-facing message, and the secured discovery-worker response exposes the reason code plus whether deactivation was suppressed. Tests in [test_goozali_discovery.py](../backend/tests/test_goozali_discovery.py) cover zero-yield preservation, invalid counts, no usable records, low valid ratio, historical yield collapse, and the positive control that a healthy run may still deactivate a stale missing job. Timestamp comparison normalizes database and test values to UTC so a healthy run cannot crash on a naive-versus-aware datetime mismatch.

The original discovery schema allowed only running, completed, failed, and disabled. An upgraded database would therefore reject the new degraded and inconclusive observations even though the application and fresh schema accepted them. [20260731200000_job_source_health_status_v24.sql](../supabase/migrations/20260731200000_job_source_health_status_v24.sql) replaces that durable status constraint, and the fresh schema plus PostgreSQL harness now assert all six values. The complete database contract for this change set is therefore **v24**: v23 adds application-event context and v24 adds durable source-health statuses.

This is a first circuit-breaker layer, not a complete provider-observability system. Follow-up work is listed later in this report.

## Repository-by-repository findings

### 1. MadsLorentzen/ai-job-search

#### What it is

ai-job-search is a local Claude Code workflow rather than a conventional hosted application. Markdown commands and skills orchestrate a candidate profile, job-source adapters, ranking, application drafting, PDF generation, and outcome tracking. Bun/TypeScript command-line tools implement portal access; Python utilities handle PDF checks, salary conversion, and repository security invariants; local files hold user state.

The central flow is setup, scrape, rank, apply, then outcome/interview. Relevant source snapshots include:

- [apply workflow](https://github.com/MadsLorentzen/ai-job-search/blob/2c41210019f4a4134fe38f87a5e17243950a9a97/.claude/commands/apply.md);
- [rank workflow](https://github.com/MadsLorentzen/ai-job-search/blob/2c41210019f4a4134fe38f87a5e17243950a9a97/.claude/commands/rank.md);
- [outcome workflow](https://github.com/MadsLorentzen/ai-job-search/blob/2c41210019f4a4134fe38f87a5e17243950a9a97/.claude/commands/outcome.md);
- [job-scraper skill](https://github.com/MadsLorentzen/ai-job-search/blob/2c41210019f4a4134fe38f87a5e17243950a9a97/.claude/skills/job-scraper/SKILL.md);
- [application writing guidance](https://github.com/MadsLorentzen/ai-job-search/blob/2c41210019f4a4134fe38f87a5e17243950a9a97/.claude/skills/job-application-assistant/03-writing-style.md);
- [security invariant checks](https://github.com/MadsLorentzen/ai-job-search/blob/2c41210019f4a4134fe38f87a5e17243950a9a97/tools/security_guards.py).

#### Strong patterns

**Treat job postings as untrusted data.** The workflow explicitly separates instructions from posting content. Portal tools fetch the user-supplied posting URL, but do not follow links embedded in the posting body. This is the correct trust boundary for AI-assisted job research.

**Ground generated material in a union of known facts.** Drafts are constrained to candidate-provided and independently verified facts. A drafter/reviewer split, PDF inspection, and ATS text checks add postconditions beyond “the model returned text.”

**Separate cheap triage from deep evaluation.** Initial ranking narrows the set before expensive research and document work. CareerFit should preserve the same principle as discovery grows.

**Close the outcome loop.** Interview, offer, and rejection outcomes are treated as feedback for future prioritization rather than terminal labels.

**Detect silent parser rot.** Source health considers expected yield and parse quality, not only HTTP success.

**Bound network behavior.** Portal clients use timeouts, retries, jitter, structured errors, and fixture tests. These are useful general standards for future CareerFit providers.

**Enforce repository invariants in CI.** The security guard checks assumptions that generic linters do not know, while Actions are pinned to immutable revisions.

#### Limitations and rejected ideas

- Much of the workflow's business logic exists in prose. CareerFit requires typed, executable, testable rules for scoring, eligibility, persistence, and authorization.
- Portal clients duplicate significant behavior and do not use a checked-in Bun lockfile.
- Parts of the PDF toolchain use mutable container/package inputs.
- The project is young and experienced a large recent development burst, so current patterns have limited long-term production evidence.
- The storage model is local and single-user; CareerFit is multi-tenant and must preserve database isolation, authorization, auditability, and retention controls.
- Personal profile/application files are easy to commit accidentally in a local-workflow repository.
- Portal automation may conflict with source terms or anti-automation controls.
- Its ranking weights are not evidence that the same weights are valid for CareerFit's users.

#### CareerFit use

Implemented now:

- evidence-and-clarity postcondition;
- versioned, factual resume-advice output;
- source-health classification and no-deactivation circuit breaker.

Prioritized next:

- use Interview, Offer, and Rejected status events in carefully bounded recommendation calibration;
- represent eligibility as pass, fail, or unverified with cited evidence;
- add CareerFit-specific security invariants and secret scanning;
- add provider contract fixtures, bounded retries, and operator-visible health history.

#### Observed verification

The checked-out repository's Python suite completed with **134 passing tests**. Bun was not available in the local review environment, so its TypeScript tests were inspected but not executed locally; the repository contains roughly 152 TypeScript test declarations and its reviewed upstream CI state was green.

Git-history review found 138 commits from 2026-03-20 through 2026-07-31. The most active and bug-associated areas overlap in the salary converter, application workflow, scraper skill, CV templates, and security guard. The recent contributor count is broad, but 122 of 138 commits landed in July, so momentum is rising and bursty rather than proven stable.

### 2. santifer/career-ops

#### What it is

career-ops is a local-first “career operating system.” Markdown is the canonical user data format; Node scripts scan, normalize, write, and analyze data; prompt modes guide workflows; a Go terminal interface and an alpha Next.js interface sit on top; provider modules normalize ATS sources.

Its architecture and data contracts are documented in:

- [ARCHITECTURE.md](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/ARCHITECTURE.md);
- [DATA_CONTRACT.md](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/DATA_CONTRACT.md#L42);
- [canonical states](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/templates/states.yml#L1-L62);
- [provider contract](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/providers/README.md).

#### Strong patterns

**Append-only status ledger.** Its event record includes tracker identity, actual event date, previous state, new state, source, and note. The writer is designed to be idempotent, locked, and atomic. See [status writer and ledger logic](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/set-status.mjs#L459-L540).

**Distinguish business time from write time.** This is essential for accurate time-to-response and time-in-stage analysis.

**Right-censored funnel statistics.** Open applications are not treated as failures merely because their eventual outcome has not arrived. The implementation also derives a follow-up backlog. See [funnel parsing and statistics](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/funnel-velocity.mjs#L88-L217).

**Provider detection and fetch contract.** Source-specific behavior sits behind a normalized interface.

**Careful normalization and provenance.** Tracking parameters are removed by allowlist, company and role names are normalized, near-duplicates use SimHash, and source provenance is retained. See the relevant [scan implementation](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/scan.mjs#L1161-L1281).

**Tri-state liveness.** A record can be live, dead, or unknown rather than forcing network uncertainty into a destructive Boolean. See [liveness-core.mjs](https://github.com/santifer/career-ops/blob/37a5184ba0bbcb590f5e17cfbf6a718db1527460/liveness-core.mjs#L116-L175).

**Actionable pipeline interface.** URL-backed opportunities, next actions, and follow-up queues are more useful than a passive list of saved jobs.

#### Limitations and rejected ideas

- Markdown is not an appropriate canonical store for CareerFit's multi-tenant product.
- Prompt files should not contain authoritative authorization, scoring, or state-transition logic.
- Shell orchestration and filesystem locks do not replace database transactions.
- Large test and scan files have become monoliths and will be costly to maintain.
- A browser-oriented local trust model does not satisfy CareerFit's hosted-service security needs.
- The root lacks a tracked lockfile even though supply-chain checks are otherwise mature.
- Dependency review is nonblocking.
- The project is young despite its high commit count; activity volume is not equivalent to production maturity.
- Its name, icons, and other marks are separately protected. CareerFit must not imitate its branding.

#### CareerFit use

Implemented now:

- richer, append-only application status context;
- separation of occurred time and audit time;
- idempotent status updates and transactional row locking;
- detailed timeline and stage-update UI;
- extraction provenance;
- tri-state-inspired source-health suppression.

Prioritized next:

- right-censored funnel analytics and follow-up backlog;
- provider protocol and registry;
- stronger URL normalization and deduplication provenance;
- operator-facing source-health history;
- explicit correction events rather than editing old history.

#### Observed verification

The repository's quick suite reported **2,705 passing checks**, one Windows symlink EPERM failure, and three warnings. Its production npm audit reported zero known vulnerabilities. CI covers multiple operating systems, CodeQL, and SBOM generation.

The scale is substantial for a roughly four-month-old project: 1,045 commits. The review therefore treats the design ideas as useful but not automatically production-proven.

### 3. surapuramakhil-org/Job_search_agent

#### What it is

Job_search_agent is a Python 3.13 command-line and Selenium application agent. On the reviewed default branch it implements Lever; its search layer provides Google, Bing, and Brave strategies/builders/factories; its LLM layer wraps an OpenAI-compatible/TensorZero interface; user data and secrets live in YAML; application data and artifacts are stored locally.

Relevant structural examples include:

- [search engine abstraction](https://github.com/surapuramakhil-org/Job_search_agent/blob/9229e64eb1696ae2eb385c56c4f93e0be6892ab3/src/services/web_search_engine.py);
- [portal base class](https://github.com/surapuramakhil-org/Job_search_agent/blob/9229e64eb1696ae2eb385c56c4f93e0be6892ab3/src/job_portals/base_job_portal.py);
- [LLM manager](https://github.com/surapuramakhil-org/Job_search_agent/blob/9229e64eb1696ae2eb385c56c4f93e0be6892ab3/src/llm/llm_manager.py);
- [application saver](https://github.com/surapuramakhil-org/Job_search_agent/blob/9229e64eb1696ae2eb385c56c4f93e0be6892ab3/src/job_application_saver.py).

#### Concepts worth retaining

- a small portal Strategy/Adapter interface;
- provider-neutral immutable query and filter values;
- a registry/factory that resolves a provider without spreading source checks across the application;
- structured Pydantic output at model boundaries;
- sanitized offline HTML fixtures for provider contract tests;
- traceable application artifacts;
- a model gateway boundary if CareerFit later has a justified generative use case.

These are common software-design concepts, not a recommendation to port this implementation.

#### Critical security, ethics, and reliability problems

**Exposed credential material.** The reviewed head and history contain an apparent live-form API credential in both a runtime secrets YAML file and a documentation example. The value, direct file links, and introducing commit are intentionally omitted from this public engineering record; the credential was not reproduced, validated, or used. The repository owner should be notified privately, revoke it, purge it from history, run a full secret scan, and review provider logs for possible misuse. History rewriting does not replace revocation.

**Fabricated application claims.** [prompts.py](https://github.com/surapuramakhil-org/Job_search_agent/blob/9229e64eb1696ae2eb385c56c4f93e0be6892ab3/src/llm/prompts.py) directs the model to infer or invent skills and years rather than return zero/unknown. This is directly incompatible with CareerFit's factual-grounding requirement.

**Automatic consent and submission.** [job_applier.py](https://github.com/surapuramakhil-org/Job_search_agent/blob/9229e64eb1696ae2eb385c56c4f93e0be6892ab3/src/job_applier.py) checks consent-like fields and submits applications without a mandatory user preview. CareerFit should never make legally or reputationally significant representations on a user's behalf without explicit, informed confirmation.

**Fail-open decisions.** Suitability and filter exceptions can allow processing to continue. High-stakes gates must fail closed or return unverified.

**Sensitive local data.** Demographics, work authorization, application answers, secrets, and documents are stored in plaintext YAML/JSON artifacts.

**Excessive diagnostics.** Detailed Loguru backtraces/diagnostics can expose sensitive application data.

**Weak network and code hygiene.** Requests lack consistent timeouts and bounded retries; a mutable default dictionary is present; the application module is a large monolith; many base methods remain unimplemented.

**Weak operational proof.** Functional Python CI is manually disabled, the README admits manual testing, and many tests are commented out. Docker/TensorZero examples use default credentials, exposed ports, and mutable image tags.

**Captured third-party assets.** Portal fixtures contain large vendor resource trees. They increase security, licensing, path-length, and maintenance risk.

#### CareerFit use

Nothing from this repository was implemented in the current change set.

The following ideas remain on the backlog for independent implementation:

1. a small CareerFit-native JobSourceProvider protocol and registry;
2. sanitized, minimal, offline provider contract fixtures;
3. an immutable provider-neutral query/filter value object;
4. consistent timeout, retry, jitter, response-size, and fail-closed parsing policies.

Automatic application submission, fabricated answers, browser form filling, plaintext profiles, and the existing LLM prompts are permanently rejected.

#### Observed verification

Python compilation succeeded. Pytest was unavailable in the local review environment, and upstream functional test CI is disabled, so there is no adequate correctness signal. The repository has 155 commits, but human ownership is effectively concentrated in one contributor and recent activity is primarily dependency automation.

### 4. petergyang/no-ai-slop

#### What it is

no-ai-slop is a Markdown editing skill with two modes:

- edit a draft using the smallest effective change while preserving the writer's voice;
- detect named writing patterns without rewriting, scoring, or claiming to identify AI authorship.

The canonical behavior lives in [SKILL.md](https://github.com/petergyang/no-ai-slop/blob/e81170dcaefa76b4cb2672532e13042f4e132b32/SKILL.md) and its same-model checklist in [eval.md](https://github.com/petergyang/no-ai-slop/blob/e81170dcaefa76b4cb2672532e13042f4e132b32/eval.md). [build_plugin.py](https://github.com/petergyang/no-ai-slop/blob/e81170dcaefa76b4cb2672532e13042f4e132b32/scripts/build_plugin.py) only packages and validates a plugin archive; there is no executable writing detector.

#### Strong patterns

- separate detection from mutation;
- make the minimum effective edit;
- preserve user intent and voice;
- never invent claims, statistics, examples, or sources;
- prefer concrete evidence over vague impact language;
- return named, explainable findings instead of a mysterious score;
- validate the packaged artifact against canonical source files.

#### Limitations and rejected ideas

- The README says “20+” patterns while the reviewed skill contains 17 named pattern headings; the mismatch is tracked in [PR #20](https://github.com/petergyang/no-ai-slop/pull/20).
- Most rules are English-specific and can create false positives in technical, multilingual, or culturally different writing.
- Blanket rules against particular words, colons, em dashes, headings, or bullets are unsuitable for resumes and structured UI content.
- A same-model self-check is not independent verification.
- It lacks an explicit prompt-injection or high-stakes candidate-decision boundary.
- Rewriting can accidentally rebind a fact to the wrong subject; this risk is discussed in [PR #24](https://github.com/petergyang/no-ai-slop/pull/24).
- It must not be used as an AI-authorship detector.
- It must not influence candidate score, eligibility, or job ranking.
- It must not silently rewrite a user's CV or application.
- Third-party personal data must not be sent to an external editor without an approved privacy basis.

#### CareerFit use

Implemented now:

- deterministic evidence-and-clarity findings;
- separate assessment and repair behavior;
- minimum, bounded repair instead of freeform rewriting;
- versioned policy metadata;
- user-visible evidence and quality state;
- targeted template claim reductions.

Remaining:

- keep the T01–T24 reachability matrix mandatory whenever templates or selection rules change;
- measure policy false positives with consented, redacted beta examples;
- keep purely stylistic warnings in shadow/advisory mode;
- preserve a mandatory user review before any suggested text leaves CareerFit.

#### Observed verification

The Linux upstream CI for the reviewed head was green. The local Windows packaging check failed because the build script compares POSIX-style expected paths with Windows backslash paths. The repository has no behavioral test suite for its editorial rules.

CareerFit's initial focused quality work passed 53 tests. A later 128-test run covered output quality, calibration, profile derivation, and job behavior; the final backend/schema audit set passed **44 tests**. The complete final backend suite then passed **338 tests**, including the T01–T24 matrix and the expanded source-health, migration, status, concurrency-sensitive, provenance, and career-transition context cases.

### 5. intergalacticalvariable/reader

#### What it is

reader is an archived Express/Firebase arbitrary-URL extraction service adapted from Jina Reader and an earlier hargup project. It combines Puppeteer, JSDOM, Mozilla Readability, and Turndown to turn web pages into text or Markdown. It has no meaningful product frontend.

Relevant concepts are visible in:

- [rendered browser extraction](https://github.com/intergalacticalvariable/reader/blob/d259179f7a6adc308f6c94e843837a1b95383e2d/backend/functions/src/services/puppeteer.ts#L501-L656);
- [Readability and selector narrowing](https://github.com/intergalacticalvariable/reader/blob/d259179f7a6adc308f6c94e843837a1b95383e2d/backend/functions/src/services/jsdom.ts#L27-L147);
- [fallback and provenance envelope](https://github.com/intergalacticalvariable/reader/blob/d259179f7a6adc308f6c94e843837a1b95383e2d/backend/functions/src/cloud-functions/crawler.ts#L329-L592).

#### Concepts worth retaining

- use static structured extraction first;
- narrow candidate content before generic page conversion;
- fall back from structured HTML to readable text/Markdown without hiding which path succeeded;
- preserve title, source URL, publication information, extraction strategy, and content;
- consider a rendered-page fallback only for sources that genuinely require JavaScript.

#### Critical problems and rejected ideas

- The repository is archived and has no useful automated test or CI safety net.
- npm install from lockfile fails because the lockfile does not match the package manifest.
- The lint command lacks a working configuration.
- The local production audit reported **50 known vulnerabilities**, including 7 critical and 21 high severity issues.
- Chromium is launched with no-sandbox and single-process-style flags.
- URL validation is incomplete for a hostile multi-hop web environment.
- Subresource blocking covers only a narrow localhost case, not the full private/link-local/metadata address space.
- User-controlled proxy, cookie, and user-agent behavior greatly expands the attack surface.
- Redirect behavior derives from the Host header.
- Screenshot path handling appears capable of unsafe path construction.
- Authentication, rate limits, concurrency limits, response-size limits, and reliable resource budgets are missing or insufficient.

The weak boundaries are visible in:

- [URL handling](https://github.com/intergalacticalvariable/reader/blob/d259179f7a6adc308f6c94e843837a1b95383e2d/backend/functions/src/cloud-functions/crawler.ts#L638-L721);
- [browser launch flags](https://github.com/intergalacticalvariable/reader/blob/d259179f7a6adc308f6c94e843837a1b95383e2d/backend/functions/src/services/puppeteer.ts#L259-L267);
- [subrequest interception](https://github.com/intergalacticalvariable/reader/blob/d259179f7a6adc308f6c94e843837a1b95383e2d/backend/functions/src/services/puppeteer.ts#L360-L420);
- [untrusted scraping controls](https://github.com/intergalacticalvariable/reader/blob/d259179f7a6adc308f6c94e843837a1b95383e2d/backend/functions/src/dto/scrapping-options.ts#L203-L291).

#### CareerFit use

Implemented now:

- extraction strategy/version persisted in workflow provenance;
- source title, confidence, and completeness shown to users.

Not adopted:

- reader source code;
- Puppeteer or its deployment model;
- its network controls;
- its proxy/cookie/screenshot features;
- its dependency tree.

A future JavaScript-rendered fallback is lower priority and must be implemented as a separate hardened worker with strict egress policy, DNS/IP pinning across redirects and subrequests, sandboxing, authentication, quotas, response-size/time limits, concurrency isolation, and no user-supplied proxy or cookie surface.

## Clean-room and license posture

### Rules applied during this review

1. Record the exact external repository and immutable reviewed head.
2. Describe the engineering problem and observable behavior, not source-code structure to reproduce line by line.
3. Design against CareerFit's existing domain model, threat model, API, database, and tests.
4. Write new CareerFit code and test cases from CareerFit invariants.
5. Do not import external repository files, prompts, fixtures, assets, or dependencies.
6. Keep external repository names and links in this design record, not in production branding or user-facing claims.
7. Reassess the license before any future direct reuse.

### Repository-specific posture

- **MIT repositories:** ai-job-search, career-ops, and no-ai-slop permit broad reuse if the copyright and license notice is preserved. No substantial source or prompt wording was reused in the current implementation. If that changes, the relevant MIT notice must travel with the reused material.
- **career-ops trademark:** the MIT code license does not grant rights to protected names or branding. CareerFit must retain its own identity.
- **reader:** the root Apache-2.0 license was treated as controlling despite a package metadata conflict. Direct reuse would require Apache license/notice handling, modified-file notices where applicable, and attention to patent terms. No reader code was reused.
- **Job_search_agent:** AGPL-3.0 code and CC BY 4.0 documentation are kept concept-only. Direct integration, modification, or network deployment could create source-disclosure and attribution obligations incompatible with the intended clean-room approach. No code, prompt prose, documentation text, or captured portal fixture was reused.

This is an engineering record, not legal advice. Any future direct reuse should receive a repository-specific legal/license review.

## Rejected directions

The following ideas should not enter CareerFit without a new, explicit architectural and risk decision:

- automatic application submission;
- automatic checking of consent, demographic, or legal representation fields;
- fabricated or inferred candidate skills, years, achievements, or eligibility answers;
- fail-open suitability or work-authorization gates;
- using writing style to infer AI authorship or candidate quality;
- silent rewriting of user application material;
- arbitrary-URL browser extraction using the reviewed reader deployment;
- user-controlled proxies, cookies, or browser identities;
- Markdown or local JSON/YAML as CareerFit's authoritative multi-tenant database;
- prompt files as the source of truth for authorization, scoring, or state transitions;
- copying AGPL implementation code into CareerFit;
- adopting another repository's score weights without CareerFit outcome evidence;
- trusting HTTP success as proof that a source parser is healthy;
- treating an unknown liveness result as permission to delete or deactivate data.

## Prioritized remaining work

### P0: required before beta deployment of this change set

1. **Local full verification — completed for the final worktree.**
   - The complete backend suite passed 338 tests.
   - The OCR worker passed 17 tests, and backend package consistency is clean.
   - The isolated PostgreSQL fresh-install and reconstructed-v18-state-to-v24 upgrade/security harness passed.
   - Frontend tests, typecheck, production build, and production dependency audit passed. These checks must remain bound to the immutable commit used for deployment.

2. **Prove migrations v23 and v24 in a beta-like database.**
   - Verify backfill order for multiple events with equal timestamps.
   - Verify application-event and source-run constraints plus index names on both fresh install and upgrade.
   - Use the documented schema-first order: v23, v24, backend, then frontend. Keep the schema-to-backend window short or pause stage writes so the old backend cannot create an event with defaulted previous-state context.
   - Capture migration identifier, database target, start/end time, row counts, and redacted output in release evidence.

3. **Exercise status-transition concurrency and time zones.**
   - Run concurrent PostgreSQL updates against the same match and confirm a coherent previous-to-next chain.
   - Exercise naive and timezone-aware API input.
   - Confirm date-only UI input resolves to the intended local business date for users outside the server timezone.

4. **Complete adversarial and beta-corpus output checks.**
   - The production-shaped T01–T24 reachability matrix already passes; keep it in the final full-suite run.
   - Confirm the policy does not incorrectly reject legitimate numbers already present in evidence.
   - Confirm repairs never bind one person's or project's fact to another subject.
   - Review consented, redacted beta examples for English-style false positives before expanding warnings.

5. **Run beta smoke tests after deployment.**
   - Analyze a pasted posting and a URL-backed posting.
   - Confirm provenance appears.
   - Confirm advice shows evidence and quality state.
   - Record Applied and Interview events with past dates and notes.
   - Confirm duplicate status updates do not duplicate history.
   - Simulate a zero-yield source run and prove existing catalog jobs remain active.

### P1: next product and reliability work

1. **Outcome-aware calibration.**
   - Connect Interview, Offer, and Rejected events to recommendation calibration.
   - Use minimum sample sizes, holdouts, and bounded adjustments.
   - Avoid treating pending applications as negative outcomes.
   - Keep eligibility vetoes outside learned calibration.
   - Show users when a recommendation was influenced by aggregate outcomes.

2. **Structured eligibility evidence.**
   - Represent work authorization, location, clearance, degree, language, and similar gates as pass, fail, or unverified.
   - Store cited evidence and extraction confidence for each conclusion.
   - Veto only explicit contradictions.
   - Ask the user when a high-impact condition remains unverified.

3. **Provider protocol and contract fixtures.**
   - Introduce a small CareerFit-owned JobSourceProvider protocol and registry.
   - Adapt Goozali behind it without changing current behavior.
   - Define immutable query/filter values.
   - Add sanitized minimal offline fixtures for each provider.
   - Standardize timeouts, retries, jitter, response-size limits, and structured error codes.

4. **Complete source health operations.**
   - Persist rolling yield/validity baselines per provider.
   - Require consecutive healthy runs before clearing a circuit.
   - Add sentinel parsing probes and fixture canaries.
   - Alert on zero yield, schema drift, low valid ratio, and yield collapse.
   - Feed the worker's degraded/inconclusive status, reason code, and suppression flag into operator alerts and a dashboard.
   - Never allow an inconclusive run to deactivate data.

5. **Right-censored funnel and follow-up analytics.**
   - Calculate time to first response, interview, offer, and rejection from occurred_at.
   - Do not classify open applications as failures.
   - Build a follow-up queue using stage age and user-configurable cadence.
   - Segment only when sample sizes protect privacy and statistical usefulness.

6. **Status correction and note governance.**
   - Add an explicit append-only correction event instead of editing history.
   - Define whether correction changes the current materialized status.
   - Add note-retention, deletion, and export rules because notes may contain recruiter names or other personal data.

### P2: useful but deliberately deferred

1. **Hardened rendered-page fallback.**
   - Add only if static JSON-LD, ATS endpoints, scoped HTML, and pasted text leave a measured coverage gap.
   - Isolate it as a resource-limited worker with strict egress and no arbitrary proxy/cookie features.

2. **URL normalization and near-duplicate evidence.**
   - Use provider-specific allowlists for tracking parameters.
   - Preserve canonical and observed URLs.
   - Add explainable company/role normalization and near-duplicate grouping.

3. **CareerFit-specific repository invariants.**
   - Scan for committed secrets.
   - Assert that public routes enforce tenant identity.
   - Assert migration/schema parity.
   - Assert network fetchers retain SSRF, redirect, timeout, and response-size guards.
   - Assert advice output cannot bypass the quality boundary.

4. **Style policy expansion in shadow mode.**
   - Collect false-positive rates before adding new warnings.
   - Keep warnings advisory and separate from ranking.
   - Support multilingual content explicitly rather than applying English heuristics globally.

5. **Model gateway only when justified.**
   - CareerFit's current deterministic scorer is safer for core matching.
   - If a generative feature is added later, define provider-neutral requests, structured output, redaction, retention, cost limits, and an auditable fallback before choosing a gateway.

## Verification record

### CareerFit current worktree

| Check | Observed result | Release status |
| --- | --- | --- |
| Focused backend reference-adaptation tests | **128 passed** for output/calibration/profile/jobs; latest backend/schema audit set **44 passed** | Passed; supplementary to the full suite |
| Frontend test suite used in this work session | **32 passed**, including same-day, historical, future, and impossible application-event date cases | Passed |
| Frontend TypeScript typecheck | Clean | Passed |
| Frontend production build | Completed successfully | Passed |
| Frontend production npm audit | **0 known production vulnerabilities** | Passed |
| Backend package consistency | pip check clean | Passed |
| Staged-diff secret scan | No findings after narrow allowlisting of the report's exact public Git commit IDs and the application-owned policy constant name | Passed |
| Complete backend suite | **338 passed in 16.92s** on the final worktree | Passed |
| OCR worker suite | **17 passed** | Passed |
| PostgreSQL fresh-install and v18-to-v24 upgrade/security harness | PostgreSQL 16 fresh schema and reconstructed v18 state followed by the v19-to-v24 forward migrations passed, including legacy-event backfill and tenant-security assertions | Passed |
| Local browser user-flow inspection | Opportunity Inspector exercised at desktop and 390×844: tabs, evidence state, provenance, timeline, and detailed stage form; no application console errors. The optimistic rollback behavior is code/contract tested rather than submitted from the fixture. Temporary QA route was removed and is absent from the production build. | Passed locally; deployed beta smoke still required |
| Beta migration application | Not performed as part of this report | **Pending** |
| Beta deployment and user smoke test | Not performed as part of this report | **Pending** |

The local unit, contract, build, browser, and real-PostgreSQL gates are green. They do not prove that beta migrations or deployments succeeded. The two pending beta rows must be closed against the final immutable commit, migration log, deployment artifacts, and deployed smoke evidence.

### External repositories

| Repository | Local/upstream observation | Interpretation |
| --- | --- | --- |
| ai-job-search | 134 Python tests passed; TypeScript suite inspected but not run locally because Bun was unavailable; reviewed upstream CI green | Strongest test posture of the five, but still young |
| career-ops | 2,705 quick checks passed; one Windows symlink EPERM and three warnings; production npm audit 0 | Broad coverage with a Windows portability issue and monolithic areas |
| Job_search_agent | Python compilation passed; pytest unavailable locally; functional CI disabled upstream | Insufficient correctness evidence |
| no-ai-slop | Linux CI green; Windows packaging failed on slash-direction comparison; no behavioral editorial suite | Packaging is checked, actual editing behavior is prompt-evaluated only |
| reader | npm lockfile install failed; no useful tests/CI; production audit found 50 vulnerabilities, including 7 critical and 21 high | Unsuitable dependency/deployment baseline |

## Release handoff checklist

Before this work is called deployed:

- [x] final diff reviewed for unintended files and secret material;
- [x] full backend, frontend, OCR, and PostgreSQL checks passed;
- [ ] migrations v23 and v24 applied to beta in order with recorded evidence;
- [ ] backend and frontend deployed from the same immutable Git commit;
- [ ] health/readiness and scheduler checks passed;
- [ ] user smoke tests completed for advice quality, provenance, timeline, and source circuit breaker;
- [ ] rollback owner, trigger, and target deployment recorded;
- [ ] final commit SHA, frontend deployment ID, backend deployment ID, and migration evidence added to the release record.

## Final recommendation

Continue with the four bounded adaptations already implemented. They improve correctness and explainability without changing CareerFit into an autonomous application bot or importing another project's architecture.

The next highest-value work is a beta migration/deployment rehearsal, outcome-aware calibration, structured eligibility evidence, and a small provider contract with fixture-based health tests. Browser rendering and model gateways should remain deferred until measured product gaps justify their security and operational cost.
