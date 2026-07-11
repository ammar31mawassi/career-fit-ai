from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from .job_research import JobRequirements
from .matcher import MatchResult, score_match
from .profile import CandidateSnapshot


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


@lru_cache(maxsize=1)
def get_match_scorer() -> MatchScorer:
    return DeterministicMatchScorer()
