"""Print aggregate onboarding conversion without user IDs or CV-derived content.

Run from backend/: python scripts/onboarding_funnel_report.py --days 30
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.database import engine
from app.models import ExtractionMetric
from app.services.onboarding_funnel import build_onboarding_funnel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    arguments = parser.parse_args()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, arguments.days))
    with Session(engine) as session:
        metrics = list(
            session.exec(
                select(ExtractionMetric).where(
                    ExtractionMetric.workflow_type == "onboarding_funnel",
                    ExtractionMetric.created_at >= cutoff,
                )
            ).all()
        )
    report = {
        "window_days": max(1, arguments.days),
        **build_onboarding_funnel(metrics),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
