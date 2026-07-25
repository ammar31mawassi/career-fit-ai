# Recommendation Feedback and Calibration Tasks

### T-1: Add feedback and calibration persistence
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2, US-3
- **Description**: Add recommendation events, job linkage, field calibration models, constraints, indexes, cascade behavior, and RLS.
- **Acceptance**: SQLite metadata and the PostgreSQL migration represent the idempotency, ownership, and aggregation rules.
- **Dependencies**: none

### T-2: Record recommendation funnel events
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2
- **Description**: Record views, saves, applications, and reasoned dismissals through authenticated services and APIs.
- **Acceptance**: Retries do not duplicate events, foreign recommendations are rejected, and application events require an explicit Applied status.
- **Dependencies**: T-1

### T-3: Add dismissal and view interactions
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2
- **Description**: Add an accessible dismissal-reason panel and non-blocking view tracking to recommendation cards.
- **Acceptance**: Cancel preserves the card, successful reason submission removes it, and external navigation remains responsive.
- **Dependencies**: T-2

### T-4: Calibrate field thresholds
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-3
- **Description**: Recompute conservative rolling field thresholds after terminal feedback and apply them during scoring.
- **Acceptance**: Sparse data stays at 40; sufficient poor feedback raises only the affected field to 50 or 65.
- **Dependencies**: T-1, T-2

### T-5: Verify the feature
- **Status**: completed
- **Wired**: n/a
- **Verified**: yes
- **Requirements**: US-1, US-2, US-3
- **Description**: Add service/API/UI tests and run backend, type, lint, and production-build checks.
- **Acceptance**: Focused and broad checks pass, including idempotency and calibration boundaries.
- **Dependencies**: T-1, T-2, T-3, T-4
