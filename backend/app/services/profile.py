from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
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
    ClarificationQuestionOut,
    ProfileAnalyzeResult,
    ProfileFactOut,
    ProfileOut,
    ProfilePreferencesIn,
    ProfileSourceOut,
    ProfileSourcesIn,
)
from .ontology import canonical_skill, extract_skills, infer_domain, skill_domain
from .profile_extraction import (
    EXTRACTOR_VERSION,
    ExtractedFact,
    extract_profile_facts,
    extracted_fact_key,
    fact_key,
)
from .storage import load_private_file, save_private_file
from .text import PDF_PARSER_VERSION, read_pdf_text, safe_filename


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
    parsed_text = read_pdf_text(data)
    existing = _source_by_type(session, profile, "cv")
    source = existing or ProfileSource(user_id=user_id, profile_id=profile.id or 0, source_type="cv")
    source.title = cleaned_filename
    source.storage_path = storage_path
    source.content_text = parsed_text
    source.metadata_json = json.dumps({"filename": cleaned_filename, "chars": len(parsed_text), "parser_version": PDF_PARSER_VERSION})
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
    parsed_text = read_pdf_text(data)
    source = _source_by_type(session, profile, "linkedin_pdf") or ProfileSource(
        user_id=user_id,
        profile_id=profile.id or 0,
        source_type="linkedin_pdf",
    )
    source.title = cleaned_filename
    source.storage_path = storage_path
    source.content_text = parsed_text
    source.metadata_json = json.dumps({"filename": cleaned_filename, "chars": len(parsed_text), "parser_version": PDF_PARSER_VERSION})
    source.updated_at = _now()
    profile.linkedin_text = parsed_text[:50000]
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
    for interest in existing:
        session.delete(interest)
    for interest in payload.career_interests:
        session.add(
            ProfileInterest(
                user_id=user_id,
                profile_id=profile.id or 0,
                interest=interest,
            )
        )
    profile.updated_at = _now()
    session.add(profile)
    session.commit()
    return profile_output(session, user_id)


def complete_onboarding(session: Session, user_id: UUID) -> ProfileOut:
    profile = get_or_create_profile(session, user_id)
    if not _has_cv(session, profile):
        raise ValueError("Upload a CV before completing onboarding.")
    interests = list(
        session.exec(select(ProfileInterest).where(ProfileInterest.profile_id == profile.id)).all()
    )
    if not interests:
        raise ValueError("Choose at least one career interest.")
    if profile.status != "ready":
        # Completion is idempotent: if a write left the profile marked stale,
        # rebuild it once instead of trapping the user after the review screen.
        analyzed = analyze_profile(session, user_id)
        profile = get_or_create_profile(session, user_id)
        if analyzed.profile.status == "cv_unreadable":
            raise ValueError(
                "We couldn't read text from your CV. Upload a text-based PDF (not a scan) and analyze again."
            )
        if analyzed.profile.status != "ready":
            raise ValueError("Profile analysis did not finish. Review your CV and analyze again.")
    profile.onboarding_completed = True
    profile.updated_at = _now()
    session.add(profile)
    session.commit()
    return profile_output(session, user_id)


def analyze_profile(session: Session, user_id: UUID) -> ProfileAnalyzeResult:
    profile = get_or_create_profile(session, user_id)
    sources = _sources(session, profile)
    cv_sources = [source for source in sources if source.source_type == "cv"]
    if not cv_sources:
        profile.status = "needs_cv"
        profile.updated_at = _now()
        session.add(profile)
        session.commit()
        output = profile_output(session, user_id)
        return ProfileAnalyzeResult(profile=output, generated_facts=0, open_questions=len(output.questions))

    # Re-run older PDF parser versions before deciding that a CV is unreadable.
    _refresh_pdf_sources(session, sources)
    if not any(source.content_text.strip() for source in cv_sources):
        profile.status = "cv_unreadable"
        profile.updated_at = _now()
        session.add(profile)
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
        career_interests=[interest.interest for interest in interests],
        last_analyzed_at=profile.last_analyzed_at,
        sources=[
            ProfileSourceOut(
                id=source.id or 0,
                source_type=source.source_type,
                title=source.title,
                storage_path=source.storage_path,
                has_text=bool(source.content_text.strip()),
                updated_at=source.updated_at,
            )
            for source in sources
        ],
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
    session.flush()
    profile = session.get(Profile, fact.profile_id)
    if profile:
        _rebuild_profile_state(session, profile)
    session.commit()
    return profile_output(session, user_id)


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
    session.flush()
    _rebuild_profile_state(session, profile)
    session.commit()
    return profile_output(session, user_id)


