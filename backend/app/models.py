from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Index, UniqueConstraint, text
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
    recommendations_enabled: bool = Field(default=False, index=True)
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
    previous_status: str = ""
    status: str = Field(index=True)
    occurred_at: datetime = Field(default_factory=utc_now)
    source: str = Field(default="system", index=True)
    note: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class JobRequirementRevision(SQLModel, table=True):
    __tablename__ = "job_requirement_revisions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    original_requirements_json: str = "{}"
    corrected_requirements_json: str = "{}"
    changed_fields_json: str = "[]"
    matcher_version: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class JobScan(SQLModel, table=True):
    __tablename__ = "job_scans"
    __table_args__ = (
        Index(
            "job_scans_user_active_input_uq",
            "user_id",
            "input_hash",
            unique=True,
            sqlite_where=text(
                "status in ('queued', 'running', 'cancel_requested')"
            ),
            postgresql_where=text(
                "status in ('queued', 'running', 'cancel_requested')"
            ),
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    input_hash: str = Field(default="", index=True)
    payload_json: str = "{}"
    status: str = Field(default="queued", index=True)
    current_step: str = "queued"
    progress: int = 0
    result_job_id: Optional[int] = Field(default=None, foreign_key="jobs.id", index=True)
    trace_id: str = Field(default="", index=True)
    attempts: int = 0
    lease_token: str = Field(default="", index=True)
    error_code: str = ""
    error_message: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ExtractionMetric(SQLModel, table=True):
    __tablename__ = "extraction_metrics"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    workflow_type: str = Field(index=True)
    subject_type: str = Field(default="", index=True)
    subject_id: Optional[int] = Field(default=None, index=True)
    strategy: str = ""
    status: str = Field(default="succeeded", index=True)
    duration_ms: int = 0
    input_length: int = 0
    output_length: int = 0
    fallback_reason: str = ""
    counts_json: str = "{}"
    error_code: str = ""
    trace_id: str = Field(default="", index=True)
    created_at: datetime = Field(default_factory=utc_now)


class EvaluationExample(SQLModel, table=True):
    __tablename__ = "evaluation_examples"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    example_type: str = Field(index=True)
    subject_id: Optional[int] = Field(default=None, index=True)
    split: str = Field(default="train", index=True)
    label: str = Field(index=True)
    features_json: str = "{}"
    model_version: str = Field(default="", index=True)
    trace_id: str = Field(default="", index=True)
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
    source_name: str = Field(default="community", index=True)
    external_id: str = Field(default="", index=True)
    source_published_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = Field(default=None, index=True)
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
    materialized_job_id: Optional[int] = Field(default=None, foreign_key="jobs.id", index=True)
    score: float = 0.0
    fit_level: str = Field(default="Weak", index=True)
    confidence: float = 0.0
    career_fields_json: str = "[]"
    reasons_json: str = "[]"
    match_snapshot_json: str = "{}"
    model_version: str = Field(default="", index=True)
    status: str = Field(default="shadow_observation", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RecommendationEvent(SQLModel, table=True):
    __tablename__ = "recommendation_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "recommendation_id",
            "event_type",
            name="uq_recommendation_event_type",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    recommendation_id: int = Field(foreign_key="job_recommendations.id", index=True)
    catalog_job_id: int = Field(foreign_key="shared_job_catalog.id", index=True)
    materialized_job_id: Optional[int] = Field(default=None, foreign_key="jobs.id", index=True)
    event_type: str = Field(index=True)
    dismiss_reason: str = ""
    score: float = 0.0
    score_band: str = Field(index=True)
    career_field: str = Field(default="unknown", index=True)
    source_name: str = Field(default="community", index=True)
    model_version: str = Field(default="", index=True)
    created_at: datetime = Field(default_factory=utc_now)


class RecommendationFieldCalibration(SQLModel, table=True):
    __tablename__ = "recommendation_field_calibrations"

    career_field: str = Field(primary_key=True)
    minimum_score: float = 40.0
    sample_size: int = 0
    positive_count: int = 0
    negative_count: int = 0
    possible_sample_size: int = 0
    possible_positive_count: int = 0
    medium_sample_size: int = 0
    medium_positive_count: int = 0
    window_days: int = 90
    updated_at: datetime = Field(default_factory=utc_now)


class JobSourceRun(SQLModel, table=True):
    __tablename__ = "job_source_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    status: str = Field(default="running", index=True)
    records_seen: int = 0
    records_valid: int = 0
    created_count: int = 0
    updated_count: int = 0
    ignored_count: int = 0
    deactivated_count: int = 0
    error_code: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class JobDiscoveryBetaMember(SQLModel, table=True):
    __tablename__ = "job_discovery_beta_members"

    user_id: UUID = Field(primary_key=True)
    market_code: str = Field(default="IL", index=True)
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class JobNotificationPreference(SQLModel, table=True):
    __tablename__ = "job_notification_preferences"

    user_id: UUID = Field(primary_key=True)
    email_enabled: bool = Field(default=False, index=True)
    unsubscribed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class NotificationDelivery(SQLModel, table=True):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("recommendation_id", "channel", name="uq_notification_delivery_channel"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(index=True)
    recommendation_id: int = Field(foreign_key="job_recommendations.id", index=True)
    channel: str = Field(default="email", index=True)
    status: str = Field(default="queued", index=True)
    attempts: int = 0
    provider_message_id: str = ""
    error_code: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    sent_at: Optional[datetime] = None
