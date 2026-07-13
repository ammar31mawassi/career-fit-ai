from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlmodel import Session, select

from ..models import JobScan, Profile
from ..schemas import JobCreateIn, JobScanOut
from .jobs import create_or_analyze_job, job_output
from .telemetry import current_trace_id, safe_error_code


QUEUE_NAME = "careerfit_job_scans"
MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(minutes=8)


class ScanCancelled(RuntimeError):
    pass


def create_job_scan(session: Session, user_id: UUID, payload: JobCreateIn) -> JobScanOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile is None or profile.status == "needs_cv":
        raise ValueError("Upload and analyze one CV before matching jobs.")
    input_hash = _payload_hash(payload)
    existing = session.exec(
        select(JobScan)
        .where(
            JobScan.user_id == user_id,
            JobScan.input_hash == input_hash,
            JobScan.status.in_(["queued", "running"]),
        )
        .order_by(JobScan.created_at.desc())
    ).first()
    if existing is not None:
        return scan_output(session, user_id, existing.id or 0)
    scan = JobScan(
        user_id=user_id,
        input_hash=input_hash,
        payload_json=payload.model_dump_json(),
        trace_id=current_trace_id() or uuid4().hex,
    )
    session.add(scan)
    session.flush()
    _enqueue_if_supported(session, scan.id or 0, user_id)
    session.commit()
    session.refresh(scan)
    return _scan_to_out(scan)


def process_user_scan(session: Session, user_id: UUID, scan_id: int) -> JobScanOut:
    scan = session.get(JobScan, scan_id)
    if scan is None or scan.user_id != user_id:
        raise ValueError("Job scan not found.")
    if scan.status != "queued":
        return scan_output(session, user_id, scan_id)
    scan.status = "running"
    scan.current_step = "validate_profile"
    scan.progress = max(scan.progress, 2)
    scan.attempts += 1
    scan.started_at = scan.started_at or _now()
    scan.updated_at = _now()
    session.add(scan)
    session.commit()
    return _run_claimed_scan(session, scan)


def cancel_job_scan(session: Session, user_id: UUID, scan_id: int) -> JobScanOut:
    scan = session.get(JobScan, scan_id)
    if scan is None or scan.user_id != user_id:
        raise ValueError("Job scan not found.")
    if scan.status == "queued":
        scan.status = "cancelled"
        scan.current_step = "cancelled"
        scan.completed_at = _now()
    elif scan.status == "running":
        scan.status = "cancel_requested"
        scan.current_step = "cancel_requested"
    scan.updated_at = _now()
    session.add(scan)
    session.commit()
    return scan_output(session, user_id, scan_id)


def scan_output(session: Session, user_id: UUID, scan_id: int) -> JobScanOut:
    scan = session.get(JobScan, scan_id)
    if scan is None or scan.user_id != user_id:
        raise ValueError("Job scan not found.")
    result = (
        job_output(session, user_id, scan.result_job_id)
        if scan.status == "succeeded" and scan.result_job_id is not None
        else None
    )
    return _scan_to_out(scan, result)


def process_one_queued_scan(session: Session) -> JobScanOut | None:
    if session.get_bind().dialect.name != "postgresql":
        scan = session.exec(
            select(JobScan)
            .where(JobScan.status.in_(["queued", "running", "cancel_requested"]))
            .order_by(JobScan.created_at)
            .limit(1)
        ).first()
        return _recover_or_process(session, scan) if scan else None
    row = session.exec(
        text("select msg_id, message from pgmq.read(:queue_name, 240, 1)").bindparams(
            queue_name=QUEUE_NAME
        )
    ).first()
    if row is None:
        return None
    message = row[1] if isinstance(row[1], dict) else json.loads(str(row[1]))
    scan_id = int(message["scan_id"])
    owner_id = UUID(str(message["user_id"]))
    scan = session.get(JobScan, scan_id)
    archive = False
    if scan is None or scan.user_id != owner_id:
        result = None
        archive = True
    else:
        result = _recover_or_process(session, scan)
        refreshed = session.get(JobScan, scan_id)
        archive = refreshed is None or refreshed.status in {"succeeded", "failed", "cancelled"}
    if archive:
        session.exec(
            text("select pgmq.archive(:queue_name, :msg_id)").bindparams(
                queue_name=QUEUE_NAME,
                msg_id=int(row[0]),
            )
        )
    session.commit()
    return result


