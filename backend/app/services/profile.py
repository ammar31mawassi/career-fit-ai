from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

from sqlmodel import Session, select

from ..models import (
    ClarificationQuestion,
    Profile,
    ProfileFact,
    ProfileFactFeedback,
    ProfileInterest,
    ProfileSource,
)
from ..schemas import (
    BrowserOcrIn,
    ClarificationQuestionOut,
    OnboardingCompleteIn,
    ProfileAnalyzeResult,
    ProfileFactOut,
    ProfileOut,
    ProfilePreferencesIn,
    ProfileSourceOut,
    ProfileSourcesIn,
)
from ..config import get_settings
from .ontology import canonical_skill, extract_skills, infer_domain, skill_domain
from .document_reader import PDF_PARSER_VERSION, read_pdf_document
from .experience_normalization import professional_experience
from .profile_extraction import (
    EXTRACTOR_VERSION,
    ExtractedFact,
    extract_profile_facts,
    extracted_fact_key,
    fact_key,
)
from .storage import load_private_file, save_private_file
from .telemetry import record_evaluation_example, record_extraction_metric, record_onboarding_event
from .text import safe_filename


PROJECT_HINTS = (
    "project",
    "built",
    "developed",
    "implemented",
    "created",
    "designed",
    "delivered",
    "engineered",
)
LOCATION_TERMS = (
    "israel",
    "jerusalem",
    "tel aviv",
    "haifa",
    "yokneam",
    "herzliya",
    "ramat gan",
    "remote",
    "hybrid",
)
SPOKEN_LANGUAGES = ("english", "hebrew", "arabic", "french", "german", "spanish", "russian")


@dataclass(frozen=True)
class SkillEvidence:
    skill: str
    strength: float
    evidence_type: str
    evidence: str
    fact_id: int | None
    source_id: int | None
    recency_factor: float = 1.0


@dataclass(frozen=True)
class CandidateSnapshot:
    skills: set[str]
    skill_evidence: dict[str, SkillEvidence]
    projects: list[str]
    project_evidence: dict[str, str]
    years_experience: float
    internship_years: float
    education: str
    semesters_left: int | None
    location: str
    work_authorization: str
    availability: str
    languages: list[str]
    domain: str
    career_stage: str
    about_me: str
    summary: str
    evidence_by_skill: dict[str, str]


def get_or_create_profile(session: Session, user_id: UUID) -> Profile:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile:
        return profile
    profile = Profile(user_id=user_id)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def upload_cv_source(session: Session, user_id: UUID, filename: str, data: bytes) -> ProfileOut:
    profile = get_or_create_profile(session, user_id)
    cleaned_filename = safe_filename(filename)
    storage_path = save_private_file(user_id, f"cv-{cleaned_filename}", data, "application/pdf")
    read_result = read_pdf_document(data)
    existing = _source_by_type(session, profile, "cv")
    source = existing or ProfileSource(user_id=user_id, profile_id=profile.id or 0, source_type="cv")
    source.title = cleaned_filename
    source.storage_path = storage_path
    source.content_text = read_result.text
    source.metadata_json = json.dumps({"filename": cleaned_filename, **read_result.metadata()}, sort_keys=True)
    source.updated_at = _now()
    profile.status = "needs_analysis"
    profile.updated_at = _now()
    session.add(source)
    session.add(profile)
    if not profile.onboarding_completed:
        record_onboarding_event(
            session,
            user_id,
            profile.id,
            "cv_uploaded",
            counts={
                "readable": int(bool(read_result.text.strip())),
                "scanned_pdf": int(bool(read_result.metadata().get("scanned_pdf_detected"))),
            },
        )
    session.commit()
    return profile_output(session, user_id)


def apply_browser_ocr(session: Session, user_id: UUID, payload: BrowserOcrIn) -> ProfileOut:
    """Persist local OCR only when the original PDF parser could not read the CV.

    The browser performs the expensive OCR locally. The API accepts only the
    recovered text and compact quality metadata, never rendered page images.
    """
    profile = get_or_create_profile(session, user_id)
    source = _source_by_type(session, profile, "cv")
    if not source:
        raise ValueError("Upload the CV PDF before submitting browser OCR results.")

    metadata = _json_dict(source.metadata_json)
    extracted_characters = _meaningful_character_count(source.content_text)
    if not bool(metadata.get("scanned_pdf_detected")) or extracted_characters >= 80:
        raise ValueError("Browser OCR is only accepted when normal PDF extraction is insufficient.")

    recovered_text = payload.text.strip()
    if _meaningful_character_count(recovered_text) < 80:
        raise ValueError("Browser OCR could not recover enough readable CV text.")

    source.content_text = recovered_text
    source.metadata_json = json.dumps(
        {
            **metadata,
            "chars": len(recovered_text),
            "read_method": "browser_ocr",
            "scanned_pdf_detected": True,
            "ocr_attempted": True,
            "ocr_confidence": round(payload.confidence, 4),
            "ocr_engine": payload.engine,
            "ocr_pages": [page.model_dump() for page in payload.pages],
        },
        sort_keys=True,
    )
    source.updated_at = _now()
    profile.status = "needs_analysis"
    profile.updated_at = _now()
    session.add(source)
    session.add(profile)
    session.commit()
    return profile_output(session, user_id)


def upload_linkedin_pdf_source(session: Session, user_id: UUID, filename: str, data: bytes) -> ProfileOut:
    profile = get_or_create_profile(session, user_id)
    cleaned_filename = safe_filename(filename)
    storage_path = save_private_file(user_id, f"linkedin-{cleaned_filename}", data, "application/pdf")
    read_result = read_pdf_document(data)
    source = _source_by_type(session, profile, "linkedin_pdf") or ProfileSource(
        user_id=user_id,
        profile_id=profile.id or 0,
        source_type="linkedin_pdf",
    )
    source.title = cleaned_filename
    source.storage_path = storage_path
    source.content_text = read_result.text
    source.metadata_json = json.dumps({"filename": cleaned_filename, **read_result.metadata()}, sort_keys=True)
    source.updated_at = _now()
    profile.linkedin_text = read_result.text[:50000]
    profile.status = "needs_analysis"
    profile.updated_at = _now()
    session.add(source)
    session.add(profile)
    session.commit()
    return profile_output(session, user_id)


