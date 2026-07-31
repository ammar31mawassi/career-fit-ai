from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from .job_research import JobRequirements
from .matcher import MatchResult, score_match
from .profile import CandidateSnapshot
from ..config import get_settings


logger = logging.getLogger("careerfit.scoring")


class MatchScorer(Protocol):
    """Stable boundary for deterministic or future trained ranking models."""

    def score(
        self,
        candidate: CandidateSnapshot,
        company: str,
        role: str,
        requirements: JobRequirements,
        source_confidence: float,
    ) -> MatchResult: ...


class DeterministicMatchScorer:
    def score(
        self,
        candidate: CandidateSnapshot,
        company: str,
        role: str,
        requirements: JobRequirements,
        source_confidence: float,
    ) -> MatchResult:
        return score_match(candidate, company, role, requirements, source_confidence)


class PiecewiseCalibratedScorer:
    """Optional monotonic calibration over the deterministic, evidence-backed score.

    Eligibility caps and blockers stay deterministic: calibration may never raise a
    capped or blocked score. This lets us add a small learned component later without
    turning the percentage into an opaque language-model opinion.
    """

    def __init__(self, base: MatchScorer, knots: list[tuple[float, float]], version: str):
        if len(knots) < 2 or any(knots[index][0] >= knots[index + 1][0] for index in range(len(knots) - 1)):
            raise ValueError("Calibration knots must have strictly increasing input scores.")
        if any(knots[index][1] > knots[index + 1][1] for index in range(len(knots) - 1)):
            raise ValueError("Calibration outputs must be monotonic.")
        self.base = base
        self.knots = knots
        self.version = version

    def score(
        self,
        candidate: CandidateSnapshot,
        company: str,
        role: str,
        requirements: JobRequirements,
        source_confidence: float,
    ) -> MatchResult:
        result = self.base.score(candidate, company, role, requirements, source_confidence)
        calibrated = _interpolate(result.score, self.knots)
        if result.missing_blockers or result.applied_caps:
            calibrated = min(calibrated, result.score)
        calibrated = round(max(0.0, min(100.0, calibrated)), 1)
        snapshot = dict(result.feature_snapshot)
        snapshot.update({"pre_calibration_score": result.score, "calibration_version": self.version})
        return replace(
            result,
            score=calibrated,
            fit_level="Strong" if calibrated >= 75 else "Medium" if calibrated >= 50 else "Weak",
            model_version=f"{result.model_version}+{self.version}",
            feature_snapshot=snapshot,
        )


@lru_cache(maxsize=1)
def get_match_scorer() -> MatchScorer:
    base = DeterministicMatchScorer()
    path = get_settings().score_calibration_path
    if path is None:
        logger.info("score_calibration status=disabled scorer=deterministic")
        return base
    try:
        artifact = Path(path).read_bytes()
        payload = json.loads(artifact.decode("utf-8"))
        knots = [(float(item[0]), float(item[1])) for item in payload["knots"]]
        version = str(payload.get("version") or "calibrated-v1")
        scorer = PiecewiseCalibratedScorer(base, knots, version)
        logger.info(
            "score_calibration status=loaded version=%s sha256=%s knots=%s",
            version,
            hashlib.sha256(artifact).hexdigest(),
            len(knots),
        )
        return scorer
    except (OSError, UnicodeDecodeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        # A bad optional artifact must not take the deterministic scorer offline.
        logger.exception(
            "score_calibration status=invalid path=%s scorer=deterministic",
            path,
        )
        return base


def _interpolate(score: float, knots: list[tuple[float, float]]) -> float:
    if score <= knots[0][0]:
        return knots[0][1]
    if score >= knots[-1][0]:
        return knots[-1][1]
    for (left_x, left_y), (right_x, right_y) in zip(knots, knots[1:], strict=True):
        if left_x <= score <= right_x:
            ratio = (score - left_x) / (right_x - left_x)
            return left_y + ratio * (right_y - left_y)
    return score
