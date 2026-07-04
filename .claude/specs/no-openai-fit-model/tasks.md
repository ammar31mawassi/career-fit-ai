# No-OpenAI Fit Model — Implementation Plan

## Phase 1 — Remove external AI dependency

### T-1: Remove OpenAI runtime paths

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1
- **Description**: Remove the OpenAI package, configuration, extraction calls, and obsolete environment variables. Preserve deterministic fallback behavior as the only behavior.
- **Acceptance**: Profile and job analysis tests pass with no OpenAI package or key installed.
- **Dependencies**: none

### T-2: Add versioned skill ontology

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2
- **Description**: Add canonical skills, aliases, related-skill links, domains, and ontology versioning. Begin with the role families supported by the template catalog.
- **Acceptance**: Tests cover exact, alias, boundary-safe, and partial-transfer matching without false matches such as `C` inside unrelated words.
- **Dependencies**: T-1

## Phase 2 — Evidence extraction

### T-3: Build structured candidate evidence extractor

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2, US-5
- **Description**: Extract skills, projects, education status, semesters remaining, professional/internship duration, domain, location, languages, availability, and evidence context. Keep professional years separate from academic/project time.
- **Acceptance**: Fixture CVs produce reviewed facts with evidence sentences and confidence; ambiguous facts create questions.
- **Dependencies**: T-2

### T-4: Build structured job requirement extractor

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2
- **Description**: Parse sections and classify requirements by category, priority, confidence, and source sentence.
- **Acceptance**: Fixture postings correctly distinguish must-have, preferred, responsibility-inferred, experience, education, location, and availability requirements.
- **Dependencies**: T-2

## Phase 3 — Scoring and explanations

### T-5: Implement feature builder and evidence strength

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-2, US-5
- **Description**: Calculate exact/alias/transfer matches, evidence strength, project relevance, recency, domain/responsibility alignment, and logistics compatibility.
- **Acceptance**: Every contribution has candidate and job evidence IDs and protected attributes never enter the feature set.
- **Dependencies**: T-3, T-4

### T-6: Implement match model v2 and eligibility caps

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-2
- **Description**: Replace the base-score heuristic with the documented earned-point model, hard caps, separate confidence, and versioned explanation payload.
- **Acceptance**: Zero-experience and must-have blocker tests enforce caps; preferred skills cannot compensate for hard blockers; identical inputs are deterministic.
- **Dependencies**: T-5

### T-7: Store model snapshots

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-2, US-4
- **Description**: Persist model version, ontology version, feature snapshot, component scores, caps, and explanations with each match.
- **Acceptance**: Previously stored matches remain reproducible and are not silently rescored after a model release.
- **Dependencies**: T-6

## Phase 4 — About templates and resume advice

### T-8: Implement typed placeholder renderer

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-3, US-5
- **Description**: Implement the documented placeholders, optional clauses, normalization, evidence checks, word limits, and unresolved-token validation.
- **Acceptance**: Renderer never emits an unresolved token or a claim without evidence; malformed user text is safely normalized.
- **Dependencies**: T-3

### T-9: Add and select the 24-template catalog

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-3
- **Description**: Store templates as versioned data and select by career stage, role family, strongest evidence, job emphasis, desired length, and tone.
- **Acceptance**: Reviewed fixtures choose appropriate student, embedded, backend, project-led, and experienced templates with deterministic tie-breaking.
- **Dependencies**: T-8

### T-10: Integrate template output with resume advice

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-3
- **Description**: Return About text, template ID, selected evidence, project recommendations, and skill ordering in existing job-match responses and UI.
- **Acceptance**: The Home page displays complete evidence-backed advice and handles missing optional data cleanly.
- **Dependencies**: T-9, T-6

## Phase 5 — Feedback and calibration

### T-11: Expand application outcome tracking

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-4
- **Description**: Add Interview, Rejected, Withdrawn, and Offer events with timestamps while retaining Lead and Applied.
- **Acceptance**: Outcomes are user-owned under RLS and linked to the original feature/model snapshot.
- **Dependencies**: T-7

### T-12: Build a reviewed calibration set

- **Status**: in_progress
- **Wired**: n/a
- **Verified**: no
- **Requirements**: US-2, US-5
- **Description**: Create anonymized fixtures covering student, junior, experienced, blocker, transferable-skill, and low-confidence cases. Assign expected ranges and explanations through human review.
- **Acceptance**: At least 40 profile/job pairs cover all eligibility caps and major role families before beta launch.
- **Dependencies**: T-6
- **Current state**: 40 automated baseline cases are implemented and passing; human review of expected score ranges remains required before beta launch.

### T-13: Add regression and fairness checks

- **Status**: completed
- **Wired**: n/a
- **Verified**: yes
- **Requirements**: US-2, US-5
- **Description**: Test score monotonicity, false-high-match cases, protected-field exclusion, deterministic output, and template evidence safety.
- **Acceptance**: CI fails on score-cap violations, unexpected score drift, protected-field influence, or unsupported template claims.
- **Dependencies**: T-9, T-12

## Phase 6 — Beta deployment

### T-14: Verify Supabase and production configuration

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-4, US-5
- **Description**: Validate real Supabase connectivity, migrations, private Storage, RLS, Auth, and secret-key handling without exposing values.
- **Acceptance**: A beta account can upload a CV, analyze a profile, save a match, and retrieve only its own data.
- **Dependencies**: T-7, T-10, T-11
- **Result**: Transaction-pooler connectivity, v2 migration, eight RLS-enabled tables, eight owner policies, seven critical indexes, private Storage, disabled public signup, and production Auth were verified.

### T-15: Deploy and run beta smoke tests

- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2, US-3
- **Description**: Deploy frontend and backend, configure domains/environment, and test the complete invite-to-match flow.
- **Acceptance**: Production smoke test passes without an OpenAI key and logs contain no CV or secret material.
- **Dependencies**: T-13, T-14
- **Result**: Frontend and FastAPI production aliases are live. Signup, login, CV upload, profile analysis, v2 job match, About template selection, status history, saved-job search, mobile login layout, console output, production logs, and test-data cleanup passed.