def update_profile_sources(session: Session, user_id: UUID, payload: ProfileSourcesIn) -> ProfileOut:
    profile = get_or_create_profile(session, user_id)
    profile.github_url = payload.github_url.strip()
    profile.linkedin_text = payload.linkedin_text.strip()
    profile.manual_info = payload.manual_info.strip()
    profile.status = "needs_analysis" if _has_cv(session, profile) else "needs_cv"
    profile.updated_at = _now()
    session.add(profile)

    _upsert_text_source(session, profile, "github", profile.github_url, _github_text(profile.github_url))
    _upsert_text_source(session, profile, "linkedin_text", "LinkedIn profile text", profile.linkedin_text)
    _upsert_text_source(session, profile, "manual", "Manually typed information", profile.manual_info)
    session.commit()
    return profile_output(session, user_id)


def update_profile_preferences(
    session: Session,
    user_id: UUID,
    payload: ProfilePreferencesIn,
) -> ProfileOut:
    profile = get_or_create_profile(session, user_id)
    existing = list(
        session.exec(select(ProfileInterest).where(ProfileInterest.profile_id == profile.id)).all()
    )
    existing_values = {interest.interest for interest in existing}
    requested_values = set(payload.career_interests)
    recommendation_unchanged = (
        payload.recommendations_enabled is None
        or profile.recommendations_enabled == payload.recommendations_enabled
    )
    if existing_values == requested_values and recommendation_unchanged:
        return profile_output(session, user_id)
    for interest in existing:
        session.delete(interest)
    # Execute deletions before inserting replacements. Without this flush,
    # SQLite/Postgres may insert the same selected interest first and hit the
    # (profile_id, interest) unique constraint during an onboarding retry.
    session.flush()
    for interest in payload.career_interests:
        session.add(
            ProfileInterest(
                user_id=user_id,
                profile_id=profile.id or 0,
                interest=interest,
            )
        )
    if payload.recommendations_enabled is not None:
        profile.recommendations_enabled = payload.recommendations_enabled
    profile.updated_at = _now()
    session.add(profile)
    session.commit()
    return profile_output(session, user_id)


def complete_onboarding(
    session: Session,
    user_id: UUID,
    payload: OnboardingCompleteIn,
) -> ProfileOut:
    profile = get_or_create_profile(session, user_id)
    if not _has_cv(session, profile):
        raise ValueError("Upload a CV before completing onboarding.")
    interests = list(
        session.exec(select(ProfileInterest).where(ProfileInterest.profile_id == profile.id)).all()
    )
    if not interests:
        raise ValueError("Choose at least one career interest.")
    if profile.status == "cv_unreadable":
        raise ValueError(
            "We couldn't read text from your CV. Upload a text-based PDF (not a scan) and analyze again."
        )
    if profile.status != "ready":
        raise ValueError("Analyze your profile before reviewing and completing onboarding.")

    pending_facts = list(
        session.exec(
            select(ProfileFact).where(
                ProfileFact.profile_id == profile.id,
                ProfileFact.review_status == "pending",
            )
        ).all()
    )
    pending_by_id = {fact.id or 0: fact for fact in pending_facts}
    approved_ids = set(payload.approved_fact_ids)
    rejected_ids = set(payload.rejected_fact_ids)
    if payload.facts_decision == "confirmed":
        reviewed_ids = approved_ids | rejected_ids
        if reviewed_ids != set(pending_by_id):
            raise ValueError("Confirm or reject every pending profile fact, or explicitly skip fact review.")
        _review_fact_records(session, user_id, [pending_by_id[fact_id] for fact_id in approved_ids], "approved")
        _review_fact_records(session, user_id, [pending_by_id[fact_id] for fact_id in rejected_ids], "rejected")

    open_questions = list(
        session.exec(
            select(ClarificationQuestion).where(
                ClarificationQuestion.profile_id == profile.id,
                ClarificationQuestion.status == "open",
            )
        ).all()
    )
    if payload.question_decision == "no_question":
        if open_questions:
            raise ValueError("Answer or skip the clarification question before completing onboarding.")
    else:
        question = next((item for item in open_questions if item.id == payload.question_id), None)
        if question is None:
            raise ValueError("The clarification question is no longer available. Review the latest profile.")
        if payload.question_decision == "answered":
            _apply_question_answer(session, user_id, question, payload.question_answer)
            session.delete(question)
        else:
            question.status = "skipped"
            question.answer = ""
            question.updated_at = _now()
            session.add(question)

    session.flush()
    _rebuild_profile_state(session, profile)
    profile.onboarding_completed = True
    profile.updated_at = _now()
    session.add(profile)
    record_onboarding_event(
        session,
        user_id,
        profile.id,
        f"facts_{payload.facts_decision}",
        counts={"approved": len(approved_ids), "rejected": len(rejected_ids), "pending": len(pending_facts)},
    )
    record_onboarding_event(
        session,
        user_id,
        profile.id,
        f"question_{payload.question_decision}",
        counts={"open_questions_presented": len(open_questions)},
    )
    record_onboarding_event(
        session,
        user_id,
        profile.id,
        "onboarding_completed",
        counts={"career_interests": len(interests)},
    )
    session.commit()
    return profile_output(session, user_id)


