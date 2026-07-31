from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, case, func, or_, text, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import JobScan, Profile
from ..schemas import JobCreateIn, JobScanOut
from .job_research import validate_pasted_job_description
from .jobs import create_or_analyze_job, job_output
from .profile import MATCHABLE_PROFILE_REQUIRED, profile_is_matchable
from .telemetry import current_trace_id, safe_error_code


QUEUE_NAME = "careerfit_job_scans"
MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(minutes=8)
ACTIVE_SCAN_STATUSES = ("queued", "running", "cancel_requested")


class ScanCancelled(RuntimeError):
    pass


def create_job_scan(session: Session, user_id: UUID, payload: JobCreateIn) -> JobScanOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if not profile_is_matchable(session, profile):
        raise ValueError(MATCHABLE_PROFILE_REQUIRED)
    if payload.description_text.strip():
        validate_pasted_job_description(payload.description_text)
    input_hash = _payload_hash(payload)
    for attempt in range(2):
        existing = _active_scan(session, user_id, input_hash)
        if existing is not None:
            return scan_output(session, user_id, existing.id or 0)
        scan = JobScan(
            user_id=user_id,
            input_hash=input_hash,
            payload_json=payload.model_dump_json(),
            trace_id=current_trace_id() or uuid4().hex,
        )
        session.add(scan)
        try:
            session.flush()
            _enqueue_if_supported(session, scan.id or 0, user_id)
            session.commit()
        except IntegrityError:
            # The partial unique index chooses one winner when concurrent
            # requests both observe no active scan.
            session.rollback()
            winner = _active_scan(session, user_id, input_hash)
            if winner is not None:
                return scan_output(session, user_id, winner.id or 0)
            if attempt:
                raise
            continue
        session.refresh(scan)
        return _scan_to_out(scan)
    raise RuntimeError("Could not persist the job scan.")


def process_user_scan(session: Session, user_id: UUID, scan_id: int) -> JobScanOut:
    session.expire_all()
    scan = session.get(JobScan, scan_id)
    if scan is None or scan.user_id != user_id:
        raise ValueError("Job scan not found.")
    if scan.status != "queued":
        return scan_output(session, user_id, scan_id)
    claimed = _claim_queued_scan(session, user_id, scan_id)
    if claimed is None:
        _fail_exhausted_queued_scan(session, user_id, scan_id)
        return scan_output(session, user_id, scan_id)
    claimed_scan, lease_token = claimed
    return _run_claimed_scan(session, claimed_scan, lease_token)


