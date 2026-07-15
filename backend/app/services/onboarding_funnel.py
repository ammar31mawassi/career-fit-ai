from __future__ import annotations

from collections import defaultdict

from ..models import ExtractionMetric


def build_onboarding_funnel(metrics: list[ExtractionMetric]) -> dict[str, object]:
    """Aggregate onboarding stages by profile without returning profile or user identifiers."""
    profiles_by_event: dict[str, set[int]] = defaultdict(set)
    for metric in metrics:
        if metric.workflow_type != "onboarding_funnel" or metric.subject_id is None:
            continue
        profiles_by_event[metric.strategy].add(metric.subject_id)

    uploads = profiles_by_event["cv_uploaded"]
    reviews = profiles_by_event["review_presented"]
    completions = profiles_by_event["onboarding_completed"]
    fact_confirmed = profiles_by_event["facts_confirmed"]
    fact_skipped = profiles_by_event["facts_skipped"]
    question_answered = profiles_by_event["question_answered"]
    question_skipped = profiles_by_event["question_skipped"]
    question_not_needed = profiles_by_event["question_no_question"]

    return {
        "profiles": {
            "cv_uploaded": len(uploads),
            "review_presented": len(reviews),
            "onboarding_completed": len(completions),
        },
        "decisions": {
            "facts_confirmed": len(fact_confirmed),
            "facts_skipped": len(fact_skipped),
            "question_answered": len(question_answered),
            "question_skipped": len(question_skipped),
            "question_not_needed": len(question_not_needed),
        },
        "conversion_percent": {
            "upload_to_review": _percent(len(reviews & uploads), len(uploads)),
            "review_to_completion": _percent(len(completions & reviews), len(reviews)),
            "upload_to_completion": _percent(len(completions & uploads), len(uploads)),
        },
        "dropoff_profiles": {
            "after_upload_before_review": len(uploads - reviews),
            "after_review_before_completion": len(reviews - completions),
        },
    }


def _percent(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0
