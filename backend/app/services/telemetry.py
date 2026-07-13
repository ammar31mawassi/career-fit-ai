from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from uuid import UUID

from sqlmodel import Session

from ..models import EvaluationExample, ExtractionMetric


_trace_id: ContextVar[str] = ContextVar("careerfit_trace_id", default="")


def set_trace_id(value: str):
    return _trace_id.set(value)


def reset_trace_id(token) -> None:
    _trace_id.reset(token)


def current_trace_id() -> str:
    return _trace_id.get()


def evaluation_split(user_id: UUID) -> str:
    """Keep all examples from one user in the same reproducible split."""
    bucket = int(hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 75:
        return "train"
    if bucket < 90:
        return "validation"
    return "test"


def record_extraction_metric(
    session: Session,
    user_id: UUID,
    *,
    workflow_type: str,
    subject_type: str = "",
    subject_id: int | None = None,
    strategy: str = "",
    status: str = "succeeded",
    duration_ms: int = 0,
    input_length: int = 0,
    output_length: int = 0,
    fallback_reason: str = "",
    counts: dict[str, int | float | str] | None = None,
    error_code: str = "",
) -> ExtractionMetric:
    metric = ExtractionMetric(
        user_id=user_id,
        workflow_type=workflow_type[:80],
        subject_type=subject_type[:80],
        subject_id=subject_id,
        strategy=strategy[:160],
        status=status[:40],
        duration_ms=max(0, int(duration_ms)),
        input_length=max(0, int(input_length)),
        output_length=max(0, int(output_length)),
        fallback_reason=fallback_reason[:240],
        counts_json=json.dumps(counts or {}, sort_keys=True),
        error_code=error_code[:80],
        trace_id=current_trace_id()[:64],
    )
    session.add(metric)
    session.flush()
    return metric


def record_evaluation_example(
    session: Session,
    user_id: UUID,
    *,
    example_type: str,
    label: str,
    features: dict[str, object],
    subject_id: int | None = None,
    model_version: str = "",
) -> EvaluationExample:
    example = EvaluationExample(
        user_id=user_id,
        example_type=example_type[:80],
        subject_id=subject_id,
        split=evaluation_split(user_id),
        label=label[:80],
        features_json=json.dumps(features, sort_keys=True),
        model_version=model_version[:80],
        trace_id=current_trace_id()[:64],
    )
    session.add(example)
    session.flush()
    return example


def safe_error_code(prefix: str, exc: Exception) -> str:
    digest = hashlib.sha256(type(exc).__name__.encode("utf-8")).hexdigest()[:8].upper()
    return f"{prefix[:24].upper()}_{digest}"
