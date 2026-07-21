# CV reader training notes

Training date: 2026-07-16

## What was trained

The production reader remains deterministic and auditable. “Training” here means learning common heading/date/skill vocabulary from licensed corpora, measuring candidate rules on held-out formats, and promoting only conservative rules backed by regression tests.

### Section recognition

`cv-sections-v1.0.0` maps common CV headings into canonical sections: summary, objective, experience, education, skills, certifications, projects, languages, awards, volunteering, publications, interests, and personal/contact information.

The aliases were derived from the 78,670-row Apache-2.0 Resume Seven Class corpus and checked against 65 real DOCX CVs. Inline headings such as `Key Skills: Python, SQL` retain their content. Prose such as `professional experience with Python` is deliberately not treated as a heading.

### Experience normalization

`experience-v1.0.0` normalizes:

- explicit claims in years or months, including written numbers;
- month-name, numeric month/year, year-only, and present/current ranges;
- overlapping or concurrent jobs by unioning calendar intervals instead of double-counting them;
- education and project date ranges as non-professional unless employment context is present.

Job requirements now also convert month-based minimums such as 18 months into 1.5 years.

### Ontology coverage

`skills-v1.3.0` adds high-frequency Djinni and O*NET-relevant families including PHP, Ruby/Rails, Laravel, Symfony, Scala, R, data analysis/engineering/science, DevOps, system administration, QA automation, Unity, Salesforce, SAP, project/product management, business analysis, support, recruitment, sales, marketing/SEO, and UI/UX design.

Broad job labels are still handled conservatively. `Other`, `Lead`, and generic `Design` are not skills, and branded O*NET software is not added merely to maximize coverage.

## Privacy and leakage controls

- Raw and derived datasets are git-ignored.
- No CV sentence, name, address, email, phone number, or document-level record is written by the training report.
- The report stores only aggregate counts, coverage rates, hashes, and high-frequency heading candidates that pass a PII filter.
- Dataset-derived rules affect extraction only; they do not create synthetic fit labels or alter score weights.

## Remaining gaps

- The section corpus is noisy and English-heavy. A manually labeled, anonymized evaluation set of 100-300 CVs across PDF/DOCX, one/two-column layouts, and local languages would be the highest-value next dataset.
- Djinni profiles are not conventional chronological CVs, so their low experience/project fact rates should not be interpreted as pure parser error.
- O*NET contains thousands of branded tools; coverage should be expanded by occupation demand and frequency, not by ingesting every product name.
- Score calibration still requires recruiter or hiring-manager judgments for real job-CV pairs, with independent train/calibration/test splits.

## Second coverage pass

`skills-v1.4.0` separates two kinds of aliases:

- extraction aliases are safe to recognize inside CV/job prose;
- exact-only category aliases normalize a complete role/category value without matching ordinary sentences.

This distinction allowed broad categories such as `Support`, `Security`, `Marketing`, and `HR` to be normalized without introducing the same words as free-text skills. QA/testing and digital-art families were added from aggregate analysis of the fixed missed-CV partition. The fixed CV audit now recognizes at least one skill in 93.0% of profiles; full distinct Djinni category coverage is 95.6%.

SkillSpan is now part of the offline training report. The released local subset contains 11,543 sentences and 9,617 expert-annotated skill/knowledge spans. Its annotations improve vocabulary discovery, but they do not supply requirement priority or candidate-fit labels.

`reader-v2.3.0` expands website reading around Schema.org `JobPosting`. It now:

- finds job records inside arrays and `@graph` containers;
- chooses the most complete posting when multiple records exist;
- merges responsibilities, qualifications, skills, experience, education, employment type, remote status, and benefits when they are separate from `description`;
- reads list-valued hiring organizations and applicant-location requirements;
- retains the existing scoped-DOM fallback for pages without usable structured data.
