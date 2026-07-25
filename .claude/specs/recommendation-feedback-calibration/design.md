# Recommendation Feedback and Calibration Design

## Architecture

Discover card -> authenticated recommendation API -> idempotent event snapshot -> field calibration refresh -> future deterministic scoring

Saved recommendation -> tracked job -> explicit `Applied` status -> recommendation application event

## Interaction design

- Dismiss opens an inline, keyboard-accessible reason panel inside the affected card.
- The card remains visible until a reason is submitted successfully.
- Opening the external listing records `viewed` without delaying navigation.
- Save retains its current behavior and creates a `saved` event atomically.
- Application tracking reuses the existing Opportunities status control; it does not infer that opening a link means an application.

## Data model

### `recommendation_events`

- One row per user, recommendation, and event type.
- Stores `viewed`, `saved`, `applied`, or `dismissed`.
- Dismissals use a controlled reason key.
- Snapshots score, score band, primary career field, source, and model version.
- Excludes raw profile evidence, CV content, job descriptions, and free-form user text.

### `recommendation_field_calibrations`

- One row per normalized primary career field.
- Stores the active minimum score, rolling sample totals, positive/negative totals, and update time.
- Is backend-managed aggregate state and is not directly exposed to browser clients.

### `job_recommendations.materialized_job_id`

- Links a saved recommendation to the user's tracked job.
- Allows an explicit future `Applied` status to produce the correct recommendation event.

## Calibration algorithm

1. Load terminal `saved`, `applied`, and `dismissed` feedback for one field from the last 90 days.
2. Collapse rows by recommendation so each recommendation contributes once; `applied` or `saved` is positive and `dismissed` is negative.
3. If fewer than 20 unique terminal examples exist, use 40.
4. Raise to 50 only when the possible band has at least 8 examples and less than 15% positive feedback.
5. Raise to 65 only when the 50–64.99 band has at least 8 examples and less than 20% positive feedback.
6. Persist the aggregate and use it for subsequent scoring in that primary field.

This deliberately favors stability over aggressive learning. Views are measured for funnel analysis but do not train the threshold because a click does not prove relevance.

## API changes

- `PATCH /api/recommendations/{id}` accepts a controlled `dismiss_reason` when status is `dismissed`.
- `POST /api/recommendations/{id}/events` accepts `viewed`.
- Job status updates record `applied` when the job is linked to a saved recommendation.

## Security and privacy

- Event ownership is checked by the API and protected with row-level security.
- Calibration rows deny direct anonymous and authenticated client access.
- Foreign keys cascade when the source recommendation, job, or user is deleted.
- Database constraints validate event types, score bands, and dismissal reason keys.

## Alternatives considered

- Treating an outbound click as an application: rejected because it inflates conversion and trains on false positives.
- Per-user thresholds: deferred because small samples would overfit and could make discovery unpredictable.
- Recomputing all fields on every read: rejected because it adds latency to the candidate-facing feed.
- Using views as positive labels: rejected because curiosity is not evidence of suitability.
