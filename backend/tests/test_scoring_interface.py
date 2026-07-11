from app.services.scoring import DeterministicMatchScorer, get_match_scorer


def test_default_scorer_is_replaceable_behind_interface():
    scorer = get_match_scorer()

    assert isinstance(scorer, DeterministicMatchScorer)
    assert callable(scorer.score)
