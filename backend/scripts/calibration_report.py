"""Report calibration without adding a model dependency.

Input is JSONL containing a numeric `score` (0-100) and binary `label` (0/1).
This script is intentionally training-free: it tells us whether collected outcomes
are sufficient and whether the deterministic score is calibrated before a small
monotonic model is considered.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--bins", type=int, default=10)
    arguments = parser.parse_args()
    examples = [json.loads(line) for line in Path(arguments.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    pairs = [(max(0.0, min(1.0, float(item["score"]) / 100)), int(item["label"])) for item in examples]
    if not pairs:
        raise SystemExit("No labeled examples found.")
    brier = sum((probability - label) ** 2 for probability, label in pairs) / len(pairs)
    bins = max(2, arguments.bins)
    expected_calibration_error = 0.0
    report = []
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        members = [(probability, label) for probability, label in pairs if lower <= probability < upper or (index == bins - 1 and probability == 1)]
        if not members:
            continue
        confidence = sum(probability for probability, _ in members) / len(members)
        outcome_rate = sum(label for _, label in members) / len(members)
        expected_calibration_error += len(members) / len(pairs) * abs(confidence - outcome_rate)
        report.append({"range": f"{lower:.1f}-{upper:.1f}", "count": len(members), "mean_score": round(confidence, 3), "outcome_rate": round(outcome_rate, 3)})
    print(json.dumps({"examples": len(pairs), "brier_score": round(brier, 4), "expected_calibration_error": round(expected_calibration_error, 4), "bins": report}, indent=2))


if __name__ == "__main__":
    main()
