# Job Reader v2 Design

## Architecture

URL → safety validation → provider adapter / JSON-LD → scoped HTML fallback → quality gate → typed requirements → evidence matcher → versioned persistence

## Components

### Job source reader

- Recognizes Workday and common structured job metadata.
- Extracts JSON-LD JobPosting before visible text.
- Uses main/article content and excludes navigation for HTML fallback.
- Returns extraction method, diagnostics, title, company, location, text, and confidence.

### Requirement classifier

- Keeps compatibility lists for existing API consumers.
- Adds typed RequirementGroup records with all-of or one-of semantics.
- Tracks whether an experience minimum was actually found.
- Uses role title plus scoped text for seniority.

### Matcher v2.1

- Scores all-of requirements independently.
- Scores one-of groups by their strongest supported alternative.
- Emits one group blocker when no alternative is supported.
- Calibrates confidence using extraction completeness.

### Persistence

- Stores reader_version inside requirements JSON for backward compatibility.
- Reuses only current, successful scans.
- Updates failed, corrected, or stale scans in place to preserve one job per normalized URL.

## Security and performance

- Preserve public-host DNS checks on the original URL and redirects.
- ATS adapter requests use public HTTPS endpoints derived only from validated hosts.
- Responses remain capped at 2 MB.
- Provider adapters fail closed and fall back to scoped HTML.

## Alternatives considered

- Headless Chromium in Vercel: rejected for v2 because of cold starts, package size, and free-tier reliability.
- Paid LLM extraction: rejected because requirements call for deterministic, no-paid-API behavior.
