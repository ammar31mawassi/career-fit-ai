from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable

from ..models import EvaluationExample


DEFAULT_MINIMUMS = {"train": 50, "validation": 20, "test": 20}


def build_label_coverage(
    rows: Iterable[EvaluationExample],
    minimums: dict[str, int] | None = None,
) -> dict[str, object]:
    """Summarize privacy-safe label coverage and identify sparse training gates."""
    required = {**DEFAULT_MINIMUMS, **(minimums or {})}
    examples = list(rows)
    by_split = Counter(row.split for row in examples)
    by_type = Counter(row.example_type for row in examples)
    by_label = Counter(row.label for row in examples)
    by_model_version = Counter(row.model_version or "unknown" for row in examples)
    fact_types: Counter[str] = Counter()
    evidence_types: Counter[str] = Counter()
    corrected_fields: Counter[str] = Counter()

    for row in examples:
        features = _json_dict(row.features_json)
        _increment_string(fact_types, features.get("fact_type"))
        _increment_string(evidence_types, features.get("evidence_type"))
        changed_fields = features.get("changed_fields")
        if isinstance(changed_fields, list):
            for field in changed_fields:
                _increment_string(corrected_fields, field)

    sparse_splits = {
        split: {"count": by_split[split], "minimum": minimum}
        for split, minimum in required.items()
        if by_split[split] < minimum
    }
    warnings = [
        f"{split} has {values['count']} labels; minimum is {values['minimum']}."
        for split, values in sparse_splits.items()
    ]
    if len(by_type) < 2:
        warnings.append("Fewer than two label types are represented.")

    return {
        "total_examples": len(examples),
        "training_gate_passed": not warnings,
        "warnings": warnings,
        "minimums": required,
        "by_split": _sorted_counts(by_split),
        "by_example_type": _sorted_counts(by_type),
        "by_label": _sorted_counts(by_label),
        "by_model_version": _sorted_counts(by_model_version),
        "segments": {
            "fact_type": _sorted_counts(fact_types),
            "evidence_type": _sorted_counts(evidence_types),
            "corrected_requirement_field": _sorted_counts(corrected_fields),
        },
    }


def _json_dict(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _increment_string(counter: Counter[str], value: object) -> None:
    if isinstance(value, str) and value.strip():
        counter[value.strip()] += 1


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))
