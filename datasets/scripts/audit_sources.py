"""Profile local recruitment datasets without printing candidate text.

Run from the repository root with the bundled/runtime Python:

    python datasets/scripts/audit_sources.py --output datasets/derived/audit.json

Raw datasets are intentionally git-ignored. The generated audit contains only
aggregate statistics, schemas, hashes, and parser coverage measurements.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.job_research import classify_requirements  # noqa: E402
from app.services.experience_normalization import professional_experience  # noqa: E402
from app.services.ontology import canonical_skill, extract_skills  # noqa: E402
from app.services.profile_extraction import extract_profile_facts  # noqa: E402


RAW = ROOT / "datasets" / "raw"
REVIEW = ROOT / "tmp" / "datasets-review"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_identity(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def parquet_summary(path: Path) -> tuple[dict[str, object], object]:
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    metadata = parquet.metadata
    summary = file_identity(path)
    summary.update(
        {
            "rows": metadata.num_rows,
            "row_groups": metadata.num_row_groups,
            "columns": parquet.schema_arrow.names,
        }
    )
    return summary, parquet


def sampled_rows(parquet: object, columns: list[str], limit: int = 300) -> list[dict[str, object]]:
    available = [column for column in columns if column in parquet.schema_arrow.names]
    if not available:
        return []
    group_count = parquet.metadata.num_row_groups
    group_indexes = sorted({0, group_count // 2, max(0, group_count - 1)})
    per_group = max(1, limit // len(group_indexes))
    rows: list[dict[str, object]] = []
    for group_index in group_indexes:
        table = parquet.read_row_group(group_index, columns=available).slice(0, per_group)
        rows.extend(table.to_pylist())
    return rows[:limit]


def job_parser_audit(parquet: object) -> dict[str, object]:
    rows = sampled_rows(
        parquet,
        ["Position", "Long Description", "Exp Years", "Primary Keyword", "English Level"],
    )
    skill_counts: list[int] = []
    priority_counts = Counter()
    experience_errors: list[float] = []
    expected_years = {"no_exp": 0.0, "1y": 1.0, "2y": 2.0, "3y": 3.0, "5y": 5.0}
    primary_keywords = Counter()
    mapped_keywords = Counter()
    for row in rows:
        text = str(row.get("Long Description") or "")
        role = str(row.get("Position") or "")
        requirements = classify_requirements(text, role)
        skill_counts.append(len(requirements.all_skills))
        priority_counts["must"] += len(requirements.must_have_skills)
        priority_counts["preferred"] += len(requirements.preferred_skills)
        priority_counts["nice"] += len(requirements.nice_to_have_skills)
        expected = expected_years.get(str(row.get("Exp Years") or ""))
        if expected is not None:
            experience_errors.append(abs(requirements.min_years_experience - expected))
        keyword = str(row.get("Primary Keyword") or "").strip()
        if keyword:
            primary_keywords[keyword] += 1
            if canonical_skill(keyword) or extract_skills(keyword):
                mapped_keywords[keyword] += 1
    sample_count = len(rows) or 1
    return {
        "sample_rows": len(rows),
        "rows_with_any_known_skill_rate": round(sum(value > 0 for value in skill_counts) / sample_count, 4),
        "mean_known_skills_per_job": round(mean(skill_counts), 3) if skill_counts else 0.0,
        "requirements_by_priority": dict(priority_counts),
        "experience_exact_agreement_rate": round(
            sum(error == 0 for error in experience_errors) / len(experience_errors), 4
        ) if experience_errors else None,
        "experience_within_one_year_rate": round(
            sum(error <= 1 for error in experience_errors) / len(experience_errors), 4
        ) if experience_errors else None,
        "primary_keyword_ontology_coverage": round(
            len(mapped_keywords) / len(primary_keywords), 4
        ) if primary_keywords else None,
        "unmapped_primary_keywords": sorted(set(primary_keywords) - set(mapped_keywords)),
    }


def cv_parser_audit(parquet: object) -> dict[str, object]:
    rows = sampled_rows(parquet, ["CV", "Position", "Experience Years", "English Level"])
    fact_counts = Counter()
    skills_per_cv: list[int] = []
    normalized_years: list[float] = []
    email_pattern = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    phone_pattern = re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){7,15}(?!\d)")
    pii_hits = Counter()
    for row in rows:
        text = str(row.get("CV") or "")
        facts = extract_profile_facts("cv", text)
        normalized_years.append(professional_experience(text).years)
        per_type = Counter(fact.fact_type for fact in facts)
        fact_counts.update(per_type)
        skills_per_cv.append(per_type["skill"])
        pii_hits["email"] += bool(email_pattern.search(text))
        pii_hits["phone_like"] += bool(phone_pattern.search(text))
    sample_count = len(rows) or 1
    return {
        "sample_rows": len(rows),
        "rows_with_any_known_skill_rate": round(sum(value > 0 for value in skills_per_cv) / sample_count, 4),
        "mean_known_skills_per_cv": round(mean(skills_per_cv), 3) if skills_per_cv else 0.0,
        "rows_with_project_rate": round(fact_counts["project"] / sample_count, 4),
        "rows_with_experience_fact_rate": round(fact_counts["experience"] / sample_count, 4),
        "rows_with_education_fact_rate": round(fact_counts["education"] / sample_count, 4),
        "rows_with_language_fact_rate": round(fact_counts["language"] / sample_count, 4),
        "rows_with_normalized_experience_rate": round(
            sum(value > 0 for value in normalized_years) / sample_count, 4
        ),
        "sample_pii_pattern_hit_rates": {
            key: round(value / sample_count, 4) for key, value in sorted(pii_hits.items())
        },
    }


def delimited_summary(path: Path, delimiter: str = ",") -> dict[str, object]:
    result = file_identity(path)
    row_count = 0
    headers: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        headers = next(reader, [])
        for _ in reader:
            row_count += 1
    result.update({"rows": row_count, "columns": headers})
    return result


def optional_delimited_summary(path: Path, delimiter: str = ",") -> dict[str, object]:
    if not path.exists():
        return {"path": path.relative_to(ROOT).as_posix(), "retained": False}
    result = delimited_summary(path, delimiter)
    result["retained"] = True
    return result


def table_summary(path: Path) -> dict[str, object]:
    result = delimited_summary(path, delimiter="\t")
    return result


def jsonl_summary(path: Path) -> dict[str, object]:
    result = file_identity(path)
    with path.open("r", encoding="utf-8") as handle:
        result["rows"] = sum(bool(line.strip()) for line in handle)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()

    jobs_path = RAW / "djinni" / "job_descriptions_english.parquet"
    cvs_path = RAW / "djinni" / "candidate_profiles_english.parquet"
    jobs, jobs_parquet = parquet_summary(jobs_path)
    cvs, cvs_parquet = parquet_summary(cvs_path)
    jobs["current_parser"] = job_parser_audit(jobs_parquet)
    cvs["current_parser"] = cv_parser_audit(cvs_parquet)

    onet_base = RAW / "onet-30.3" / "extracted" / "db_30_3_text"
    onet_tables = {}
    for name in (
        "Occupation Data.txt",
        "Essential Skills.txt",
        "Transferable Skills.txt",
        "Software Skills.txt",
        "Education.txt",
        "Training and Experience.txt",
        "Task Statements.txt",
        "Task Ratings.txt",
        "Job Zones.txt",
    ):
        onet_tables[name] = table_summary(onet_base / name)

    human_base = RAW / "human-ranked" / "extracted" / "vacancy-resume-matching-dataset-main"
    report = {
        "djinni": {"jobs_english": jobs, "candidate_profiles_english": cvs},
        "onet_30_3": {
            "archive": file_identity(RAW / "onet-30.3" / "db_30_3_text.zip"),
            "tables": onet_tables,
        },
        "human_ranked": {
            "archive": file_identity(RAW / "human-ranked" / "vacancy-resume-matching-main.zip"),
            "cv_files": len(list((human_base / "CV").glob("*.docx"))),
            "vacancies": delimited_summary(human_base / "5_vacancies.csv"),
        },
        "jobresqa_english": delimited_summary(RAW / "jobresqa" / "jobresqa.en.tsv", delimiter="\t"),
        "fairness_eval": delimited_summary(RAW / "fairness" / "pairs_longtext.csv"),
        "resume_seven_class": parquet_summary(RAW / "resume-seven-class" / "train.parquet")[0],
        "skillspan": {
            split: jsonl_summary(
                RAW / "skillspan" / "SkillSpan-main" / "data" / "json" / f"{split}.json"
            )
            for split in ("train", "dev", "test")
        },
        "reviewed_only": {
            "kaggle_global_job_market": optional_delimited_summary(REVIEW / "global" / "job_market_dataset.csv"),
            "kaggle_resume_1200": optional_delimited_summary(REVIEW / "pair" / "resume_dataset_1200.csv"),
        },
    }
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote privacy-safe aggregate audit to {output}.")


if __name__ == "__main__":
    main()
