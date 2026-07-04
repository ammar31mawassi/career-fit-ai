# Job Reader v2 Requirements

## US-1: Read a job from its URL

**As a** candidate
**I want** CareerFit to extract a specific job from a supported public URL
**So that** I do not have to paste the posting manually.

1. WHEN a user submits a public job URL without company, role, or description
   THE SYSTEM SHALL derive job identity and requirements from structured metadata, an ATS adapter, or scoped job-page content.
2. WHEN extracted content does not contain a credible job title and meaningful posting text
   THE SYSTEM SHALL return a failed result instead of an empty or misleading match.
3. WHEN an ATS blocks static extraction
   THE SYSTEM SHALL explain that pasted text is required and record extraction diagnostics.

## US-2: Represent requirements accurately

1. WHEN a required sentence lists alternative skills with “or”, “one of”, or “e.g.”
   THE SYSTEM SHALL represent the alternatives as a one-of requirement group.
2. WHEN a posting states experience using common forms such as “1 year of experience with”
   THE SYSTEM SHALL extract the stated minimum.
3. WHEN no experience minimum is stated
   THE SYSTEM SHALL preserve “unknown” rather than claiming that zero years are required.
4. WHEN seniority is present in the title
   THE SYSTEM SHALL use the title as primary seniority evidence.

## US-3: Produce defensible match calculations

1. WHEN a candidate satisfies one option in a one-of group
   THE SYSTEM SHALL treat the group as satisfied.
2. WHEN a required one-of group has no supported option
   THE SYSTEM SHALL create one blocker for the group, not one blocker per option.
3. WHEN extraction is incomplete
   THE SYSTEM SHALL lower confidence and SHALL NOT present high-confidence conclusions from empty requirements.

## US-4: Recover from failed or stale scans

1. WHEN an existing URL scan failed and the user supplies a description
   THE SYSTEM SHALL reprocess and update the existing job.
2. WHEN an existing job was produced by an older reader version
   THE SYSTEM SHALL reprocess it when the URL is submitted again.
3. WHEN a current successful result is submitted unchanged
   THE SYSTEM SHALL reuse the stored result.

## Non-functional requirements

- THE SYSTEM SHALL retain SSRF protections and response-size limits.
- THE SYSTEM SHALL remain deterministic and require no paid model API.
- THE SYSTEM SHALL complete extraction within the existing 60-second frontend proxy limit.
- THE SYSTEM SHALL include offline regression fixtures and live Goozali-derived integration checks.

## Out of scope

- General web crawling or automatic Goozali monitoring.
- CAPTCHA bypassing, authenticated LinkedIn scraping, or paid browser-rendering services.
- Automatic job application.
