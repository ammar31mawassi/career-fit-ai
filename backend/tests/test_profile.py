from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from uuid import UUID

from app.models import ClarificationQuestion, Profile, ProfileFactFeedback, ProfileSource
from app.schemas import ProfilePreferencesIn, ProfileSourcesIn
from app.services.profile import (
    add_fact,
    analyze_profile,
    answer_question,
    candidate_snapshot,
    complete_onboarding,
    patch_fact,
    update_profile_sources,
    update_profile_preferences,
)


USER_ID = UUID("00000000-0000-0000-0000-000000000201")
STUDENT_ID = UUID("00000000-0000-0000-0000-000000000202")
OLDER_ID = UUID("00000000-0000-0000-0000-000000000203")
RECENT_ID = UUID("00000000-0000-0000-0000-000000000204")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def test_cv_is_required_before_profile_is_ready():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        result = analyze_profile(session, USER_ID)
        profile = session.exec(select(Profile).where(Profile.user_id == USER_ID)).one()

    assert result.profile.status == "needs_cv"
    assert profile.status == "needs_cv"


def test_optional_sources_do_not_replace_required_cv():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        result = update_profile_sources(
            session,
            USER_ID,
            ProfileSourcesIn(
                github_url="https://github.com/example",
                linkedin_text="Computer Science student with Python and React.",
                manual_info="Interested in backend roles.",
            ),
        )

    assert result.status == "needs_cv"
    assert result.github_url == "https://github.com/example"


def test_onboarding_requires_cv_and_supported_career_interest():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        update_profile_preferences(
            session,
            USER_ID,
            ProfilePreferencesIn(career_interests=["Software Engineering"]),
        )
        with pytest.raises(ValueError, match="Upload a CV"):
            complete_onboarding(session, USER_ID)

    with pytest.raises(ValueError, match="Unsupported career interest"):
        ProfilePreferencesIn(career_interests=["Professional Wizard"])


def test_analyzed_profile_can_complete_onboarding_with_interests():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                content_text="B.Sc. Computer Science student. Skills: Python, SQL, React.",
            )
        )
        session.commit()
        analyze_profile(session, USER_ID)
        update_profile_preferences(
            session,
            USER_ID,
            ProfilePreferencesIn(
                career_interests=["Software Engineering", "AI, Data Science, ML & Algorithms"]
            ),
        )
        completed = complete_onboarding(session, USER_ID)

    assert completed.onboarding_completed is True
    assert completed.career_interests == [
        "AI, Data Science, ML & Algorithms",
        "Software Engineering",
    ]


def test_completion_recovers_a_stale_profile_after_cv_upload():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                content_text="Computer Science student. Skills: Python, SQL, React.",
            )
        )
        session.commit()
        update_profile_preferences(
            session,
            USER_ID,
            ProfilePreferencesIn(career_interests=["Software Engineering"]),
        )

        completed = complete_onboarding(session, USER_ID)

    assert completed.status == "ready"
    assert completed.last_analyzed_at is not None
    assert completed.onboarding_completed is True


def test_unreadable_cv_is_reported_instead_of_showing_ready():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="scanned-cv.pdf",
                content_text="",
            )
        )
        session.commit()
        update_profile_preferences(
            session,
            USER_ID,
            ProfilePreferencesIn(career_interests=["Software Engineering"]),
        )

        analyzed = analyze_profile(session, USER_ID)
        with pytest.raises(ValueError, match="couldn't read text"):
            complete_onboarding(session, USER_ID)

    assert analyzed.profile.status == "cv_unreadable"
    assert analyzed.profile.onboarding_completed is False


def test_profile_analysis_extracts_facts_and_questions_from_cv():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                content_text=(
                    "B.Sc. in Computer Science. Built an AI Job Tracker project using Python, "
                    "FastAPI, React, SQL, and GitHub. Developed a C++ concurrent robotics project."
                ),
            )
        )
        session.commit()

        result = analyze_profile(session, USER_ID)
        questions = session.exec(select(ClarificationQuestion)).all()

    assert result.profile.status == "ready"
    assert result.generated_facts >= 5
    assert any(fact.fact_type == "skill" and fact.value == "python" for fact in result.profile.facts)
    assert any(fact.fact_type == "project" for fact in result.profile.facts)
    assert any(question.field_key == "years_experience" for question in questions)


