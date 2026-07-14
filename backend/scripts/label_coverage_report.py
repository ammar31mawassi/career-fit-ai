"""Report whether privacy-safe evaluation labels are broad enough for training.

Run from backend/: python scripts/label_coverage_report.py
The output contains aggregate counts only; it excludes user IDs and source text.
"""

from __future__ import annotations

import argparse
import json

from sqlmodel import Session, select

from app.database import engine
from app.models import EvaluationExample
from app.services.label_coverage import build_label_coverage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-train", type=int, default=50)
    parser.add_argument("--min-validation", type=int, default=20)
    parser.add_argument("--min-test", type=int, default=20)
    arguments = parser.parse_args()
    with Session(engine) as session:
        rows = list(session.exec(select(EvaluationExample)).all())
    report = build_label_coverage(
        rows,
        {
            "train": max(0, arguments.min_train),
            "validation": max(0, arguments.min_validation),
            "test": max(0, arguments.min_test),
        },
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