def analyze_profile(session: Session, user_id: UUID) -> ProfileAnalyzeResult:
    started = time.perf_counter()
    profile = get_or_create_profile(session, user_id)
    sources = _sources(session, profile)
    cv_sources = [source for source in sources if source.source_type == "cv"]
    if not cv_sources:
        profile.status = "needs_cv"
        profile.updated_at = _now()
        session.add(profile)
        record_extraction_metric(
            session,
            user_id,
            workflow_type="profile_extraction",
            subject_type="profile",
            subject_id=profile.id,
            status="failed",
            duration_ms=round((time.perf_counter() - started) * 1000),
            error_code="NO_CV",
        )
        session.commit()
        output = profile_output(session, user_id)
        return ProfileAnalyzeResult(profile=output, generated_facts=0, open_questions=len(output.questions))

    # Re-run older PDF parser versions before deciding that a CV is unreadable.
    _refresh_pdf_sources(session, sources)
    if not any(source.content_text.strip() for source in cv_sources):
        profile.status = "cv_unreadable"
        profile.updated_at = _now()
        session.add(profile)
        record_extraction_metric(
            session,
            user_id,
            workflow_type="profile_extraction",
            subject_type="profile",
            subject_id=profile.id,
            strategy=_profile_reader_strategy(sources),
            status="failed",
            duration_ms=round((time.perf_counter() - started) * 1000),
            error_code="CV_UNREADABLE",
        )
        session.commit()
        output = profile_output(session, user_id)
        return ProfileAnalyzeResult(profile=output, generated_facts=0, open_questions=len(output.questions))

    existing_facts = list(session.exec(select(ProfileFact).where(ProfileFact.profile_id == profile.id)).all())
    reviewed: dict[str, ProfileFact] = {}
    for record in existing_facts:
        status = record.review_status or ("approved" if record.user_approved else "pending")
        record.review_status = status
        if status in {"approved", "rejected"}:
            key = record.extraction_key or fact_key(record.fact_type, record.value)
            record.extraction_key = key
            reviewed[key] = record
            session.add(record)
        else:
            session.delete(record)
    for record in session.exec(select(ClarificationQuestion).where(ClarificationQuestion.profile_id == profile.id)).all():
        session.delete(record)
    session.flush()

    generated = 0
    all_text = "\n".join(source.content_text for source in sources if source.content_text)
    profile.years_experience = _extract_professional_years(all_text)
    grouped: dict[str, list[tuple[ProfileSource, ExtractedFact]]] = {}
    for source in sources:
        for candidate in extract_profile_facts(source.source_type, source.content_text):
            grouped.setdefault(extracted_fact_key(candidate), []).append((source, candidate))
    for key, candidates in grouped.items():
        if key in reviewed:
            _update_reviewed_fact(reviewed[key], candidates)
            session.add(reviewed[key])
            continue
        session.add(_merged_fact(profile, key, candidates))
        generated += 1
    session.flush()

    snapshot = candidate_snapshot(session, profile)
    profile.years_experience = snapshot.years_experience
    profile.summary = _build_summary(snapshot)
    profile.status = "ready"
    profile.last_analyzed_at = _now()
    profile.updated_at = _now()
    session.add(profile)
    _create_questions(session, profile, snapshot)
    record_extraction_metric(
        session,
        user_id,
        workflow_type="profile_extraction",
        subject_type="profile",
        subject_id=profile.id,
        strategy=_profile_reader_strategy(sources),
        duration_ms=round((time.perf_counter() - started) * 1000),
        input_length=len(all_text),
        output_length=sum(len(fact.value) for fact in session.exec(
            select(ProfileFact).where(ProfileFact.profile_id == profile.id)
        ).all()),
        counts={
            "facts": len(grouped),
            "skills": len(snapshot.skills),
            "projects": len(snapshot.projects),
            "sources": len(sources),
        },
    )
    session.commit()
    output = profile_output(session, user_id)
    return ProfileAnalyzeResult(
        profile=output,
        generated_facts=generated,
        open_questions=len([question for question in output.questions if question.status == "open"]),
    )


def profile_output(session: Session, user_id: UUID) -> ProfileOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if not profile:
        return ProfileOut()
    sources = _sources(session, profile)
    facts = session.exec(
        select(ProfileFact)
        .where(ProfileFact.profile_id == profile.id)
        .order_by(ProfileFact.fact_type, ProfileFact.confidence.desc())
    ).all()
    questions = session.exec(
        select(ClarificationQuestion)
        .where(ClarificationQuestion.profile_id == profile.id)
        .order_by(ClarificationQuestion.status, ClarificationQuestion.created_at)
    ).all()
    interests = session.exec(
        select(ProfileInterest)
        .where(ProfileInterest.profile_id == profile.id)
        .order_by(ProfileInterest.interest)
    ).all()
    return ProfileOut(
        id=profile.id,
        summary=profile.summary,
        status=profile.status,
        github_url=profile.github_url,
        linkedin_text=profile.linkedin_text,
        manual_info=profile.manual_info,
        years_experience=profile.years_experience,
        onboarding_completed=profile.onboarding_completed,
        recommendations_enabled=profile.recommendations_enabled,
        career_interests=[interest.interest for interest in interests],
        last_analyzed_at=profile.last_analyzed_at,
        updated_at=profile.updated_at,
        sources=[_profile_source_output(source) for source in sources],
        facts=[
            ProfileFactOut(
                id=fact.id or 0,
                fact_type=fact.fact_type,
                value=fact.value,
                evidence=fact.evidence,
                confidence=fact.confidence,
                user_approved=fact.user_approved,
                review_status=fact.review_status,
                support_count=fact.support_count,
                source_ids=_json_int_list(fact.source_ids_json),
                source_id=fact.source_id,
            )
            for fact in facts
        ],
        questions=[
            ClarificationQuestionOut(
                id=question.id or 0,
                field_key=question.field_key,
                question=question.question,
                answer=question.answer,
                status=question.status,
            )
            for question in questions
        ],
    )


def _profile_source_output(source: ProfileSource) -> ProfileSourceOut:
    metadata = _json_dict(source.metadata_json)
    raw_confidence = metadata.get("ocr_confidence")
    try:
        ocr_confidence = float(raw_confidence) if raw_confidence is not None else None
    except (TypeError, ValueError):
        ocr_confidence = None
    return ProfileSourceOut(
        id=source.id or 0,
        source_type=source.source_type,
        title=source.title,
        has_text=bool(source.content_text.strip()),
        read_method=str(metadata.get("read_method") or ""),
        scanned_pdf_detected=bool(metadata.get("scanned_pdf_detected")),
        ocr_attempted=bool(metadata.get("ocr_attempted")),
        ocr_confidence=ocr_confidence,
        ocr_recommended=(
            bool(metadata.get("scanned_pdf_detected"))
            and _meaningful_character_count(source.content_text) < 80
        ),
        updated_at=source.updated_at,
    )


def _profile_reader_strategy(sources: list[ProfileSource]) -> str:
    methods = {
        str(_json_dict(source.metadata_json).get("read_method") or source.source_type)
        for source in sources
        if source.content_text.strip()
    }
    return "+".join(sorted(methods))[:160]