def test_student_semesters_are_extracted_without_counting_projects_as_work_experience():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=STUDENT_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=STUDENT_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                content_text=(
                    "Computer Science student with 2 semesters remaining. "
                    "Built a Python FastAPI project over 2 years using PostgreSQL."
                ),
            )
        )
        session.commit()
        result = analyze_profile(session, STUDENT_ID)

    assert result.profile.years_experience == 0
    assert any(fact.fact_type == "semesters_left" and fact.value == "2" for fact in result.profile.facts)


def test_recency_affects_evidence_but_protected_text_does_not_become_a_feature():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        strengths = []
        for user_id, year, protected in (
            (OLDER_ID, 2018, ""),
            (RECENT_ID, 2025, "Age 22, male. "),
        ):
            profile = Profile(user_id=user_id, status="needs_analysis")
            session.add(profile)
            session.commit()
            session.refresh(profile)
            session.add(
                ProfileSource(
                    user_id=user_id,
                    profile_id=profile.id or 0,
                    source_type="cv",
                    title="cv.pdf",
                    content_text=f"{protected}Built a Python backend project in {year}.",
                )
            )
            session.commit()
            result = analyze_profile(session, user_id)
            session.refresh(profile)
            strengths.append(candidate_snapshot(session, profile).skill_evidence["python"].strength)
            assert not any(fact.fact_type in {"age", "gender"} for fact in result.profile.facts)

    assert strengths[1] > strengths[0]


def test_duplicate_facts_are_merged_and_corroboration_raises_confidence():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add_all(
            [
                ProfileSource(
                    user_id=USER_ID,
                    profile_id=profile.id or 0,
                    source_type="cv",
                    title="cv.pdf",
                    content_text="SKILLS\nPython\nEDUCATION\nB.Sc. in Computer Science",
                ),
                ProfileSource(
                    user_id=USER_ID,
                    profile_id=profile.id or 0,
                    source_type="linkedin_pdf",
                    title="linkedin.pdf",
                    content_text="Top Skills\nPython\nEducation\nBachelor of Science, Computer Science",
                ),
            ]
        )
        session.commit()
        result = analyze_profile(session, USER_ID)

    python_facts = [fact for fact in result.profile.facts if fact.fact_type == "skill" and fact.value == "python"]
    education_facts = [fact for fact in result.profile.facts if fact.fact_type == "education"]
    assert len(python_facts) == 1
    assert python_facts[0].support_count == 2
    assert python_facts[0].confidence > 0.66
    assert len(education_facts) == 1
    assert education_facts[0].support_count == 2


def test_near_duplicate_project_names_and_experience_titles_are_reconciled():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add_all(
            [
                ProfileSource(
                    user_id=USER_ID,
                    profile_id=profile.id or 0,
                    source_type="cv",
                    title="cv.pdf",
                    content_text=(
                        "B.Sc. in Computer Science\nWORK EXPERIENCE\n10.2025 – Present\n"
                        "Teaching Assistant — Intro to Computer Science\nPROJECTS\nThe Traveling Fan\n"
                        "Built a Python genetic-algorithm tool for football itineraries."
                    ),
                ),
                ProfileSource(
                    user_id=USER_ID,
                    profile_id=profile.id or 0,
                    source_type="linkedin_pdf",
                    title="linkedin.pdf",
                    content_text="Experience\nTeaching Assistant\nOctober 2025 - Present",
                ),
                ProfileSource(
                    user_id=USER_ID,
                    profile_id=profile.id or 0,
                    source_type="github",
                    title="github",
                    content_text="Project Traveling_Fan Python genetic-algorithm visualizer for stadium travel routes.",
                ),
            ]
        )
        session.commit()
        result = analyze_profile(session, USER_ID)

    projects = [fact for fact in result.profile.facts if fact.fact_type == "project"]
    experiences = [fact for fact in result.profile.facts if fact.fact_type == "experience"]
    assert len(projects) == 1
    assert projects[0].support_count == 2
    assert projects[0].value.startswith("The Traveling Fan")
    assert len(experiences) == 1
    assert experiences[0].support_count == 2


