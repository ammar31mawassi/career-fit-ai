# Recommendation Feedback and Calibration Requirements

## US-1: Explain dismissals

**As a** candidate
**I want** to tell CareerFit why a suggested job is not suitable
**So that** irrelevant recommendations can be diagnosed and reduced.

1. WHEN a candidate dismisses a recommendation
   THE SYSTEM SHALL ask for one concise reason before removing the recommendation.
2. WHEN the candidate cancels the reason prompt
   THE SYSTEM SHALL leave the recommendation unchanged.
3. WHEN a dismissal is submitted
   THE SYSTEM SHALL store the reason with a privacy-safe recommendation snapshot and shall not store raw CV or job-description text.
4. WHEN an action is retried
   THE SYSTEM SHALL record at most one event of each type for that recommendation.

## US-2: Measure the recommendation funnel

**As a** CareerFit product operator
**I want** recommendation views, saves, applications, and dismissals grouped by score band
**So that** matching quality can be evaluated with behavioral evidence.

1. WHEN a candidate opens a recommended listing
   THE SYSTEM SHALL record a `viewed` event.
2. WHEN a candidate saves or dismisses a recommendation
   THE SYSTEM SHALL record the corresponding event in the same transaction as the state change.
3. WHEN a recommendation-backed tracked job first moves to `Applied`
   THE SYSTEM SHALL record an `applied` event.
4. WHEN an event is stored
   THE SYSTEM SHALL snapshot its score, score band, primary career field, source, and matcher version.
5. THE SYSTEM SHALL classify scores as `possible` from 40 through 49.99, `medium` from 50 through 74.99, and `strong` from 75 upward.

## US-3: Calibrate discovery by career field

**As a** candidate
**I want** discovery thresholds to reflect how useful recommendations are in my selected field
**So that** noisy fields become stricter without hiding useful matches everywhere.

1. WHEN a career field has fewer than 20 terminal feedback examples in the rolling 90-day window
   THE SYSTEM SHALL retain the default 40-point discovery floor.
2. WHEN a field has sufficient feedback
   THE SYSTEM SHALL derive a field threshold from unique saves, applications, and dismissals.
3. WHEN the 40–49.99 band has at least 8 examples and a positive rate below 15 percent
   THE SYSTEM SHALL raise that field's threshold to 50.
4. WHEN the 50–64.99 band has at least 8 examples and a positive rate below 20 percent
   THE SYSTEM SHALL raise that field's threshold to 65.
5. THE SYSTEM SHALL never calibrate below 40 or above 65 and shall fall back to 40 if calibration data is unavailable or invalid.
6. WHEN scoring a recommendation
   THE SYSTEM SHALL apply the threshold for the job's primary career field while preserving hard eligibility, confidence, and blocker checks.

## Non-functional requirements

- THE SYSTEM SHALL keep event creation idempotent under retries.
- THE SYSTEM SHALL enforce user ownership for recommendation events.
- THE SYSTEM SHALL index recommendation, user/time, and field/type/time access paths.
- THE SYSTEM SHALL use aggregate field feedback only after the minimum sample sizes are met.
- THE SYSTEM SHALL leave email preferences, queuing, eligibility, and delivery unchanged.

## Out of scope

- Email alerts or notification changes.
- Automated applications.
- Free-form dismissal text.
- Per-user adaptive thresholds.
- Replacing deterministic hard blockers with behavioral data.
