# Job Reader v2 Tasks

### T-1: Implement structured source extraction
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1
- **Acceptance**: URL-only Google and Workday fixtures produce a title and meaningful description; empty content fails.
- **Dependencies**: none

### T-2: Implement typed requirement groups
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-2
- **Acceptance**: alternatives form one-of groups; common experience phrases and title seniority parse correctly.
- **Dependencies**: T-1

### T-3: Adjust deterministic matcher
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-3
- **Acceptance**: one satisfied language alternative produces no false blockers; actual experience and iOS gaps remain.
- **Dependencies**: T-2

### T-4: Wire versioned rescanning
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-4
- **Acceptance**: failed/stale jobs update in place; current successful jobs are reused.
- **Dependencies**: T-1, T-2, T-3

### T-5: Add regression and live verification
- **Status**: completed
- **Wired**: n/a
- **Verified**: yes
- **Requirements**: US-1, US-2, US-3, US-4
- **Acceptance**: full test suite, production build, Goozali sample, and permanent QA account checks pass.
- **Dependencies**: T-4

### T-6: Deploy Reader v2
- **Status**: completed
- **Wired**: yes
- **Verified**: yes
- **Requirements**: US-1, US-2, US-3, US-4
- **Acceptance**: production aliases are healthy and the live website replaces the prior failed Google scan with a v2 result.
- **Dependencies**: T-5
