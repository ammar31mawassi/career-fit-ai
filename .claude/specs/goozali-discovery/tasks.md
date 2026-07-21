# Goozali Discovery Beta Tasks

### T-1: Add source and notification persistence
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2, US-4
- **Description**: Add source identity/run, beta enrollment, preference, and delivery models plus a migration and RLS.
- **Acceptance**: SQLite metadata and PostgreSQL migration represent all entities and idempotency constraints.
- **Dependencies**: none

### T-2: Implement the bounded Goozali adapter
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1
- **Description**: Fetch and parse the public shared view while excluding contact fields and bounding initial discovery.
- **Acceptance**: Fixtures cover valid rows, missing descriptions, contract drift, response limits, and stable IDs.
- **Dependencies**: T-1

### T-3: Wire catalog ingestion and cohort matching
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2, US-3
- **Description**: Upsert external jobs, enqueue changes, restrict Goozali candidates, and expose 65+ in-app suggestions.
- **Acceptance**: Repeated syncs are idempotent; non-members receive no Goozali suggestions; existing community behavior remains unchanged.
- **Dependencies**: T-1, T-2

### T-4: Implement consented email delivery
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-4
- **Description**: Add preference APIs/UI, delivery queue, Resend adapter, Supabase email lookup, and unsubscribe endpoint.
- **Acceptance**: Only opted-in beta users produce one delivery for a 76+ match; unsubscribe disables future email.
- **Dependencies**: T-1, T-3

### T-5: Register bounded workers and operating configuration
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-4
- **Description**: Add protected discovery processing, configuration flags, examples, and Supabase Cron instructions.
- **Acceptance**: Disabled configuration performs no external fetch; enabled worker returns source/recommendation/email counters.
- **Dependencies**: T-2, T-3, T-4

### T-6: Verify and document the beta
- **Status**: completed
- **Wired**: n/a
- **Verified**: yes
- **Requirements**: US-1, US-2, US-3, US-4
- **Description**: Run backend tests, frontend checks/build, diff checks, secret scan, and document risks and rollout steps.
- **Acceptance**: Full automated verification passes and the independent-source fragility is documented.
- **Dependencies**: T-1, T-2, T-3, T-4, T-5
