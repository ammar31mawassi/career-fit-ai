# Career Fit datasets

This directory contains the local data workspace for improving Career Fit's job reader, CV reader, skill ontology, ranking evaluation, and score calibration.

Raw datasets and generated audits are intentionally excluded from git. Only reusable scripts and documentation are tracked. No downloaded dataset has been connected to production scoring automatically.

## Local inventory

| Dataset | Local content | Primary use |
|---|---:|---|
| Djinni Recruitment Dataset (English) | 141,897 jobs and 210,250 anonymized candidate profiles | Requirement/CV parsing, terminology coverage, retrieval pretraining |
| O*NET 30.3 database | 1,016 occupations plus skills, tasks, education, experience, and software tables | Occupation priors and feature importance |
| Vacancy-resume human rankings | 65 CV files, 5 jobs, only 30 CVs ranked | Small ranking smoke test only |
| JobResQA English | 581 QA examples over synthetic resume/JD pairs | Cross-document extraction and reasoning evaluation |
| Resume-job fairness evaluation | 960 synthetic pairs | Counterfactual school-prestige bias audit |
| Resume Seven Class | 78,670 labeled CV sentences | Section heading recognition and date-format coverage |
| SkillSpan | 11,543 released job-posting sentences and 9,617 expert-annotated spans | Hard/soft skill extraction and long-tail ontology evaluation |

See [DATASET_ASSESSMENT.md](DATASET_ASSESSMENT.md) for the source-by-source decision and [SCORING_POLICY.md](SCORING_POLICY.md) for the recommended training and weighting policy.

## Reproduce the privacy-safe audit

From the repository root:

```powershell
python datasets/scripts/audit_sources.py --output datasets/derived/audit.json
```

The audit prints no CV or job text. It stores only schemas, counts, hashes, aggregate parser coverage, and sampled PII-pattern rates. Reading the Parquet sources requires `pyarrow`.

To reproduce the reader-training aggregates:

```powershell
python datasets/scripts/train_reader_artifacts.py --output datasets/derived/reader_training_report.json
```

This training stage stores only counts, coverage metrics, file hashes, and high-frequency heading phrases that pass a PII filter. Production rules are promoted only after regression tests; raw CV sentences are never copied into source control.

The job website reader is also checked against the official Schema.org `JobPosting` field model. It reads JSON-LD embedded in HTML and merges separate description, responsibilities, qualifications, skills, experience, education, employment-type, remote-work, and benefits fields before classifying requirements.

## Data safety rules

- Never commit `datasets/raw/` or `datasets/derived/`.
- Treat all CV text as sensitive even when a source claims anonymization.
- Run PII scrubbing before creating training examples.
- Exclude names, age, gender, religion, marital status, nationality, photos, addresses, and school prestige from scoring features.
- Keep source licenses and attribution with every derived artifact.
- Split evaluation data by both candidate and job; do not let the same document appear in train and test.
- Do not treat synthetic or model-generated scores as human ground truth.