def _record_fact_feedback_example(
    session: Session,
    user_id: UUID,
    fact: ProfileFact,
    label: str,
    *,
    value_changed: bool = False,
) -> None:
    metadata = _json_dict(fact.metadata_json)
    record_evaluation_example(
        session,
        user_id,
        example_type="profile_fact_review",
        subject_id=fact.id,
        label=label,
        model_version=str(metadata.get("extractor_version") or EXTRACTOR_VERSION),
        features={
            "fact_type": fact.fact_type,
            "confidence": round(fact.confidence, 3),
            "support_count": fact.support_count,
            "source_count": len(_json_int_list(fact.source_ids_json)),
            "evidence_type": str(metadata.get("evidence_type") or "unknown"),
            "value_changed": value_changed,
            "value_length_bucket": min(10, len(fact.value) // 40),
        },
    )


def patch_fact(session: Session, user_id: UUID, fact_id: int, value: str, review_status: str) -> ProfileOut:
    fact = session.get(ProfileFact, fact_id)
    if not fact or fact.user_id != user_id:
        raise ValueError("Profile fact not found.")
    original_value = fact.value
    original_key = fact.extraction_key or fact_key(fact.fact_type, original_value)
    fact.value = value.strip()
    fact.review_status = review_status
    fact.user_approved = review_status == "approved"
    fact.reviewed_at = _now() if review_status in {"approved", "rejected"} else None
    # Keep the extractor's original key after a correction. This suppresses the
    # same incorrect extraction on future analyses while retaining the user's
    # corrected value.
    fact.extraction_key = original_key
    fact.updated_at = _now()
    session.add(fact)
    session.add(
        ProfileFactFeedback(
            user_id=user_id,
            profile_id=fact.profile_id,
            fact_id=fact.id,
            fact_type=fact.fact_type,
            extraction_key=fact.extraction_key,
            action="edited_and_approved" if original_value != fact.value and review_status == "approved" else review_status,
            original_value=original_value,
            corrected_value=fact.value if original_value != fact.value else "",
            source_ids_json=fact.source_ids_json,
            extractor_version=EXTRACTOR_VERSION,
        )
    )
    _record_fact_feedback_example(
        session,
        user_id,
        fact,
        "edited_and_approved" if original_value != fact.value and review_status == "approved" else review_status,
        value_changed=original_value != fact.value,
    )
    session.flush()
    profile = session.get(Profile, fact.profile_id)
    if profile:
        _rebuild_profile_state(session, profile)
    session.commit()
    return profile_output(session, user_id)


def patch_facts_bulk(
    session: Session,
    user_id: UUID,
    fact_ids: list[int],
    review_status: str,
) -> ProfileOut:
    ids = list(dict.fromkeys(fact_ids))
    facts = list(
        session.exec(
            select(ProfileFact).where(
                ProfileFact.user_id == user_id,
                ProfileFact.id.in_(ids),
            )
        ).all()
    )
    if len(facts) != len(ids):
        raise ValueError("One or more profile facts were not found.")
    _review_fact_records(session, user_id, facts, review_status)
    session.flush()
    profile = session.get(Profile, facts[0].profile_id)
    if profile:
        _rebuild_profile_state(session, profile)
    session.commit()
    return profile_output(session, user_id)


def _review_fact_records(
    session: Session,
    user_id: UUID,
    facts: list[ProfileFact],
    review_status: str,
) -> None:
    now = _now()
    for fact in facts:
        fact.review_status = review_status
        fact.user_approved = review_status == "approved"
        fact.reviewed_at = now
        fact.extraction_key = fact.extraction_key or fact_key(fact.fact_type, fact.value)
        fact.updated_at = now
        session.add(fact)
        session.add(
            ProfileFactFeedback(
                user_id=user_id,
                profile_id=fact.profile_id,
                fact_id=fact.id,
                fact_type=fact.fact_type,
                extraction_key=fact.extraction_key,
                action=review_status,
                original_value=fact.value,
                corrected_value="",
                source_ids_json=fact.source_ids_json,
                extractor_version=EXTRACTOR_VERSION,
            )
        )
        _record_fact_feedback_example(session, user_id, fact, review_status)


def add_fact(session: Session, user_id: UUID, fact_type: str, value: str) -> ProfileOut:
    profile = get_or_create_profile(session, user_id)
    cleaned = value.strip()
    if fact_type == "skill":
        cleaned = canonical_skill(cleaned) or cleaned.lower()
    key = fact_key(fact_type, cleaned)
    fact = session.exec(
        select(ProfileFact).where(
            ProfileFact.profile_id == profile.id,
            ProfileFact.extraction_key == key,
            ProfileFact.review_status != "rejected",
        )
    ).first()
    if fact is None:
        fact = ProfileFact(
            user_id=user_id,
            profile_id=profile.id or 0,
            fact_type=fact_type,
            value=cleaned,
            evidence="Added manually by the user.",
            metadata_json=json.dumps(
                {"evidence_type": "user_approved", "extractor_version": EXTRACTOR_VERSION},
                sort_keys=True,
            ),
            confidence=1.0,
            user_approved=True,
            review_status="approved",
            reviewed_at=_now(),
            extraction_key=key,
        )
        session.add(fact)
        session.flush()
    else:
        fact.value = cleaned
        fact.user_approved = True
        fact.review_status = "approved"
        fact.reviewed_at = _now()
        fact.updated_at = _now()
        session.add(fact)
    session.add(
        ProfileFactFeedback(
            user_id=user_id,
            profile_id=profile.id or 0,
            fact_id=fact.id,
            fact_type=fact_type,
            extraction_key=key,
            action="manually_added",
            original_value="",
            corrected_value=cleaned,
            source_ids_json="[]",
            extractor_version=EXTRACTOR_VERSION,
        )
    )
    _record_fact_feedback_example(session, user_id, fact, "manually_added", value_changed=True)
    session.flush()
    _rebuild_profile_state(session, profile)
    session.commit()
    return profile_output(session, user_id)


def answer_question(session: Session, user_id: UUID, question_id: int, answer: str) -> ProfileOut:
    question = session.get(ClarificationQuestion, question_id)
    if not question or question.user_id != user_id:
        raise ValueError("Profile fact question not found.")
    profile = _apply_question_answer(session, user_id, question, answer)
    session.delete(question)
    session.flush()
    if profile:
        _rebuild_profile_state(session, profile)
    session.commit()
    return profile_output(session, user_id)


def _apply_question_answer(
    session: Session,
    user_id: UUID,
    question: ClarificationQuestion,
    answer: str,
) -> Profile | None:
    profile = session.get(Profile, question.profile_id)
    if not profile:
        return None
    cleaned_answer = answer.strip()
    values = extract_skills(cleaned_answer) if question.field_key == "skill" else [cleaned_answer]
    if not values:
        values = [cleaned_answer]
    for value in values:
        session.add(
            ProfileFact(
                user_id=user_id,
                profile_id=profile.id or 0,
                fact_type=question.field_key,
                value=value,
                evidence=f"User clarification: {question.question}",
                confidence=1.0,
                user_approved=True,
                review_status="approved",
                reviewed_at=_now(),
                extraction_key=fact_key(question.field_key, value),
                metadata_json=json.dumps(
                    {"evidence_type": "user_approved", "extractor_version": EXTRACTOR_VERSION}
                ),
            )
        )
    if question.field_key == "years_experience":
        profile.years_experience = _number_from_answer(cleaned_answer)
    return profile


def _rebuild_profile_state(session: Session, profile: Profile) -> None:
    existing_questions = list(session.exec(
        select(ClarificationQuestion).where(ClarificationQuestion.profile_id == profile.id)
    ).all())
    skipped_fields = {question.field_key for question in existing_questions if question.status == "skipped"}
    for question in existing_questions:
        session.delete(question)
    session.flush()
    snapshot = candidate_snapshot(session, profile)
    profile.years_experience = snapshot.years_experience
    profile.summary = _build_summary(snapshot)
    profile.updated_at = _now()
    session.add(profile)
    _create_questions(session, profile, snapshot)
    session.flush()
    if skipped_fields:
        regenerated = session.exec(
            select(ClarificationQuestion).where(ClarificationQuestion.profile_id == profile.id)
        ).all()
        for question in regenerated:
            if question.field_key in skipped_fields:
                question.status = "skipped"
                question.updated_at = _now()
                session.add(question)


def candidate_snapshot(session: Session, profile: Profile) -> CandidateSnapshot:
    facts = list(session.exec(select(ProfileFact).where(ProfileFact.profile_id == profile.id)).all())
    sources = {source.id: source for source in _sources(session, profile)}
    skill_evidence: dict[str, SkillEvidence] = {}
    projects: list[str] = []
    project_evidence: dict[str, str] = {}
    scalar: dict[str, str] = {}
    languages: list[str] = []
    years = max(0.0, profile.years_experience)
    internship_years = 0.0

    for fact in facts:
        if fact.review_status == "rejected":
            continue
        source = sources.get(fact.source_id)
        metadata = _json_dict(fact.metadata_json)
        if fact.fact_type == "skill":
            skill = canonical_skill(fact.value) or fact.value.lower().strip()
            evidence_type = str(metadata.get("evidence_type") or _evidence_type(source, fact.evidence))
            recency_factor = _recency_factor(fact.evidence)
            strength = _evidence_strength(
                evidence_type, fact.confidence, fact.user_approved, recency_factor
            )
            current = skill_evidence.get(skill)
            if current is None or strength > current.strength:
                skill_evidence[skill] = SkillEvidence(
                    skill=skill,
                    strength=strength,
                    evidence_type=evidence_type,
                    evidence=fact.evidence,
                    fact_id=fact.id,
                    source_id=fact.source_id,
                    recency_factor=recency_factor,
                )
        elif fact.fact_type == "project" and fact.value not in projects:
            projects.append(fact.value)
            project_evidence[fact.value] = fact.evidence
        elif fact.fact_type == "language" and fact.value.lower() not in languages:
            languages.append(fact.value.lower())
        elif fact.fact_type == "years_experience":
            years = max(years, _number_from_answer(fact.value))
        elif fact.fact_type == "internship_years":
            internship_years = max(internship_years, _number_from_answer(fact.value))
        elif fact.fact_type == "education":
            current = scalar.get("education", "")
            if fact.user_approved or _education_rank(fact.value) > _education_rank(current):
                scalar["education"] = fact.value
        elif fact.fact_type not in scalar or fact.user_approved or fact.confidence > 0.8:
            scalar[fact.fact_type] = fact.value

    semesters = _optional_int(scalar.get("semesters_left", ""))
    education = scalar.get("education", "")
    career_stage = _career_stage(years, internship_years, semesters, education, "\n".join(f.value for f in facts))
    domain = scalar.get("domain") or infer_domain(set(skill_evidence))
    return CandidateSnapshot(
        skills=set(skill_evidence),
        skill_evidence=skill_evidence,
        projects=projects,
        project_evidence=project_evidence,
        years_experience=round(years, 1),
        internship_years=round(internship_years, 1),
        education=education,
        semesters_left=semesters,
        location=scalar.get("location", ""),
        work_authorization=scalar.get("work_authorization", ""),
        availability=scalar.get("availability", ""),
        languages=languages,
        domain=domain,
        career_stage=career_stage,
        about_me=scalar.get("about_me", ""),
        summary=profile.summary,
        evidence_by_skill={skill: evidence.evidence for skill, evidence in skill_evidence.items()},
    )


def _refresh_pdf_sources(session: Session, sources: list[ProfileSource]) -> None:
    for source in sources:
        if source.source_type not in {"cv", "linkedin_pdf"} or not source.storage_path:
            continue
        metadata = _json_dict(source.metadata_json)
        if metadata.get("parser_version") == PDF_PARSER_VERSION:
            continue
        data = load_private_file(source.storage_path)
        if not data:
            continue
        read_result = read_pdf_document(data)
        source.content_text = read_result.text
        metadata.update(read_result.metadata())
        source.metadata_json = json.dumps(metadata, sort_keys=True)
        source.updated_at = _now()
        session.add(source)
    session.flush()


def _source_by_type(session: Session, profile: Profile, source_type: str) -> ProfileSource | None:
    return session.exec(
        select(ProfileSource).where(ProfileSource.profile_id == profile.id, ProfileSource.source_type == source_type)
    ).first()


def _sources(session: Session, profile: Profile) -> list[ProfileSource]:
    return list(
        session.exec(
            select(ProfileSource).where(ProfileSource.profile_id == profile.id).order_by(ProfileSource.created_at)
        ).all()
    )


def _has_cv(session: Session, profile: Profile) -> bool:
    return bool(_source_by_type(session, profile, "cv"))


def _upsert_text_source(session: Session, profile: Profile, source_type: str, title: str, text: str) -> None:
    existing = _source_by_type(session, profile, source_type)
    if not text.strip() and not existing:
        return
    source = existing or ProfileSource(user_id=profile.user_id, profile_id=profile.id or 0, source_type=source_type)
    source.title = title[:180] or source_type
    source.content_text = text.strip()
    source.updated_at = _now()
    session.add(source)


def _merged_fact(
    profile: Profile,
    key: str,
    candidates: list[tuple[ProfileSource, ExtractedFact]],
) -> ProfileFact:
    records = _unique_source_candidates(candidates)
    source_priority = {"cv": 4, "linkedin_pdf": 3, "linkedin_text": 3, "manual": 2, "github": 1}
    representative_source, representative = max(
        records,
        key=lambda item: (
            item[1].confidence,
            source_priority.get(item[0].source_type, 0),
            len(item[1].value),
        ),
    )
    source_ids = [source.id for source, _ in records if source.id is not None]
    confidence = min(0.97, max(candidate.confidence for _, candidate in records) + 0.08 * (len(source_ids) - 1))
    metadata = dict(representative.metadata)
    metadata.update(
        {
            "extractor_version": EXTRACTOR_VERSION,
            "support_count": len(source_ids),
            "source_evidence": [
                {
                    "source_id": source.id,
                    "source_type": source.source_type,
                    "evidence": candidate.evidence,
                    "confidence": candidate.confidence,
                }
                for source, candidate in records
            ],
        }
    )
    return ProfileFact(
        user_id=profile.user_id,
        profile_id=profile.id or 0,
        source_id=representative_source.id,
        source_ids_json=json.dumps(source_ids),
        support_count=max(1, len(source_ids)),
        extraction_key=key,
        fact_type=representative.fact_type,
        value=representative.value,
        evidence=representative.evidence,
        confidence=round(confidence, 3),
        review_status="pending",
        metadata_json=json.dumps(metadata, sort_keys=True),
    )


def _update_reviewed_fact(
    fact: ProfileFact,
    candidates: list[tuple[ProfileSource, ExtractedFact]],
) -> None:
    records = _unique_source_candidates(candidates)
    source_ids = [source.id for source, _ in records if source.id is not None]
    fact.source_ids_json = json.dumps(source_ids)
    fact.support_count = max(1, len(source_ids))
    if records:
        fact.confidence = round(
            min(1.0, max(candidate.confidence for _, candidate in records) + 0.08 * (len(source_ids) - 1)),
            3,
        )
        metadata = _json_dict(fact.metadata_json)
        metadata.update({"extractor_version": EXTRACTOR_VERSION, "support_count": len(source_ids)})
        fact.metadata_json = json.dumps(metadata, sort_keys=True)
    fact.updated_at = _now()


def _unique_source_candidates(
    candidates: list[tuple[ProfileSource, ExtractedFact]],
) -> list[tuple[ProfileSource, ExtractedFact]]:
    by_source: dict[int, tuple[ProfileSource, ExtractedFact]] = {}
    for source, candidate in candidates:
        source_key = source.id if source.id is not None else -id(source)
        current = by_source.get(source_key)
        if current is None or candidate.confidence > current[1].confidence:
            by_source[source_key] = (source, candidate)
    return list(by_source.values())


def _extract_facts_from_source(session: Session, profile: Profile, source: ProfileSource) -> int:
    text = source.content_text
    if not text.strip():
        return 0
    count = 0
    for skill in extract_skills(text):
        evidence = _evidence_sentence(text, skill)
        evidence_type = _evidence_type(source, evidence)
        confidence = _source_confidence(source.source_type, evidence_type)
        session.add(
            ProfileFact(
                user_id=profile.user_id,
                profile_id=profile.id or 0,
                source_id=source.id,
                fact_type="skill",
                value=skill,
                evidence=evidence,
                confidence=confidence,
                metadata_json=json.dumps(
                    {"evidence_type": evidence_type, "domain": skill_domain(skill)}, sort_keys=True
                ),
            )
        )
        count += 1

    for project in _extract_projects(text):
        session.add(
            ProfileFact(
                user_id=profile.user_id,
                profile_id=profile.id or 0,
                source_id=source.id,
                fact_type="project",
                value=project,
                evidence=project,
                confidence=0.8 if source.source_type in {"cv", "github"} else 0.68,
                metadata_json=json.dumps({"evidence_type": "project"}),
            )
        )
        count += 1

    extracted: list[tuple[str, str, str, float]] = []
    education = _extract_education(text)
    if education:
        extracted.append(("education", education, _evidence_sentence(text, education.split()[-1]), 0.82))
    semesters = _extract_semesters_left(text)
    if semesters is not None:
        extracted.append(("semesters_left", str(semesters), _evidence_sentence(text, "semester"), 0.9))
    location = _extract_location(text)
    if location:
        extracted.append(("location", location, _evidence_sentence(text, location.split(",")[0]), 0.7))
    availability = _extract_availability(text)
    if availability:
        extracted.append(("availability", availability, _evidence_sentence(text, availability.split()[0]), 0.75))
    authorization = _extract_work_authorization(text)
    if authorization:
        extracted.append(("work_authorization", authorization, authorization, 0.72))
    internship = _extract_internship_years(text)
    if internship > 0:
        extracted.append(("internship_years", f"{internship:g}", _evidence_sentence(text, "intern"), 0.78))
    for language in _extract_languages(text):
        extracted.append(("language", language, _evidence_sentence(text, language), 0.72))
    skills = extract_skills(text)
    if skills:
        extracted.append(("domain", infer_domain(skills), ", ".join(skills[:8]), 0.62))

    for fact_type, value, evidence, confidence in extracted:
        session.add(
            ProfileFact(
                user_id=profile.user_id,
                profile_id=profile.id or 0,
                source_id=source.id,
                fact_type=fact_type,
                value=value,
                evidence=evidence or value,
                confidence=confidence,
                metadata_json=json.dumps({"evidence_type": _evidence_type(source, evidence)}),
            )
        )
        count += 1
    return count


def _create_questions(session: Session, profile: Profile, snapshot: CandidateSnapshot) -> None:
    questions: list[tuple[str, str]] = []
    resolved_fields = {
        fact.fact_type
        for fact in session.exec(
            select(ProfileFact).where(
                ProfileFact.profile_id == profile.id,
                ProfileFact.review_status != "rejected",
            )
        ).all()
    }
    # Zero is a valid, important answer. Ask only when experience is unknown,
    # not when the candidate explicitly confirmed that they have none.
    if snapshot.years_experience <= 0 and "years_experience" not in resolved_fields:
        questions.append(
            (
                "years_experience",
                "How many months or years of professional software experience do you have, excluding coursework and personal projects?",
            )
        )
    if not snapshot.location:
        questions.append(("location", "Which locations and work modes are realistic for you?"))
    if snapshot.career_stage == "student" and snapshot.semesters_left is None:
        questions.append(("semesters_left", "How many semesters remain until you complete your degree?"))
    if not snapshot.availability:
        questions.append(("availability", "When can you start, and are you available full-time or part-time?"))
    if not snapshot.projects:
        questions.append(("project", "Which two or three projects are strongest for software roles?"))
    if len(snapshot.skills) < 5:
        questions.append(("skill", "Which technical skills are missing from the uploaded sources?"))
    if not snapshot.about_me:
        questions.append(
            (
                "about_me",
                "In one factual sentence, how would you describe your professional focus or strongest differentiator?",
            )
        )
    for field_key, question in questions:
        session.add(
            ClarificationQuestion(
                user_id=profile.user_id,
                profile_id=profile.id or 0,
                field_key=field_key,
                question=question,
            )
        )


def _github_text(github_url: str) -> str:
    if not github_url.strip():
        return ""
    username = _github_username(github_url)
    if not username:
        return f"GitHub profile could not be read: {github_url.strip()}"
    return _cached_github_text(username.lower(), int(time.time() // 900))


@lru_cache(maxsize=256)
def _cached_github_text(username: str, _time_bucket: int) -> str:
    canonical_url = f"https://github.com/{username}"
    try:
        profile = _github_api_json(f"/users/{urllib.parse.quote(username)}")
        repos = _github_api_json(
            f"/users/{urllib.parse.quote(username)}/repos?per_page=100&sort=pushed&direction=desc&type=owner"
        )
    except Exception:
        return f"GitHub profile: {canonical_url}"
    if not isinstance(repos, list):
        return f"GitHub profile: {canonical_url}"

    lines = [f"GitHub profile: {canonical_url}"]
    if isinstance(profile, dict):
        name = str(profile.get("name") or "").strip()
        bio = str(profile.get("bio") or "").strip()
        location = str(profile.get("location") or "").strip()
        blog = str(profile.get("blog") or "").strip()
        if name:
            lines.append(f"GitHub name: {name}")
        if bio:
            lines.append(f"GitHub bio: {bio}")
        if location:
            lines.append(f"GitHub location: {location}")
        if blog:
            lines.append(f"GitHub website: {blog}")

    ranked = sorted(
        [repo for repo in repos if _usable_github_repo(repo)],
        key=_github_repo_rank,
        reverse=True,
    )
    for repo in ranked[:12]:
        topics = [str(topic) for topic in repo.get("topics", []) if str(topic).strip()]
        details = [str(repo.get("description") or "").strip()]
        language = str(repo.get("language") or "").strip()
        if language:
            details.append(f"Language: {language}")
        if topics:
            details.append(f"Topics: {', '.join(topics[:8])}")
        stars = int(repo.get("stargazers_count") or 0)
        if stars:
            details.append(f"Stars: {stars}")
        pushed_at = str(repo.get("pushed_at") or "")[:10]
        if pushed_at:
            details.append(f"Last pushed: {pushed_at}")
        lines.append(f"Project {repo.get('name')}: " + ". ".join(part for part in details if part))
    return "\n".join(lines)


def _github_api_json(path: str) -> object:
    settings = get_settings()
    headers = {
        "User-Agent": "career-fit-ai",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    request = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=6) as response:
        return json.loads(response.read(2_000_000).decode("utf-8"))


def _usable_github_repo(repo: object) -> bool:
    return bool(
        isinstance(repo, dict)
        and repo.get("name")
        and not repo.get("fork")
        and not repo.get("archived")
        and not repo.get("disabled")
    )


def _github_repo_rank(repo: dict[str, object]) -> tuple[int, int, int, str]:
    evidence = int(bool(repo.get("description"))) + int(bool(repo.get("language"))) + int(bool(repo.get("topics")))
    stars = min(int(repo.get("stargazers_count") or 0), 1000)
    size = min(int(repo.get("size") or 0), 100000)
    return evidence, stars, size, str(repo.get("pushed_at") or "")


def _github_username(github_url: str) -> str:
    value = github_url.strip().rstrip("/")
    if not value:
        return ""
    if "/" not in value:
        username = value
    else:
        parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
        if parsed.hostname not in {"github.com", "www.github.com"}:
            return ""
        parts = [part for part in parsed.path.split("/") if part]
        username = parts[0] if parts else ""
    reserved = {"about", "apps", "collections", "enterprise", "events", "explore", "features", "issues", "login", "marketplace", "new", "notifications", "orgs", "pricing", "pulls", "search", "settings", "signup", "sponsors", "topics"}
    if username.lower() in reserved:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        return ""
    return username


def _meaningful_character_count(text: str) -> int:
    return sum(character.isalnum() for character in text)


def _extract_professional_years(text: str) -> float:
    return professional_experience(text).years


def _extract_internship_years(text: str) -> float:
    lower = text.lower()
    months = [float(value) for value in re.findall(r"\b(\d+)\s*[- ]?months?\s+(?:software\s+)?intern", lower)]
    years = [float(value) for value in re.findall(r"\b(\d+(?:\.\d+)?)\s*[- ]?years?\s+(?:software\s+)?intern", lower)]
    values = [*years, *[month / 12 for month in months]]
    return round(max(values), 1) if values else 0.0


def _extract_projects(text: str) -> list[str]:
    rough = re.split(r"(?<=[.!?])\s+|\n+|[•*]", text)
    projects: list[str] = []
    for sentence in rough:
        cleaned = re.sub(r"\s+", " ", sentence).strip(" -–—")
        lower = cleaned.lower()
        if 20 <= len(cleaned) <= 300 and any(hint in lower for hint in PROJECT_HINTS):
            projects.append(cleaned)
        if len(projects) >= 10:
            break
    return _dedupe(projects)


def _extract_education(text: str) -> str:
    lower = text.lower()
    field = ""
    for token, label in (
        ("computer science", "Computer Science"),
        ("software engineering", "Software Engineering"),
        ("computer engineering", "Computer Engineering"),
        ("electrical engineering", "Electrical Engineering"),
        ("information systems", "Information Systems"),
    ):
        if token in lower:
            field = label
            break
    if not field:
        return ""
    if any(token in lower for token in ("b.sc", "bsc", "bachelor")):
        return f"B.Sc. in {field}"
    if any(token in lower for token in ("m.sc", "msc", "master")):
        return f"M.Sc. in {field}"
    return f"{field} education"


def _extract_semesters_left(text: str) -> int | None:
    lower = text.lower()
    patterns = (
        r"\b(\d+)\s+semesters?\s+(?:remaining|left|to go)\b",
        r"\b(?:remaining|left)\s*[:\-]?\s*(\d+)\s+semesters?\b",
    )
    values = [int(value) for pattern in patterns for value in re.findall(pattern, lower)]
    return min(values) if values else None


def _extract_location(text: str) -> str:
    hits = [term for term in LOCATION_TERMS if re.search(_phrase_pattern(term), text, re.IGNORECASE)]
    return ", ".join(hits[:3])


def _extract_languages(text: str) -> list[str]:
    lines = [line for line in text.splitlines() if "language" in line.lower()]
    scope = " ".join(lines) if lines else text
    return [language for language in SPOKEN_LANGUAGES if re.search(_phrase_pattern(language), scope, re.IGNORECASE)]


def _extract_availability(text: str) -> str:
    lower = text.lower()
    for pattern, value in (
        (r"available\s+(?:to\s+)?start\s+immediately|immediate availability", "Available immediately"),
        (r"available\s+full[- ]time|full[- ]time availability", "Available full-time"),
        (r"available\s+part[- ]time|part[- ]time availability", "Available part-time"),
        (r"available\s+(\d+)\s+(?:days|hours)\s+(?:a|per)\s+week", ""),
    ):
        match = re.search(pattern, lower)
        if match:
            if value:
                return value
            return match.group(0).capitalize()
    return ""


def _extract_work_authorization(text: str) -> str:
    lower = text.lower()
    if "authorized to work in israel" in lower or "israeli citizen" in lower:
        return "Authorized to work in Israel"
    if "requires sponsorship" in lower or "need sponsorship" in lower:
        return "Requires work sponsorship"
    return ""


def _evidence_sentence(text: str, term: str) -> str:
    canonical = canonical_skill(term)
    aliases = [term]
    if canonical:
        aliases.append(canonical)
    segments = re.split(r"(?<=[.!?])\s+|\n+|[•*]", text)
    for sentence in segments:
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if any(alias.lower() in cleaned.lower() for alias in aliases) and 3 <= len(cleaned) <= 320:
            return cleaned
    return term


def _evidence_type(source: ProfileSource | None, evidence: str) -> str:
    if source is None:
        return "user_approved"
    if source.source_type == "manual":
        return "self_reported"
    if source.source_type == "github":
        return "github_project"
    lower = evidence.lower()
    if "intern" in lower:
        return "internship"
    if any(hint in lower for hint in PROJECT_HINTS):
        return "project"
    if any(word in lower for word in ("course", "coursework", "studied", "university")):
        return "coursework"
    if source.source_type in {"linkedin_pdf", "linkedin_text"} and any(
        word in lower for word in ("experience", "engineer", "developer", "worked")
    ):
        return "professional"
    return "cv_mention"


def _source_confidence(source_type: str, evidence_type: str) -> float:
    if evidence_type == "professional":
        return 0.9
    if evidence_type in {"project", "internship", "github_project"}:
        return 0.82
    if evidence_type == "coursework":
        return 0.68
    if source_type == "manual":
        return 0.55
    return 0.65


def _evidence_strength(
    evidence_type: str,
    confidence: float,
    approved: bool,
    recency_factor: float = 1.0,
) -> float:
    base = {
        "professional": 1.0,
        "internship": 0.85,
        "project": 0.8,
        "github_project": 0.65,
        "declared_skill": 0.58,
        "coursework": 0.55,
        "user_approved": 0.45,
        "self_reported": 0.4,
        "cv_mention": 0.35,
    }.get(evidence_type, 0.3)
    if approved:
        # Confirmation must change the match outcome, while demonstrated
        # project/work evidence remains the strongest signal.
        base = max(base, 0.7)
    return round(
        min(1.0, base * (0.7 + 0.3 * max(0.0, min(1.0, confidence))) * recency_factor),
        3,
    )


def _recency_factor(evidence: str) -> float:
    years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", evidence)]
    if not years:
        return 1.0
    age = max(0, datetime.now(timezone.utc).year - max(years))
    if age <= 2:
        return 1.0
    if age <= 5:
        return 0.85
    return 0.7


def _career_stage(
    years: float,
    internship_years: float,
    semesters_left: int | None,
    education: str,
    text: str,
) -> str:
    lower = text.lower()
    if semesters_left is not None or "student" in lower or "currently pursuing" in lower:
        return "student"
    if any(term in lower for term in ("new graduate", "new grad", "recent graduate")):
        return "new graduate"
    if years >= 5:
        return "experienced"
    if years >= 2:
        return "mid-level"
    if years > 0 or internship_years > 0:
        return "junior"
    if education:
        return "new graduate"
    return "candidate"


def _build_summary(snapshot: CandidateSnapshot) -> str:
    skill_text = ", ".join(sorted(snapshot.skills)[:8]) or "software engineering"
    education = snapshot.education or snapshot.career_stage.capitalize()
    if snapshot.years_experience <= 0:
        experience = "no confirmed professional experience"
    else:
        experience = f"{snapshot.years_experience:g}+ years of confirmed professional experience"
    semesters = (
        f", {snapshot.semesters_left} semesters remaining"
        if snapshot.semesters_left is not None
        else ""
    )
    return f"{education}{semesters}; {experience}; strongest visible skills: {skill_text}."


def _number_from_answer(value: str) -> float:
    match = re.search(r"\d+(?:\.\d+)?", value)
    if not match:
        return 0.0
    number = float(match.group(0))
    if "month" in value.lower():
        number /= 12
    return round(number, 1)


def _optional_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _phrase_pattern(term: str) -> str:
    return rf"(?<![a-z0-9]){re.escape(term).replace(r'\ ', r'\s+')}(?![a-z0-9])"


def _json_dict(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_int_list(value: str) -> list[int]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, int)]


def _education_rank(value: str) -> int:
    lower = value.lower()
    if "ph.d" in lower or "doctor" in lower:
        return 4
    if "m.sc" in lower or "master" in lower:
        return 3
    if "b.sc" in lower or "b.a" in lower or "bachelor" in lower:
        return 2
    return 1 if value else 0


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return output


def _now() -> datetime:
    return datetime.now(timezone.utc)
