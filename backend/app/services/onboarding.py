from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from ..models import (
    ClarificationQuestion,
    EvaluationExample,
    Profile,
    ProfileFact,
    ProfileFactFeedback,
    ProfileInterest,
    ProfileSource,
)
from ..schemas import OnboardingAnalyzeIn, ProfileAnalyzeResult, ProfilePreferencesIn, ProfileSourcesIn
from .profile import (
    analyze_profile,
    get_or_create_profile,
    profile_output,
    update_profile_preferences,
    update_profile_sources,
)
from .storage import delete_private_file
from .telemetry import record_onboarding_event


ABANDONED_ONBOARDING_RETENTION = timedelta(hours=24)


def analyze_onboarding_profile(
    session: Session,
    user_id: UUID,
    payload: OnboardingAnalyzeIn,
) -> ProfileAnalyzeResult:
    """Save onboarding context and avoid rebuilding an unchanged CV preview."""
    profile = get_or_create_profile(session, user_id)
    sources_changed = any(
        (
            profile.github_url != payload.github_url.strip(),
            profile.linkedin_text != payload.linkedin_text.strip(),
            profile.manual_info != payload.manual_info.strip(),
        )
    )
    if sources_changed:
        update_profile_sources(
            session,
            user_id,
            ProfileSourcesIn(
                github_url=payload.github_url,
                linkedin_text=payload.linkedin_text,
                manual_info=payload.manual_info,
            ),
        )
    update_profile_preferences(
        session,
        user_id,
        ProfilePreferencesIn(career_interests=payload.career_interests),
    )
    profile = get_or_create_profile(session, user_id)
    if profile.status != "ready":
        result = analyze_profile(session, user_id)
        reused_preview = 0
    else:
        output = profile_output(session, user_id)
        result = ProfileAnalyzeResult(
            profile=output,
            generated_facts=0,
            open_questions=len([question for question in output.questions if question.status == "open"]),
        )
        reused_preview = 1
    record_onboarding_event(
        session,
        user_id,
        profile.id,
        "review_presented",
        counts={
            "reused_preview": reused_preview,
            "facts": len(result.profile.facts),
            "open_questions": result.open_questions,
            "career_interests": len(result.profile.career_interests),
        },
    )
    session.commit()
    return result


def cleanup_abandoned_onboarding(
    session: Session,
    *,
    now: datetime | None = None,
    retention: timedelta = ABANDONED_ONBOARDING_RETENTION,
    limit: int = 5,
) -> int:
    """Remove private preview data for accounts that did not finish onboarding."""
    timestamp = now or datetime.now(timezone.utc)
    profiles = list(
        session.exec(
            select(Profile)
            .where(
                Profile.onboarding_completed.is_(False),
                Profile.updated_at <= timestamp - retention,
            )
            .order_by(Profile.updated_at)
            .limit(max(1, min(limit, 100)))
        ).all()
    )
    cleaned = 0
    for profile in profiles:
        sources = list(
            session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id)).all()
        )
        try:
            for source in sources:
                delete_private_file(source.storage_path)
        except RuntimeError:
            session.rollback()
            continue
        for record in session.exec(
            select(ProfileFactFeedback).where(ProfileFactFeedback.profile_id == profile.id)
        ).all():
            session.delete(record)
        for record in session.exec(
            select(ClarificationQuestion).where(ClarificationQuestion.profile_id == profile.id)
        ).all():
            session.delete(record)
        for record in session.exec(select(ProfileFact).where(ProfileFact.profile_id == profile.id)).all():
            session.delete(record)
        for record in sources:
            session.delete(record)
        for record in session.exec(
            select(ProfileInterest).where(ProfileInterest.profile_id == profile.id)
        ).all():
            session.delete(record)
        for record in session.exec(
            select(EvaluationExample).where(
                EvaluationExample.user_id == profile.user_id,
                EvaluationExample.example_type == "profile_fact_review",
            )
        ).all():
            session.delete(record)
        profile.summary = ""
        profile.status = "needs_cv"
        profile.github_url = ""
        profile.linkedin_text = ""
        profile.manual_info = ""
        profile.years_experience = 0
        profile.last_analyzed_at = None
        profile.updated_at = timestamp
        session.add(profile)
        session.commit()
        cleaned += 1
    return cleaned