def test_soft_skills_are_extracted_without_turning_profile_text_into_projects():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                content_text=(
                    "B.A. in Management Information Systems\n"
                    "Skills\nJava\nHigh management skills\nProblem solving\nLeadership\nTeamwork\n"
                    "Profile\nExperienced in leading academic and personal projects.\n"
                    "Professional Experience\n2022: Secretary in the Accounting Department"
                ),
            )
        )
        session.commit()
        result = analyze_profile(session, USER_ID)

    skills = {fact.value for fact in result.profile.facts if fact.fact_type == "skill"}
    projects = [fact.value for fact in result.profile.facts if fact.fact_type == "project"]
    assert {"java", "management", "problem solving", "leadership", "teamwork"} <= skills
    assert projects == []


def test_section_headers_are_not_projects_and_java_is_not_inferred_from_javascript():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                content_text=(
                    "B.Sc. in Computer Science\nWORK EXPERIENCE\nPROJECTS\n"
                    "Web Dashboard\nJavaScript, React\nBuilt a dashboard for students."
                ),
            )
        )
        session.commit()
        result = analyze_profile(session, USER_ID)

    skills = {fact.value for fact in result.profile.facts if fact.fact_type == "skill"}
    projects = [fact.value for fact in result.profile.facts if fact.fact_type == "project"]
    assert "javascript" in skills
    assert "java" not in skills
    assert all(value.lower() not in {"experience", "projects", "work experience projects"} for value in projects)
    assert any(value.startswith("Web Dashboard:") for value in projects)


def test_rejected_fact_is_excluded_from_matching_and_feedback_is_saved():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                content_text="B.Sc. in Computer Science\nSkills\nPython\nJava",
            )
        )
        session.commit()
        result = analyze_profile(session, USER_ID)
        java = next(fact for fact in result.profile.facts if fact.fact_type == "skill" and fact.value == "java")
        updated = patch_fact(session, USER_ID, java.id, java.value, "rejected")
        session.refresh(profile)
        snapshot = candidate_snapshot(session, profile)
        feedback = session.exec(select(ProfileFactFeedback)).all()

    assert "java" not in snapshot.skills
    assert "python" in snapshot.skills
    assert "java" not in updated.summary
    assert feedback[-1].action == "rejected"


def test_answered_questions_disappear_and_manual_facts_refresh_questions():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Profile(user_id=USER_ID, status="needs_analysis")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            ProfileSource(
                user_id=USER_ID,
                profile_id=profile.id or 0,
                source_type="cv",
                title="cv.pdf",
                content_text="B.Sc. in Computer Science",
            )
        )
        session.commit()
        analyzed = analyze_profile(session, USER_ID)
        location = next(question for question in analyzed.profile.questions if question.field_key == "location")
        answered = answer_question(session, USER_ID, location.id, "Haifa, Israel")
        experience = next(question for question in answered.questions if question.field_key == "years_experience")
        answered = answer_question(session, USER_ID, experience.id, "0 years of professional experience")
        added = None
        for skill in ("Python", "Java", "SQL", "Docker", "Git"):
            added = add_fact(session, USER_ID, "skill", skill)
        feedback = session.exec(select(ProfileFactFeedback)).all()

    assert added is not None
    assert all(question.field_key != "location" for question in answered.questions)
    assert all(question.field_key != "years_experience" for question in answered.questions)
    assert all(question.field_key != "skill" for question in added.questions)
    assert any(fact.fact_type == "skill" and fact.value == "python" for fact in added.facts)
    assert feedback[-1].action == "manually_added"
