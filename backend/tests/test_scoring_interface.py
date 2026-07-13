from types import SimpleNamespace

from app.services.matcher import MatchResult
from app.services.scoring import DeterministicMatchScorer, PiecewiseCalibratedScorer, get_match_scorer


def test_default_scorer_is_replaceable_behind_interface():
    scorer = get_match_scorer()

    assert isinstance(scorer, DeterministicMatchScorer)
    assert callable(scorer.score)


class _BaseScorer:
    def __init__(self, *, blocker: bool = False):
        self.blocker = blocker

    def score(self, *_args, **_kwargs):
        return MatchResult(
            score=60,
            fit_level="Medium",
            confidence=.8,
            matched_evidence=[],
            missing_blockers=["missing"] if self.blocker else [],
            gaps=[],
            projects=[],
            skill_order=[],
            about_text="",
            about_template_id="",
            about_evidence=[],
            model_version="fit-test",
            ontology_version="skills-test",
            component_scores={},
            applied_caps=["cap"] if self.blocker else [],
            feature_snapshot={},
        )


def test_piecewise_calibration_is_monotonic_and_never_raises_blocked_score():
    calibrator = PiecewiseCalibratedScorer(_BaseScorer(), [(0, 0), (50, 55), (100, 100)], "cal-v1")
    blocked = PiecewiseCalibratedScorer(_BaseScorer(blocker=True), [(0, 0), (50, 55), (100, 100)], "cal-v1")

    result = calibrator.score(SimpleNamespace(), "", "", SimpleNamespace(), 1)
    blocked_result = blocked.score(SimpleNamespace(), "", "", SimpleNamespace(), 1)

    assert result.score == 64
    assert result.model_version.endswith("+cal-v1")
    assert blocked_result.score == 60