def _recover_or_process(session: Session, scan: JobScan) -> JobScanOut | None:
    scan_id = scan.id or 0
    if scan.status == "queued":
        return process_user_scan(session, scan.user_id, scan_id)
    if scan.status == "cancel_requested":
        scan.status = "cancelled"
        scan.current_step = "cancelled"
        scan.completed_at = _now()
        scan.updated_at = _now()
        session.add(scan)
        session.commit()
        return scan_output(session, scan.user_id, scan_id)
    if scan.status == "running" and _is_stale(scan.updated_at):
        if scan.attempts >= MAX_ATTEMPTS:
            scan.status = "failed"
            scan.current_step = "failed"
            scan.error_code = "SCAN_LEASE_EXPIRED"
            scan.error_message = "The scan stopped repeatedly before it could finish. Retry the saved input."
            scan.completed_at = _now()
            scan.updated_at = _now()
            session.add(scan)
            session.commit()
            return scan_output(session, scan.user_id, scan_id)
        scan.status = "queued"
        scan.current_step = "queued_retry"
        scan.updated_at = _now()
        session.add(scan)
        session.commit()
        return process_user_scan(session, scan.user_id, scan_id)
    # Keep the PGMQ message unarchived while a healthy worker still owns it.
    return None


def _run_claimed_scan(session: Session, scan: JobScan) -> JobScanOut:
    payload = JobCreateIn.model_validate_json(scan.payload_json)

    def report(step: str, progress: int) -> None:
        current = session.get(JobScan, scan.id)
        if current is None or current.status in {"cancel_requested", "cancelled"}:
            raise ScanCancelled("Scan cancelled by the user.")
        current.current_step = step
        current.progress = max(current.progress, progress)
        current.updated_at = _now()
        session.add(current)
        session.commit()

    try:
        result = create_or_analyze_job(session, scan.user_id, payload, progress_callback=report)
        current = session.get(JobScan, scan.id)
        if current is None:
            raise RuntimeError("Persisted scan disappeared during processing.")
        current.result_job_id = result.id
        current.status = "succeeded" if result.status == "analyzed" else "failed"
        current.current_step = "ready" if result.status == "analyzed" else "failed"
        current.progress = 100
        current.error_message = result.error if result.status != "analyzed" else ""
        current.error_code = "JOB_READER_FAILED" if result.status != "analyzed" else ""
        current.completed_at = _now()
        current.updated_at = _now()
        session.add(current)
        session.commit()
        return scan_output(session, scan.user_id, scan.id or 0)
    except ScanCancelled:
        session.rollback()
        current = session.get(JobScan, scan.id)
        if current is not None:
            current.status = "cancelled"
            current.current_step = "cancelled"
            current.completed_at = _now()
            current.updated_at = _now()
            session.add(current)
            session.commit()
        return scan_output(session, scan.user_id, scan.id or 0)
    except Exception as exc:
        session.rollback()
        current = session.get(JobScan, scan.id)
        if current is not None:
            current.status = "failed"
            current.current_step = "failed"
            current.error_code = safe_error_code("SCAN", exc)
            current.error_message = "The scan could not finish. Retry it using the saved input."
            current.completed_at = _now()
            current.updated_at = _now()
            session.add(current)
            session.commit()
        return scan_output(session, scan.user_id, scan.id or 0)


def _enqueue_if_supported(session: Session, scan_id: int, user_id: UUID) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    payload = json.dumps({"scan_id": scan_id, "user_id": str(user_id)})
    session.exec(
        text("select * from pgmq.send(:queue_name, cast(:payload as jsonb))").bindparams(
            queue_name=QUEUE_NAME,
            payload=payload,
        )
    )
    session.flush()


def _payload_hash(payload: JobCreateIn) -> str:
    normalized = {
        "source_url": payload.source_url.strip().lower().rstrip("/"),
        "company": " ".join(payload.company.lower().split()),
        "role": " ".join(payload.role.lower().split()),
        "description_text": " ".join(payload.description_text.lower().split()),
    }
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode("utf-8")).hexdigest()


def _scan_to_out(scan: JobScan, result=None) -> JobScanOut:
    return JobScanOut(
        id=scan.id or 0,
        status=scan.status,  # type: ignore[arg-type]
        current_step=scan.current_step,
        progress=scan.progress,
        result_job_id=scan.result_job_id,
        trace_id=scan.trace_id,
        error_code=scan.error_code,
        error_message=scan.error_message,
        created_at=scan.created_at,
        updated_at=scan.updated_at,
        completed_at=scan.completed_at,
        result_job=result,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_stale(updated_at: datetime) -> bool:
    value = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
    return value <= _now() - STALE_AFTER
