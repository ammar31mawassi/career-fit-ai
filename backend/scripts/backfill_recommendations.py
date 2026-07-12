from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select

from app.database import engine
from app.models import Job
from app.services.recommendations import (
    catalog_and_enqueue_job,
    generate_shadow_recommendations,
    process_one_queued_recommendation,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill the private shared-job catalog and shadow queue.")
    parser.add_argument("--max-jobs", type=int, default=500)
    parser.add_argument("--process", action="store_true", help="Process queued shadow recommendation jobs too.")
    parser.add_argument("--recompute", action="store_true", help="Recompute every cataloged job immediately.")
    parser.add_argument("--max-messages", type=int, default=500)
    args = parser.parse_args()

    cataloged = 0
    seen_hashes: set[str] = set()
    catalog_jobs: list[tuple[int, UUID]] = []
    with Session(engine) as session:
        jobs = session.exec(
            select(Job)
            .where(Job.status == "analyzed")
            .order_by(Job.updated_at.desc())
            .limit(max(1, args.max_jobs))
        ).all()
        for job in jobs:
            if job.content_hash in seen_hashes:
                continue
            seen_hashes.add(job.content_hash)
            catalog = catalog_and_enqueue_job(session, job.user_id, job)
            if catalog is not None:
                cataloged += 1
                if catalog.id is not None:
                    catalog_jobs.append((catalog.id, job.user_id))

        recomputed = 0
        if args.recompute:
            for catalog_job_id, source_user_id in catalog_jobs:
                generate_shadow_recommendations(session, catalog_job_id, source_user_id)
                recomputed += 1

        processed = 0
        if args.process:
            while processed < max(1, args.max_messages):
                if process_one_queued_recommendation(session) is None:
                    break
                processed += 1

    print(
        f"cataloged={cataloged} unique_jobs={len(seen_hashes)} "
        f"recomputed={recomputed} processed={processed}"
    )


if __name__ == "__main__":
    main()
