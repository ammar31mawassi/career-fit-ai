# Goozali Discovery Beta Requirements

## US-1: Discover new Israel-market jobs

**As a** CareerFit beta operator
**I want** a bounded hourly import from Goozali's public job table
**So that** newly posted roles can enter the existing recommendation pipeline without manual scans.

1. WHEN the discovery worker runs with Goozali enabled
   THE SYSTEM SHALL fetch the public table once, ignore contact fields, and ingest only valid new or changed job records.
2. WHEN a Goozali record has already been seen
   THE SYSTEM SHALL update the existing catalog entry instead of creating a duplicate.
3. WHEN the public-table contract changes, returns an oversized payload, or becomes unavailable
   THE SYSTEM SHALL fail the source run safely without changing existing recommendations.
4. WHEN an initial import runs
   THE SYSTEM SHALL enforce a recent lookback and a configurable per-run limit so it does not enqueue the historic table.

## US-2: Restrict the beta cohort

**As a** product owner
**I want** Goozali discovery limited to explicitly enrolled test accounts
**So that** CareerFit does not infer citizenship or expose an unfinished feature broadly.

1. WHEN a Goozali job is matched
   THE SYSTEM SHALL shortlist only ready, opted-in profiles that are active members of the IL beta cohort.
2. WHEN a person's name or location resembles an Israeli identity
   THE SYSTEM SHALL NOT infer eligibility from that information.
3. WHEN a non-member uses existing community recommendations
   THE SYSTEM SHALL preserve the current community recommendation behavior.

## US-3: Suggest useful matches

**As an** enrolled candidate
**I want** useful new jobs to appear in CareerFit
**So that** I can review, dismiss, open, or save them.

1. WHEN an enrolled candidate scores at least 65 with sufficient confidence and no deterministic blocker
   THE SYSTEM SHALL make the Goozali role available in the existing recommendation rail.
2. WHEN a score is below the suggestion threshold
   THE SYSTEM SHALL retain it only as a private shadow observation.
3. WHEN the candidate has already saved the job
   THE SYSTEM SHALL NOT recommend it again.

## US-4: Send consented high-confidence email alerts

**As an** enrolled candidate
**I want** an optional email for high-confidence new matches
**So that** I can react without constantly opening CareerFit.

1. WHEN an eligible candidate explicitly enables email alerts and a new Goozali recommendation scores at least 76 with high confidence and no blocker
   THE SYSTEM SHALL enqueue one email delivery.
2. WHEN the same recommendation is processed repeatedly
   THE SYSTEM SHALL NOT send more than one email.
3. WHEN email delivery is not configured or fails
   THE SYSTEM SHALL retain a retryable delivery record without exposing profile evidence or secrets.
4. WHEN the candidate unsubscribes
   THE SYSTEM SHALL disable future email alerts while preserving in-app recommendations.

## Non-functional requirements

- THE SYSTEM SHALL keep deterministic scoring, blockers, confidence, and model versioning authoritative.
- THE SYSTEM SHALL not ingest Goozali contact names, email addresses, phone numbers, or LinkedIn profiles.
- THE SYSTEM SHALL bound network response sizes, use timeouts, and provide a source kill switch.
- THE SYSTEM SHALL make queue processing idempotent and safe under overlapping scheduled runs.
- THE SYSTEM SHALL not place raw CV evidence or raw job descriptions in email delivery logs.

## Out of scope

- Applying to jobs or contacting recruiters.
- Scraping employer career sites.
- Inferring citizenship, religion, ethnicity, or nationality.
- Daily or weekly digest batching in the first beta.
- Broad rollout beyond explicitly configured test accounts.
