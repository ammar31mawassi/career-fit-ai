# Recommended scoring and training policy

## What the score should mean

Career Fit's percentage should mean **evidence-backed qualification fit for the stated posting**, not the probability of being interviewed or hired. Hiring outcomes also reflect competition, timing, referrals, labor-market conditions, and human bias. Mixing those into the user-facing fit score would make it less explainable and less fair.

## Requirement priority

Use the posting as the primary source of truth:

1. Explicit hard constraints: work authorization, mandatory license/certification, on-site location, and truly mandatory education.
2. Explicit must-have skills and required alternatives (for example, Python **or** Java).
3. Minimum professional experience and seniority, interpreted in context rather than by the largest number in the page.
4. Responsibilities and domain experience.
5. Preferred skills.
6. Nice-to-have skills.

O*NET or ESCO may fill gaps in a vague posting, but an ontology-inferred requirement must never create a hard blocker. A practical blend is 70% posting evidence and at most 30% occupation prior for non-blocking requirement importance.

Within an O*NET occupation, a starting prior for a skill can use normalized importance and level:

```text
occupation_skill_prior = 0.65 * importance + 0.25 * level + 0.10 * in_demand_software
```

This is a prior to validate, not a calibrated production coefficient.

## CV evidence importance

| Evidence | Suggested evidence strength | Treatment |
|---|---:|---|
| Recent work/project evidence with action, scope, and outcome | 0.85-1.00 | Strongest evidence |
| Repeated use across work and projects | 0.75-0.90 | Strong evidence |
| Internship, coursework project, or relevant certification | 0.55-0.75 | Valid but context-dependent |
| Skill listed only in a skills section | 0.40-0.55 | Recognize, but do not claim demonstrated mastery |
| Summary/objective/“seeking a role” statement | 0.00-0.20 | Preference, not competency evidence |
| Name, age, gender, nationality, religion, marital status, photo, address, school prestige | 0.00 | Never score |

Recency should reduce confidence gradually, not erase durable foundational skills. Years should be counted from confirmed professional timelines; overlapping roles must not be double-counted, and internships should remain separate unless the posting explicitly accepts them.

## Current component weights

The existing deterministic defaults are a defensible starting point:

| Component | Current weight |
|---|---:|
| Must-have skills | 30 |
| Relevant evidence | 25 |
| Experience/seniority | 20 |
| Responsibilities/domain | 10 |
| Preferred/nice skills | 5 |
| Education/language | 5 |
| Logistics | 5 |

Keep hard blockers and caps deterministic. Do not change these weights from unlabeled Djinni, Kaggle, O*NET, or synthetic data. Use those sources to improve features; learn calibration only from independent judgments on complete CV/job pairs.

## Training sequence

1. **Reader evaluation:** Use Djinni and JobResQA to measure skill, experience, education, responsibility, alternative-requirement, and evidence extraction.
2. **Ontology expansion:** Mine recurring Djinni terms and map them to O*NET/ESCO concepts. Human-review every alias and transfer edge before release.
3. **Ranking evaluation:** Use the small human-ranked set only as a smoke test. Report nDCG/MRR and annotator agreement; do not fit production weights to it.
4. **Fairness evaluation:** Run counterfactual tests with school names and other protected proxies masked. The qualification score should remain stable when only a protected signal changes.
5. **Calibration labels:** Collect independent 0-100 qualification judgments or ordered relevance labels from trained reviewers using the same rubric. Store two reviewers for a subset to measure agreement.
6. **Calibration model:** Fit only a monotonic calibration layer over the deterministic score. Never allow it to raise a capped or blocked result.

## Minimum evaluation design

- Bare minimum gate: 50 train, 20 validation, 20 test examples, matching the current code's safety gate.
- Useful initial target: at least 1,000 reviewed pairs across career stages and job families, with no candidate/job leakage across splits.
- Hold out entire job families and a later time period to test generalization.
- Deduplicate near-identical jobs and CVs before splitting.
- Report calibration error, Brier score, rank metrics, blocker precision/recall, extraction field accuracy, and fairness counterfactual shift separately.
- Never use GPT-generated scores as the sole target. Synthetic pairs are valuable for edge cases and parser tests, not for claiming real-world score accuracy.