def answer_question(session: Session, user_id: UUID, question_id: int, answer: str) -> ProfileOut:
    question = session.get(ClarificationQuestion, question_id)
    if not question or question.user_id != user_id:
        raise ValueError("Profile fact question not found.")
    profile = session.get(Profile, question.profile_id)
    if profile:
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
                    metadata_json=json.dumps({"evidence_type": "user_approved", "extractor_version": EXTRACTOR_VERSION}),
                )
            )
        if question.field_key == "years_experience":
            profile.years_experience = _number_from_answer(cleaned_answer)
    session.delete(question)
    session.flush()
    if profile:
        _rebuild_profile_state(session, profile)
    session.commit()
    return profile_output(session, user_id)


def _rebuild_profile_state(session: Session, profile: Profile) -> None:
    for question in session.exec(
        select(ClarificationQuestion).where(ClarificationQuestion.profile_id == profile.id)
    ).all():
        session.delete(question)
    session.flush()
    snapshot = candidate_snapshot(session, profile)
    profile.years_experience = snapshot.years_experience
    profile.summary = _build_summary(snapshot)
    profile.updated_at = _now()
    session.add(profile)
    _create_questions(session, profile, snapshot)


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
        parsed_text = read_pdf_text(data)
        if not parsed_text:
            continue
        source.content_text = parsed_text
        metadata.update({"chars": len(parsed_text), "parser_version": PDF_PARSER_VERSION})
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
        return github_url.strip()
    try:
        url = f"https://api.github.com/users/{urllib.parse.quote(username)}/repos?per_page=12&sort=updated"
        request = urllib.request.Request(url, headers={"User-Agent": "career-fit-ai"})
        with urllib.request.urlopen(request, timeout=8) as response:
            repos = json.loads(response.read().decode("utf-8"))
    except Exception:
        return f"GitHub profile: {github_url.strip()}"
    if not isinstance(repos, list):
        return f"GitHub profile: {github_url.strip()}"
    lines = [f"GitHub profile: {github_url.strip()}"]
    for repo in repos[:12]:
        if isinstance(repo, dict) and not repo.get("fork"):
            lines.append(
                "Project "
                + " ".join(str(repo.get(key) or "") for key in ("name", "description", "language"))
            )
    return "\n".join(lines)


def _github_username(github_url: str) -> str:
    value = github_url.strip().rstrip("/")
    if not value:
        return ""
    if "/" not in value:
        return re.sub(r"[^A-Za-z0-9-]", "", value)
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0] if parts else ""


def _extract_professional_years(text: str) -> float:
    lower = text.lower()
    patterns = (
        r"\b(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s+of\s+(?:professional|commercial|industry|software|engineering|work)\s+experience\b",
        r"\bprofessional\s+experience\s*[:\-]?\s*(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\b",
        r"\bexperience\s*[:\-]?\s*(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\b",
    )
    matches = [float(value) for pattern in patterns for value in re.findall(pattern, lower)]
    months = [
        float(value)
        for value in re.findall(
            r"\b(\d+)\+?\s*months?\s+of\s+(?:professional|commercial|industry|software|engineering|work)\s+experience\b",
            lower,
        )
    ]
    values = [*matches, *[month / 12 for month in months]]
    return round(max(values), 1) if values else 0.0


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
        "coursework": 0.55,
        "user_approved": 0.45,
        "self_reported": 0.4,
        "cv_mention": 0.35,
    }.get(evidence_type, 0.3)
    if approved:
        base = max(base, 0.5)
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
