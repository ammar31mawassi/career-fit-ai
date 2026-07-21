# Dataset assessment for job-fit scoring

Assessment date: 2026-07-16

## Decision summary

| Source | Decision | Value for Career Fit | Main limitation |
|---|---|---|---|
| [Job Market Dataset (Global)](https://www.kaggle.com/datasets/kundanbedmutha/job-market-dataset-global) | Do not train scoring | Market/salary analytics only | 500,000 synthetic demographic rows; no CV, job text, pair, or fit label |
| [Djinni Recruitment Dataset paper](https://aclanthology.org/2024.unlp-1.2/) and [data](https://huggingface.co/datasets/lang-uk/recruitment-dataset-job-descriptions-english) | Use now for parsing and coverage | Best supplied source: large, real recruitment text; jobs and anonymized profiles | Jobs and CVs are separate and unlabeled; cannot calibrate match percentages |
| [Resume and Job Description](https://www.kaggle.com/datasets/sayyedfaizan95/resume-and-job-description) | Reject | None beyond toy parser checks | Synthetic, unknown license, contains name/age/gender, generic target statements, no actual pair label |
| [Kaggle job search](https://www.kaggle.com/search?q=job+dataset) | Not a dataset | Discovery only | Quality, licenses, schemas, and labels vary by result |
| [Ravindra Job Description Dataset](https://www.kaggle.com/datasets/ravindrasinghrana/job-description-dataset) | Optional stress test | Broad schema and 1.6M job-like records | Synthetic, 1.74 GB, redundant with higher-quality Djinni text; not score ground truth |
| [AI Job Replacement and Skill Shift](https://www.kaggle.com/datasets/dmahajanbe23/ai-job-replacement-and-skill-shift-dataset) | Exclude from fit score | Separate career-trend feature at most | Synthetic macro forecasts do not measure whether one person meets one job's requirements |
| [O*NET 30.3](https://www.onetcenter.org/database.html) | Use now | Authoritative occupation-specific importance/level ratings, tasks, education, experience, and in-demand software | U.S.-centric; occupation mapping must be confidence-gated |
| [ESCO 1.2.1](https://esco.ec.europa.eu/en/use-esco/download) | Add next | Multilingual occupation/skill aliases and essential/optional relations, including Arabic and Ukrainian | Official customized download requires privacy acceptance and an email; not downloaded automatically |
| [Human-ranked vacancy/resume data](https://github.com/NataliaVanetik/vacancy-resume-matching-dataset) | Evaluation only | Actual human rankings and HR instructions | Only 5 jobs and 30 ranked CVs; at least two ranking arrays contain duplicate ranks; GPL-3.0 |
| [JobResQA](https://github.com/Avature/jobresqa-benchmark) | Use for reader evaluation | Human-in-the-loop QA answers and explanations across CV/JD documents | Synthetic and intended for reading comprehension, not numeric fit calibration |
| [Resume-job fairness evaluation](https://huggingface.co/datasets/renhehuang/resume-job-fairness-eval) | Use for fairness audit | Counterfactual school-prestige sensitivity checks | No relevance ground truth; synthetic and only one protected-attribute proxy |
| [Resume Seven Class](https://huggingface.co/datasets/ganchengguang/resume_seven_class) | Use for reader training | 78,670 sentence-level CV labels across experience, education, skills, summary, objective, qualifications/certifications, and personal information | Labels are noisy and derived from an older résumé corpus; useful for section vocabulary, not score labels |
| [SkillSpan](https://github.com/kris927b/SkillSpan) | Use now | Expert hard-skill and soft-skill spans from de-identified English job postings; 11,543 released sentences locally | Does not label must-have versus preferred priority and contains many long, job-specific phrases |
| [Web Data Commons JobPosting](https://webdatacommons.org/structureddata/schemaorg/) | Schema and future stress-test source | Current Common Crawl JSON-LD/Microdata `JobPosting` records across many sites | Class subset is web-scale; sample deliberately rather than downloading the full corpus |
| [SWDE job vertical](https://academictorrents.com/details/411576c7e80787e4b40452360f5f24acba9b5159) | Do not download yet | 20,000 cached job pages with title, company, location, and posting-date labels | Old pages and no clear dataset license in the surviving distribution |
| [PJB](https://arxiv.org/abs/2603.17386) | Monitor, cannot use | Strong diagnostic design: 297 jobs, 197,674 CVs, 2,242 positive judgments | Paper says release is internal-research-only; labels are mostly LLM judgments with partial manual checks |

## What the local audit found

The reusable audit sampled 300 Djinni jobs and 300 Djinni profiles across the Parquet row groups and ran the project's current rules.

- Job skill coverage is already strong: 95.7% of sampled jobs produced at least one known skill, averaging 6.64 known skills.
- Role/category coverage is weak: only 29.6% of distinct sampled `Primary Keyword` values mapped to the current ontology. Missing coverage includes PHP, Ruby, Unity, DevOps, sysadmin, support, product, sales, marketing, HR, and recruiter families.
- Experience extraction needs calibration: exact agreement with Djinni's coarse experience field was 38.7%; agreement within one year was 58.3%.
- CV-format coverage is the biggest gap: 60.3% of sampled profiles produced a known skill, but only 7.7% produced an experience fact, 1.7% a project, 0.3% education, and 0.7% language. Djinni profiles are not conventional chronological CVs, so these numbers measure format mismatch as well as parser weakness.
- No sampled profile contained an email pattern. A broad phone-like regex matched 5.7%, but years, dates, and other numeric strings can create false positives; every derived CV corpus still needs a dedicated PII pass.

These results point to ontology expansion, profile-section parsing, and experience normalization as the highest-return uses of the downloaded data. They do not justify changing the production score weights by themselves.

## License notes

- Djinni data cards and paper identify the dataset as MIT; the preprocessing repository code is Apache-2.0.
- O*NET 30.3 data is CC BY 4.0 and requires USDOL/ETA attribution.
- JobResQA is CC BY-SA 2.0.
- The human-ranked repository is GPL-3.0.
- The fairness dataset is MIT.
- Resume Seven Class is Apache-2.0 according to its Hugging Face dataset card.
- SkillSpan code/data distribution is MIT and the released subsets are de-identified according to its maintainers.
- The supplied 1,200-row resume dataset reports an unknown license and was not selected for `datasets/raw/`.

## Reader training result (2026-07-16)

The first offline reader-training pass has been promoted to production rules as `cv-sections-v1.0.0`, `experience-v1.0.0`, `profile-rules-v1.4.0`, and `skills-v1.3.0`.

- Conservative section recognition now covers 32.0% of heading-like rows in Resume Seven Class, with 88.8% agreement among recognized headings. The lower recall is intentional: generic subsection labels such as “description” and administrative fields are not treated as top-level sections.
- On 65 real DOCX CVs, 64.6% now produce normalized professional experience from explicit claims or non-overlapping employment timelines. Only aggregate metrics are retained.
- On the fixed 300-profile Djinni audit, known-skill coverage increased from 60.3% to 70.0%, and mean recognized skills increased from 2.35 to 2.71.
- On the fixed 300-job Djinni audit, jobs with a recognized skill increased from 95.7% to 97.3%; sampled primary-keyword coverage increased from 29.6% to 66.7%.
- Numeric scoring weights were not changed. These datasets still do not contain enough trustworthy job-CV fit judgments to calibrate a percentage score.

## Coverage and website-reader pass (2026-07-16)

The second pass promoted `skills-v1.4.0` and `reader-v2.3.0`.

- Fixed 300-CV skill recall reached 93.0%, exceeding the 80% target. Mean recognized skills increased from 2.71 to 4.39, mainly through QA/testing and 2D/3D art vocabularies that were common in the previously missed partition.
- Fixed 300-job primary-keyword coverage reached 92.6%; full Djinni distinct-category coverage reached 95.6%, exceeding the 75% target. Only `Lead` and `Other` remain intentionally unmapped.
- Exact-only job-category aliases map labels such as `HR`, `Support`, `Data Analyst`, and `Product Owner` without extracting ordinary prose such as “we support the team” as a candidate skill.
- SkillSpan adds 11,543 job-posting sentences and 9,617 annotated skill/knowledge spans to the offline evaluation. Current weighted span coverage is 27.7%; its long tail is retained as an evaluation source rather than copied wholesale into the ontology.
- The JSON-LD website reader now combines separate Schema.org fields and selects the strongest `JobPosting` object when a page embeds multiple records.
