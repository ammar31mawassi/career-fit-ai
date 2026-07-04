# No-OpenAI Fit Model — Requirements

## Objective

Replace all OpenAI-dependent profile and job analysis with an explainable, evidence-based system that runs in the existing FastAPI backend. The result must be useful before training data exists and capable of evolving into a trained model after enough consented outcome data is collected.

The displayed match percentage means **evidence alignment with the posting**, not probability of receiving an interview or offer.

## User stories

### US-1: Analyze without a paid AI provider

**As a** beta user  
**I want** my CV and job description analyzed without an OpenAI key  
**So that** matching has no per-request AI cost or external LLM dependency

#### Acceptance criteria

1. WHEN a user analyzes a profile or job without an OpenAI key  
   THE SYSTEM SHALL complete the analysis using only application-owned code and locally packaged data.
2. WHEN the application is deployed  
   THE SYSTEM SHALL NOT send CV, LinkedIn, GitHub, or job text to an external generative-AI provider.
3. WHEN extraction confidence is low  
   THE SYSTEM SHALL ask for clarification rather than inventing a fact.

### US-2: Receive a defensible match result

**As a** job seeker  
**I want** experience and must-have requirements to materially affect my score  
**So that** superficial keyword overlap cannot produce a misleading high match

#### Acceptance criteria

1. WHEN a posting requires professional experience and the profile has zero confirmed professional experience  
   THE SYSTEM SHALL apply a major penalty and a score cap.
2. WHEN a candidate is missing an explicit must-have requirement  
   THE SYSTEM SHALL penalize it more than a preferred or nice-to-have requirement.
3. WHEN a skill is supported by professional or project evidence  
   THE SYSTEM SHALL score it higher than an unsupported self-report.
4. WHEN candidate evidence is old or irrelevant to the role  
   THE SYSTEM SHALL reduce its contribution.
5. WHEN a result is returned  
   THE SYSTEM SHALL return score components, blockers, gaps, matched evidence, model version, and a separate confidence value.

### US-3: Generate an evidence-backed About section

**As a** job seeker  
**I want** an About section tailored to my career stage and target role  
**So that** I can improve my resume without fabricated claims

#### Acceptance criteria

1. WHEN an About section is requested  
   THE SYSTEM SHALL select one of the approved templates using candidate stage, role family, strongest evidence type, and job emphasis.
2. WHEN a placeholder cannot be filled from approved evidence  
   THE SYSTEM SHALL remove its optional clause or choose another template.
3. WHEN skills are inserted  
   THE SYSTEM SHALL use three to five relevant, evidence-backed skills in job-priority order.
4. WHEN text is rendered  
   THE SYSTEM SHALL contain no unresolved placeholders and no unsupported metrics, years, titles, or soft-skill claims.
5. WHEN the candidate is a student  
   THE SYSTEM SHALL support education status, semesters remaining, availability, and project-led evidence without presenting it as professional experience.

### US-4: Improve the model using outcomes

**As a** product owner  
**I want** application outcomes captured separately from fit analysis  
**So that** a statistically trained model can be evaluated later

#### Acceptance criteria

1. WHEN a user records progress  
   THE SYSTEM SHALL support Lead, Applied, Interview, Rejected, Withdrawn, and Offer stages with timestamps.
2. WHEN outcome data is stored  
   THE SYSTEM SHALL preserve the feature snapshot and model version used for the original match.
3. WHEN insufficient labeled data exists  
   THE SYSTEM SHALL continue using the versioned deterministic model and SHALL NOT describe it as statistically trained.
4. WHEN training is introduced  
   THE SYSTEM SHALL evaluate calibration, false-high-match rate, and subgroup behavior before activation.

### US-5: Protect users from misleading or discriminatory scoring

**As a** beta user  
**I want** the score based on job-relevant evidence  
**So that** irrelevant personal attributes do not affect the result

#### Acceptance criteria

1. WHEN a profile contains age, gender, name, photograph, ethnicity, religion, marital status, disability, or similar protected information  
   THE SYSTEM SHALL exclude it from scoring and template selection.
2. WHEN GitHub is supplied  
   THE SYSTEM SHALL use relevant project evidence but SHALL NOT treat commit frequency, account age, follower count, or star count as general candidate quality.
3. WHEN school information is supplied  
   THE SYSTEM SHALL use degree subject/status where relevant but SHALL NOT score school prestige.
4. WHEN match confidence is low  
   THE SYSTEM SHALL communicate uncertainty and request missing information.

## Non-functional requirements

- A normal profile or job analysis should complete within 3 seconds after a serverless cold start has completed.
- Runtime must not require a GPU.
- Matching must be deterministic for the same profile, job snapshot, ontology version, and model version.
- Every nonzero feature contribution must be traceable to candidate and job evidence.
- Template rendering must escape or normalize user-provided text before display.
- Existing saved matches must retain their original score and version after model upgrades.

## Out of scope for this phase

- Predicting the probability of an interview or offer.
- Training a neural network or hosting a large language model.
- Generating arbitrary prose from a generative model.
- LinkedIn scraping.
- Automatic applications.
- Pooling user outcome data for training without explicit consent.

