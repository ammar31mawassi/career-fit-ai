from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_profile_user_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    summary: str = ""
    status: str = Field(default="needs_cv", index=True)
    github_url: str = ""
    linkedin_text: str = ""
    manual_info: str = ""
    years_experience: float = 0.0
    onboarding_completed: bool = Field(default=False, index=True)
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileInterest(SQLModel, table=True):
    __tablename__ = "profile_interests"
    __table_args__ = (UniqueConstraint("profile_id", "interest", name="uq_profile_interest"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    interest: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)


class ProfileSource(SQLModel, table=True):
    __tablename__ = "profile_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    source_type: str = Field(index=True)
    title: str = ""
    storage_path: str = ""
    content_text: str = ""
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileFact(SQLModel, table=True):
    __tablename__ = "profile_facts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    source_id: Optional[int] = Field(default=None, foreign_key="profile_sources.id")
    fact_type: str = Field(index=True)
    value: str
    evidence: str = ""
    metadata_json: str = "{}"
    source_ids_json: str = "[]"
    support_count: int = 1
    extraction_key: str = Field(default="", index=True)
    confidence: float = 0.0
    user_approved: bool = False
    review_status: str = Field(default="pending", index=True)
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileFactFeedback(SQLModel, table=True):
    __tablename__ = "profile_fact_feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    fact_id: Optional[int] = Field(default=None, foreign_key="profile_facts.id", index=True)
    fact_type: str = Field(index=True)
    extraction_key: str = Field(default="", index=True)
    action: str = Field(index=True)
    original_value: str = ""
    corrected_value: str = ""
    source_ids_json: str = "[]"
    extractor_version: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class ClarificationQuestion(SQLModel, table=True):
    __tablename__ = "clarification_questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    field_key: str = Field(index=True)
    question: str
    answer: str = ""
    status: str = Field(default="open", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("user_id", "content_hash", name="uq_job_user_content_hash"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    content_hash: str = Field(index=True)
    source_url: str = ""
    company: str = Field(default="Unknown Company", index=True)
    role: str = Field(default="Unknown Role", index=True)
    location: str = ""
    description_text: str = ""
    source_title: str = ""
    source_confidence: float = 0.0
    application_link: str = ""
    requirements_json: str = "{}"
    status: str = Field(default="analyzed", index=True)
    error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class JobMatch(SQLModel, table=True):
    __tablename__ = "job_matches"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_job_match_user_job"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    score: float = 0.0
    fit_level: str = Field(default="Weak", index=True)
    confidence: float = 0.0
    status: str = Field(default="Lead", index=True)
    matched_evidence_json: str = "[]"
    missing_blockers_json: str = "[]"
    gaps_json: str = "[]"
    model_version: str = "fit-v1.0.0"
    ontology_version: str = "skills-v1.2.0"
    component_scores_json: str = "{}"
    applied_caps_json: str = "[]"
    feature_snapshot_json: str = "{}"
    analyzed_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ResumeAdvice(SQLModel, table=True):
    __tablename__ = "resume_advice"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_resume_advice_user_match"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    match_id: int = Field(foreign_key="job_matches.id", index=True)
    projects_json: str = "[]"
    skill_order_json: str = "[]"
    about_text: str = ""
    template_id: str = ""
    evidence_json: str = "[]"
    generated_at: datetime = Field(default_factory=utc_now)


class JobStatusEvent(SQLModel, table=True):
    __tablename__ = "job_status_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    match_id: int = Field(foreign_key="job_matches.id", index=True)
    status: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    workflow_type: str = Field(index=True)
    subject_type: str = Field(default="", index=True)
    subject_id: Optional[int] = Field(default=None, index=True)
    input_hash: str = Field(default="", index=True)
    status: str = Field(default="running", index=True)
    version: str = ""
    summary: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class AgentStep(SQLModel, table=True):
    __tablename__ = "agent_steps"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    run_id: int = Field(foreign_key="agent_runs.id", index=True)
    step_key: str = Field(index=True)
    title: str
    status: str = Field(default="running", index=True)
    attempt: int = 1
    progress: str = ""
    output_json: str = "{}"
    error: str = ""
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class SharedJobCatalog(SQLModel, table=True):
    __tablename__ = "shared_job_catalog"
    __table_args__ = (UniqueConstraint("content_hash", name="uq_shared_job_catalog_hash"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    content_hash: str = Field(index=True)
    source_url: str = ""
    application_link: str = ""
    company: str = Field(default="Unknown Company", index=True)
    role: str = Field(default="Unknown Role", index=True)
    location: str = ""
    description_text: str = ""
    requirements_json: str = "{}"
    domain: str = Field(default="", index=True)
    career_fields_json: str = "[]"
    source_confidence: float = 0.0
    first_seen_by: Optional[UUID] = Field(default=None, index=True)
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RecommendationRun(SQLModel, table=True):
    __tablename__ = "recommendation_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    catalog_job_id: int = Field(foreign_key="shared_job_catalog.id", index=True)
    source_user_id: Optional[UUID] = Field(default=None, index=True)
    status: str = Field(default="running", index=True)
    candidate_count: int = 0
    scored_count: int = 0
    strong_count: int = 0
    error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class JobRecommendation(SQLModel, table=True):
    __tablename__ = "job_recommendations"
    __table_args__ = (
        UniqueConstraint("user_id", "catalog_job_id", "model_version", name="uq_job_recommendation_version"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    catalog_job_id: int = Field(foreign_key="shared_job_catalog.id", index=True)
    score: float = 0.0
    fit_level: str = Field(default="Weak", index=True)
    confidence: float = 0.0
    career_fields_json: str = "[]"
    reasons_json: str = "[]"
    match_snapshot_json: str = "{}"
    model_version: str = Field(default="", index=True)
    status: str = Field(default="shadow", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