def cancel_job_scan(session: Session, user_id: UUID, scan_id: int) -> JobScanOut:
    session.expire_all()
    scan = session.get(JobScan, scan_id)
    if scan is None or scan.user_id != user_id:
        raise ValueError("Job scan not found.")
    now = _now()
    cancelled = session.execute(
        update(JobScan)
        .where(
            JobScan.id == scan_id,
            JobScan.user_id == user_id,
            JobScan.status == "queued",
        )
        .values(
            status="cancelled",
            current_step="cancelled",
            lease_token="",
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if cancelled.rowcount == 0:
        session.execute(
            update(JobScan)
            .where(
                JobScan.id == scan_id,
                JobScan.user_id == user_id,
                JobScan.status == "running",
            )
            .values(
                status="cancel_requested",
                current_step="cancel_requested",
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
    session.commit()
    return scan_output(session, user_id, scan_id)


def latest_active_scan(session: Session, user_id: UUID) -> JobScanOut | None:
    session.expire_all()
    scan = session.exec(
        select(JobScan)
        .where(
            JobScan.user_id == user_id,
            JobScan.status.in_(ACTIVE_SCAN_STATUSES),
        )
        .order_by(JobScan.created_at.desc(), JobScan.id.desc())
        .limit(1)
    ).first()
    return _scan_to_out(scan) if scan is not None else None


def scan_output(session: Session, user_id: UUID, scan_id: int) -> JobScanOut:
    session.expire_all()
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
        stale_before = _now() - STALE_AFTER
        scan = session.exec(
            select(JobScan)
            .where(
                or_(
                    JobScan.status.in_(["queued", "cancel_requested"]),
                    and_(
                        JobScan.status == "running",
                        JobScan.updated_at <= stale_before,
                    ),
                )
            )
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
    try:
        message = row[1] if isinstance(row[1], dict) else json.loads(str(row[1]))
        scan_id = int(message["scan_id"])
        owner_id = UUID(str(message["user_id"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        _archive_queue_message(session, int(row[0]))
        session.commit()
        return None
    session.expire_all()
    scan = session.get(JobScan, scan_id)
    archive = False
    if scan is None or scan.user_id != owner_id:
        result = None
        archive = True
    else:
        result = _recover_or_process(session, scan)
        session.expire_all()
        refreshed = session.get(JobScan, scan_id)
        archive = refreshed is None or refreshed.status in {"succeeded", "failed", "cancelled"}
    if archive:
        _archive_queue_message(session, int(row[0]))
    session.commit()
    return result


def _recover_or_process(session: Session, scan: JobScan) -> JobScanOut | None:
    scan_id = scan.id or 0
    if scan.status == "queued":
        return process_user_scan(session, scan.user_id, scan_id)
    if scan.status == "cancel_requested":
        if _finalize_cancel_requested(session, scan_id):
            return scan_output(session, scan.user_id, scan_id)
        return None
    if scan.status == "running" and _is_stale(scan.updated_at):
        if scan.attempts >= MAX_ATTEMPTS:
            if _expire_stale_claim(session, scan):
                return scan_output(session, scan.user_id, scan_id)
            return None
        if _release_stale_claim(session, scan):
            return process_user_scan(session, scan.user_id, scan_id)
    # Keep the PGMQ message unarchived while a healthy worker still owns it.
    return None


def _run_claimed_scan(
    session: Session,
    scan: JobScan,
    lease_token: str,
) -> JobScanOut:
    payload = JobCreateIn.model_validate_json(scan.payload_json)

    def report(step: str, progress: int) -> None:
        if not _heartbeat_claim(
            session,
            scan.id or 0,
            lease_token,
            step,
            progress,
        ):
            raise ScanCancelled("Scan cancelled by the user.")

    try:
        result = create_or_analyze_job(session, scan.user_id, payload, progress_callback=report)
        finished = _finish_claim(
            session,
            scan.id or 0,
            lease_token,
            result.id,
            result.status,
            result.error,
        )
        if not finished:
            _finalize_cancel_requested(session, scan.id or 0, lease_token)
        return scan_output(session, scan.user_id, scan.id or 0)
    except ScanCancelled:
        session.rollback()
        _finalize_cancel_requested(session, scan.id or 0, lease_token)
        return scan_output(session, scan.user_id, scan.id or 0)
    except Exception as exc:
        session.rollback()
        if not _fail_claim(session, scan.id or 0, lease_token, exc):
            _finalize_cancel_requested(session, scan.id or 0, lease_token)
        return scan_output(session, scan.user_id, scan.id or 0)


def _active_scan(session: Session, user_id: UUID, input_hash: str) -> JobScan | None:
    session.expire_all()
    return session.exec(
        select(JobScan)
        .where(
            JobScan.user_id == user_id,
            JobScan.input_hash == input_hash,
            JobScan.status.in_(ACTIVE_SCAN_STATUSES),
        )
        .order_by(JobScan.created_at.desc())
    ).first()


def _claim_queued_scan(
    session: Session,
    user_id: UUID,
    scan_id: int,
) -> tuple[JobScan, str] | None:
    now = _now()
    lease_token = uuid4().hex
    claimed = session.execute(
        update(JobScan)
        .where(
            JobScan.id == scan_id,
            JobScan.user_id == user_id,
            JobScan.status == "queued",
            JobScan.attempts < MAX_ATTEMPTS,
        )
        .values(
            status="running",
            current_step="validate_profile",
            progress=case((JobScan.progress < 2, 2), else_=JobScan.progress),
            attempts=JobScan.attempts + 1,
            lease_token=lease_token,
            started_at=func.coalesce(JobScan.started_at, now),
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    if claimed.rowcount != 1:
        return None
    session.expire_all()
    scan = session.get(JobScan, scan_id)
    if scan is None:
        return None
    return scan, lease_token


def _fail_exhausted_queued_scan(
    session: Session,
    user_id: UUID,
    scan_id: int,
) -> bool:
    now = _now()
    failed = session.execute(
        update(JobScan)
        .where(
            JobScan.id == scan_id,
            JobScan.user_id == user_id,
            JobScan.status == "queued",
            JobScan.attempts >= MAX_ATTEMPTS,
        )
        .values(
            status="failed",
            current_step="failed",
            lease_token="",
            error_code="SCAN_LEASE_EXPIRED",
            error_message=(
                "The scan stopped repeatedly before it could finish. "
                "Retry the saved input."
            ),
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return failed.rowcount == 1


def _release_stale_claim(session: Session, scan: JobScan) -> bool:
    now = _now()
    released = session.execute(
        update(JobScan)
        .where(
            JobScan.id == scan.id,
            JobScan.status == "running",
            JobScan.lease_token == scan.lease_token,
            JobScan.updated_at == scan.updated_at,
        )
        .values(
            status="queued",
            current_step="queued_retry",
            lease_token="",
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return released.rowcount == 1


def _expire_stale_claim(session: Session, scan: JobScan) -> bool:
    now = _now()
    expired = session.execute(
        update(JobScan)
        .where(
            JobScan.id == scan.id,
            JobScan.status == "running",
            JobScan.lease_token == scan.lease_token,
            JobScan.updated_at == scan.updated_at,
            JobScan.attempts >= MAX_ATTEMPTS,
        )
        .values(
            status="failed",
            current_step="failed",
            lease_token="",
            error_code="SCAN_LEASE_EXPIRED",
            error_message=(
                "The scan stopped repeatedly before it could finish. "
                "Retry the saved input."
            ),
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return expired.rowcount == 1


def _heartbeat_claim(
    session: Session,
    scan_id: int,
    lease_token: str,
    step: str,
    progress: int,
) -> bool:
    heartbeat = session.execute(
        update(JobScan)
        .where(
            JobScan.id == scan_id,
            JobScan.status == "running",
            JobScan.lease_token == lease_token,
        )
        .values(
            current_step=step,
            progress=case(
                (JobScan.progress < progress, progress),
                else_=JobScan.progress,
            ),
            updated_at=_now(),
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return heartbeat.rowcount == 1


def _finish_claim(
    session: Session,
    scan_id: int,
    lease_token: str,
    result_job_id: int | None,
    result_status: str,
    result_error: str,
) -> bool:
    analyzed = result_status == "analyzed"
    now = _now()
    finished = session.execute(
        update(JobScan)
        .where(
            JobScan.id == scan_id,
            JobScan.status == "running",
            JobScan.lease_token == lease_token,
        )
        .values(
            result_job_id=result_job_id,
            status="succeeded" if analyzed else "failed",
            current_step="ready" if analyzed else "failed",
            progress=100,
            lease_token="",
            error_message="" if analyzed else result_error,
            error_code="" if analyzed else "JOB_READER_FAILED",
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return finished.rowcount == 1


def _fail_claim(
    session: Session,
    scan_id: int,
    lease_token: str,
    error: Exception,
) -> bool:
    now = _now()
    failed = session.execute(
        update(JobScan)
        .where(
            JobScan.id == scan_id,
            JobScan.status == "running",
            JobScan.lease_token == lease_token,
        )
        .values(
            status="failed",
            current_step="failed",
            lease_token="",
            error_code=safe_error_code("SCAN", error),
            error_message="The scan could not finish. Retry it using the saved input.",
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return failed.rowcount == 1


def _finalize_cancel_requested(
    session: Session,
    scan_id: int,
    lease_token: str | None = None,
) -> bool:
    conditions = [JobScan.id == scan_id, JobScan.status == "cancel_requested"]
    if lease_token is not None:
        conditions.append(JobScan.lease_token == lease_token)
    now = _now()
    cancelled = session.execute(
        update(JobScan)
        .where(*conditions)
        .values(
            status="cancelled",
            current_step="cancelled",
            lease_token="",
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return cancelled.rowcount == 1


def _archive_queue_message(session: Session, message_id: int) -> None:
    session.exec(
        text("select pgmq.archive(:queue_name, :msg_id)").bindparams(
            queue_name=QUEUE_NAME,
            msg_id=message_id,
        )
    )


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
        # Consent is part of the request semantics. Reusing an active scan
        # created under a different choice could publish a posting after the
        # user has opted out (or suppress a contribution they opted into).
        "contribute_public_posting": payload.contribute_public_posting,
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
