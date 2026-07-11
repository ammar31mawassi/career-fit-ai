from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from ..models import AgentRun, AgentStep
from ..schemas import AgentRunOut, AgentStepOut


JOB_READER_WORKFLOW_VERSION = "job-reader-agent-v1.0.0"


def start_agent_run(
    session: Session,
    user_id: UUID,
    workflow_type: str,
    *,
    input_hash: str,
    version: str,
    subject_type: str = "",
    summary: str = "",
) -> AgentRun:
    run = AgentRun(
        user_id=user_id,
        workflow_type=workflow_type,
        subject_type=subject_type,
        input_hash=input_hash,
        version=version,
        summary=summary,
        status="running",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def attach_subject(session: Session, run: AgentRun | None, subject_type: str, subject_id: int) -> None:
    if not run:
        return
    run.subject_type = subject_type
    run.subject_id = subject_id
    run.updated_at = _now()
    session.add(run)
    session.commit()


def start_step(session: Session, run: AgentRun | None, step_key: str, title: str, progress: str = "") -> AgentStep | None:
    if not run or run.id is None:
        return None
    step = AgentStep(
        user_id=run.user_id,
        run_id=run.id,
        step_key=step_key,
        title=title,
        status="running",
        progress=progress,
        started_at=_now(),
    )
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


def complete_step(
    session: Session,
    step: AgentStep | None,
    progress: str = "",
    output: dict[str, object] | None = None,
) -> None:
    if not step:
        return
    step.status = "completed"
    if progress:
        step.progress = progress
    step.output_json = _json(output or {})
    step.completed_at = _now()
    session.add(step)
    session.commit()


def fail_step(session: Session, step: AgentStep | None, error: str, output: dict[str, object] | None = None) -> None:
    if not step:
        return
    step.status = "failed"
    step.error = error[:500]
    step.output_json = _json(output or {})
    step.completed_at = _now()
    session.add(step)
    session.commit()


def complete_run(session: Session, run: AgentRun | None, summary: str = "", status: str = "completed") -> None:
    if not run:
        return
    run.status = status
    if summary:
        run.summary = summary
    run.updated_at = _now()
    run.completed_at = _now()
    session.add(run)
    session.commit()


def fail_run(session: Session, run: AgentRun | None, error: str, summary: str = "") -> None:
    if not run:
        return
    run.status = "failed"
    run.error = error[:500]
    if summary:
        run.summary = summary
    run.updated_at = _now()
    run.completed_at = _now()
    session.add(run)
    session.commit()


def latest_agent_run_for_subject(
    session: Session,
    user_id: UUID,
    workflow_type: str,
    subject_type: str,
    subject_id: int,
) -> AgentRunOut | None:
    run = session.exec(
        select(AgentRun)
        .where(
            AgentRun.user_id == user_id,
            AgentRun.workflow_type == workflow_type,
            AgentRun.subject_type == subject_type,
            AgentRun.subject_id == subject_id,
        )
        .order_by(AgentRun.id.desc())
    ).first()
    if not run or run.id is None:
        return None
    steps = list(
        session.exec(
            select(AgentStep)
            .where(AgentStep.user_id == user_id, AgentStep.run_id == run.id)
            .order_by(AgentStep.id)
        ).all()
    )
    return _run_to_out(run, steps)


def _run_to_out(run: AgentRun, steps: list[AgentStep]) -> AgentRunOut:
    return AgentRunOut(
        id=run.id or 0,
        workflow_type=run.workflow_type,
        subject_type=run.subject_type,
        subject_id=run.subject_id,
        status=run.status,
        version=run.version,
        summary=run.summary,
        error=run.error,
        created_at=run.created_at,
        completed_at=run.completed_at,
        steps=[
            AgentStepOut(
                id=step.id or 0,
                step_key=step.step_key,
                title=step.title,
                status=step.status,
                attempt=step.attempt,
                progress=step.progress,
                output=_load_dict(step.output_json),
                error=step.error,
                started_at=step.started_at,
                completed_at=step.completed_at,
            )
            for step in steps
        ],
    )


def _json(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _load_dict(value: str) -> dict[str, object]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _now() -> datetime:
    return datetime.now(timezone.utc)
