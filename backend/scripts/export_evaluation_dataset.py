"""Export privacy-safe labeled feature examples as JSONL.

Run from backend/: python scripts/export_evaluation_dataset.py --output evaluation.jsonl
The export deliberately excludes user IDs, CV text, evidence excerpts, URLs, and job descriptions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlmodel import Session, select

from app.database import engine
from app.models import EvaluationExample


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--type", default="")
    arguments = parser.parse_args()
    statement = select(EvaluationExample).order_by(EvaluationExample.created_at)
    if arguments.type:
        statement = statement.where(EvaluationExample.example_type == arguments.type)
    with Session(engine) as session:
        rows = list(session.exec(statement).all())
    output = Path(arguments.output)
    lines = [
        json.dumps(
            {
                "example_type": row.example_type,
                "split": row.split,
                "label": row.label,
                "features": _json_dict(row.features_json),
                "model_version": row.model_version,
            },
            sort_keys=True,
        )
        for row in rows
    ]
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"Exported {len(lines)} privacy-safe examples to {output}.")


def _json_dict(value: str) -> dict[str, object]:
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


if __name__ == "__main__":
    main()
