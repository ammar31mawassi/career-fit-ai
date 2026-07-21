"""Derive privacy-safe CV reader metrics and vocabulary candidates.

This is deliberately an offline, aggregate-only training stage. It learns
which heading phrases and technology families are common, but never writes CV
sentences, names, contact details, or document-level records to its output.

Run from the repository root:

    python datasets/scripts/train_reader_artifacts.py \
        --output datasets/derived/reader_training_report.json
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


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.cv_sections import SECTION_MODEL_VERSION, section_heading  # noqa: E402
from app.services.experience_normalization import (  # noqa: E402
    EXPERIENCE_NORMALIZER_VERSION,
    professional_experience,
)
from app.services.ontology import ONTOLOGY_VERSION, canonical_skill, extract_skills  # noqa: E402


RAW = ROOT / "datasets" / "raw"
LABEL_TO_SECTIONS = {
    "Exp": {"experience", "projects"},
    "Edu": {"education"},
    "Sum": {"summary", "awards"},
    "Skill": {"skills"},
    "Obj": {"objective"},
    "QC": {"certifications"},
    "PI": {"personal", "languages", "interests"},
}
SAFE_CANDIDATE_LABELS = {"Exp", "Edu", "Sum", "Skill", "Obj", "QC"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resume_section_metrics(path: Path) -> dict[str, object]:
    import pyarrow.parquet as pq

    values = pq.read_table(path, columns=["text"])["text"].to_pylist()
    labels = Counter()
    candidates = Counter()
    recognized = Counter()
    correct = Counter()
    unrecognized = Counter()
    date_shapes = Counter()

    for raw in values:
        label, separator, value = str(raw).partition("\t")
        if not separator:
            continue
        labels[label] += 1
        line = " ".join(value.split()).strip()
        if label == "Exp":
            if re.search(r"\b(?:19|20)\d{2}\s*[-\u2013\u2014]\s*(?:present|(?:19|20)\d{2})\b", line, re.I):
                date_shapes["year_range"] += 1
            if re.search(
                r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z.]*\s+(?:19|20)\d{2}",
                line,
                re.I,
            ):
                date_shapes["named_month"] += 1
            if re.search(r"\b(?:0?[1-9]|1[0-2])[/.](?:19|20)\d{2}\b", line):
                date_shapes["numeric_month"] += 1

        if not _heading_candidate(line):
            continue
        candidates[label] += 1
        section, _ = section_heading(line)
        if section:
            recognized[label] += 1
            if section in LABEL_TO_SECTIONS.get(label, set()):
                correct[label] += 1
            continue
        normalized = _safe_heading_phrase(line)
        if label in SAFE_CANDIDATE_LABELS and normalized:
            unrecognized[(label, normalized)] += 1

    total_candidates = sum(candidates.values())
    total_recognized = sum(recognized.values())
    return {
        "source": {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "rows": len(values),
            "license": "Apache-2.0",
        },
        "label_counts": dict(sorted(labels.items())),
        "heading_candidate_counts": dict(sorted(candidates.items())),
        "heading_recognition_rate": round(total_recognized / total_candidates, 4) if total_candidates else 0.0,
        "recognized_heading_precision": round(
            sum(correct.values()) / total_recognized, 4
        ) if total_recognized else 0.0,
        "correct_recognized_by_label": dict(sorted(correct.items())),
        "experience_date_shape_counts": dict(sorted(date_shapes.items())),
        "high_frequency_unrecognized_heading_candidates": [
            {"label": label, "phrase": phrase, "count": count}
            for (label, phrase), count in unrecognized.most_common(40)
            if count >= 10
        ],
    }


def ontology_metrics() -> dict[str, object]:
    import pyarrow.parquet as pq

    djinni_path = RAW / "djinni" / "job_descriptions_english.parquet"
    keywords = [
        str(value).strip()
        for value in pq.read_table(djinni_path, columns=["Primary Keyword"])["Primary Keyword"].to_pylist()
        if value and str(value).strip()
    ]
    counts = Counter(keywords)
    mapped = {value for value in counts if canonical_skill(value) or extract_skills(value)}

    onet_path = RAW / "onet-30.3" / "extracted" / "db_30_3_text" / "Software Skills.txt"
    onet_examples: set[str] = set()
    with onet_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            value = (row.get("Workplace Example") or "").strip()
            if value:
                onet_examples.add(value)
    onet_mapped = {value for value in onet_examples if canonical_skill(value) or extract_skills(value)}

    return {
        "djinni_primary_keyword": {
            "rows": len(keywords),
            "distinct": len(counts),
            "weighted_coverage": round(sum(counts[value] for value in mapped) / len(keywords), 4),
            "distinct_coverage": round(len(mapped) / len(counts), 4),
            "unmapped": sorted(set(counts) - mapped),
        },
        "onet_software_examples": {
            "distinct": len(onet_examples),
            "distinct_exact_or_alias_coverage": round(len(onet_mapped) / len(onet_examples), 4),
        },
    }


def human_docx_metrics() -> dict[str, object]:
    from docx import Document

    base = RAW / "human-ranked" / "extracted" / "vacancy-resume-matching-dataset-main" / "CV"
    section_counts = Counter()
    documents_with_sections = 0
    documents_with_experience = 0
    paragraph_counts: list[int] = []
    table_counts: list[int] = []
    for path in sorted(base.glob("*.docx")):
        document = Document(path)
        lines = [" ".join(paragraph.text.split()) for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    value = " ".join(cell.text.split())
                    if value:
                        lines.append(value)
        seen: set[str] = set()
        for line in lines:
            section, _ = section_heading(line)
            if section:
                section_counts[section] += 1
                seen.add(section)
        documents_with_sections += bool(seen)
        documents_with_experience += professional_experience("\n".join(lines)).years > 0
        paragraph_counts.append(len(document.paragraphs))
        table_counts.append(len(document.tables))
    count = len(paragraph_counts)
    return {
        "documents": count,
        "documents_with_recognized_section_rate": round(documents_with_sections / count, 4) if count else 0.0,
        "documents_with_normalized_experience_rate": round(documents_with_experience / count, 4) if count else 0.0,
        "recognized_section_counts": dict(sorted(section_counts.items())),
        "mean_paragraphs": round(sum(paragraph_counts) / count, 2) if count else 0.0,
        "documents_with_tables": sum(value > 0 for value in table_counts),
        "privacy": "aggregate-only; DOCX text is not retained",
    }


def skillspan_metrics() -> dict[str, object]:
    base = RAW / "skillspan" / "SkillSpan-main"
    span_counts = Counter()
    kind_counts = Counter()
    mapped_occurrences = 0
    sentence_count = 0
    source_counts = Counter()
    files: list[dict[str, object]] = []
    for path in sorted((base / "data" / "json").glob("*.json")):
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                record = json.loads(raw)
                sentence_count += 1
                source_counts[str(record.get("source") or "unknown")] += 1
                tokens = [str(token) for token in record.get("tokens") or []]
                for kind, key in (("skill", "tags_skill"), ("knowledge", "tags_knowledge")):
                    for value in _bio_spans(tokens, list(record.get(key) or [])):
                        normalized = re.sub(r"\s+([,.;:/)])", r"\1", value.lower())
                        normalized = re.sub(r"([(])\s+", r"\1", normalized)
                        normalized = re.sub(r"\s+", " ", normalized).strip()
                        if not normalized:
                            continue
                        span_counts[normalized] += 1
                        kind_counts[kind] += 1
                        if canonical_skill(normalized) or extract_skills(normalized):
                            mapped_occurrences += 1
    total_spans = sum(span_counts.values())
    safe_unmapped = [
        {"phrase": phrase, "count": count}
        for phrase, count in span_counts.most_common()
        if count >= 5
        and len(phrase.split()) <= 5
        and not re.search(r"<|>|@|https?://|\d{3,}", phrase)
        and not (canonical_skill(phrase) or extract_skills(phrase))
    ][:40]
    return {
        "license": "MIT",
        "sentences": sentence_count,
        "annotated_spans": total_spans,
        "unique_annotated_spans": len(span_counts),
        "span_counts_by_type": dict(sorted(kind_counts.items())),
        "source_sentence_counts": dict(sorted(source_counts.items())),
        "ontology_weighted_span_coverage": round(mapped_occurrences / total_spans, 4) if total_spans else 0.0,
        "frequent_unmapped_span_candidates": safe_unmapped,
        "files": files,
        "privacy": "aggregate-only; job-posting sentences are not retained",
    }


def _bio_spans(tokens: list[str], tags: list[str]) -> list[str]:
    output: list[str] = []
    current: list[str] = []
    for token, tag in zip(tokens, tags):
        if tag == "B":
            if current:
                output.append(" ".join(current))
            current = [token]
        elif tag == "I" and current:
            current.append(token)
        else:
            if current:
                output.append(" ".join(current))
                current = []
    if current:
        output.append(" ".join(current))
    return output


def _heading_candidate(value: str) -> bool:
    if not value or len(value) > 80 or len(value.split()) > 8:
        return False
    letters = [character for character in value if character.isalpha()]
    mostly_upper = bool(letters) and sum(character.isupper() for character in letters) / len(letters) >= 0.75
    return value.endswith(":") or mostly_upper


def _safe_heading_phrase(value: str) -> str:
    # Only alphabetic, short aggregates are retained. This excludes names,
    # dates, phone numbers, emails, addresses, and document-specific text.
    if re.search(r"\d|@|https?://|www\.", value, re.I):
        return ""
    normalized = re.sub(r"[^a-z ]", " ", value.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized or len(normalized.split()) > 6:
        return ""
    blocked = {"name", "address", "email", "phone", "date of birth", "dob", "place"}
    return "" if normalized in blocked else normalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()

    report = {
        "artifact_versions": {
            "section_model": SECTION_MODEL_VERSION,
            "experience_normalizer": EXPERIENCE_NORMALIZER_VERSION,
            "ontology": ONTOLOGY_VERSION,
        },
        "resume_sections": resume_section_metrics(RAW / "resume-seven-class" / "train.parquet"),
        "human_docx": human_docx_metrics(),
        "skillspan_job_postings": skillspan_metrics(),
        "ontology": ontology_metrics(),
        "privacy": "aggregate-only; no CV or job sentences retained",
    }
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote privacy-safe reader training report to {output}.")


if __name__ == "__main__":
    main()
