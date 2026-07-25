from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .services.career_interests import CAREER_INTEREST_SET


JobStatus = Literal["Lead", "Applied", "Interview", "Rejected", "Withdrawn", "Offer"]
FitLevel = Literal["Strong", "Medium", "Weak"]


class ProfileSourceOut(BaseModel):
    id: int
    source_type: str
    title: str
    has_text: bool
    read_method: str = ""
    scanned_pdf_detected: bool = False
    ocr_attempted: bool = False
    ocr_confidence: float | None = None
    ocr_recommended: bool = False
    updated_at: datetime


class BrowserOcrPageIn(BaseModel):
    page_number: int = Field(ge=1, le=8)
    confidence: float = Field(ge=0, le=1)
    word_count: int = Field(default=0, ge=0, le=100000)


class BrowserOcrIn(BaseModel):
    text: str = Field(min_length=1, max_length=200000)
    confidence: float = Field(ge=0, le=1)
    engine: Literal["tesseract.js"] = "tesseract.js"
    pages: list[BrowserOcrPageIn] = Field(default_factory=list, max_length=8)


class ProfileFactOut(BaseModel):
    id: int
    fact_type: str
    value: str
    evidence: str
    confidence: float
    user_approved: bool
    review_status: Literal["pending", "approved", "rejected"] = "pending"
    support_count: int = 1
    source_ids: list[int] = Field(default_factory=list)
    source_id: int | None


class ClarificationQuestionOut(BaseModel):
    id: int
    field_key: str
    question: str
    answer: str
    status: str


class ProfileOut(BaseModel):
    id: int | None = None
    summary: str = ""
    status: str = "needs_cv"
    github_url: str = ""
    linkedin_text: str = ""
    manual_info: str = ""
    years_experience: float = 0.0
    onboarding_completed: bool = False
    recommendations_enabled: bool = False
    career_interests: list[str] = Field(default_factory=list)
    last_analyzed_at: datetime | None = None
    updated_at: datetime | None = None
    sources: list[ProfileSourceOut] = Field(default_factory=list)
    facts: list[ProfileFactOut] = Field(default_factory=list)
    questions: list[ClarificationQuestionOut] = Field(default_factory=list)


class ProfileSourcesIn(BaseModel):
    github_url: str = Field(default="", max_length=2000)
    linkedin_text: str = Field(default="", max_length=50000)
    manual_info: str = Field(default="", max_length=50000)


class ProfilePreferencesIn(BaseModel):
    career_interests: list[str] = Field(default_factory=list, max_length=25)
    recommendations_enabled: bool | None = None

    @field_validator("career_interests")
    @classmethod
    def validate_career_interests(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        invalid = [value for value in cleaned if value not in CAREER_INTEREST_SET]
        if invalid:
            raise ValueError(f"Unsupported career interest: {invalid[0]}")
        return cleaned


class OnboardingAnalyzeIn(ProfileSourcesIn):
    career_interests: list[str] = Field(min_length=1, max_length=25)

    @field_validator("career_interests")
    @classmethod
    def validate_career_interests(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        invalid = [value for value in cleaned if value not in CAREER_INTEREST_SET]
        if invalid:
            raise ValueError(f"Unsupported career interest: {invalid[0]}")
        return cleaned


class OnboardingCompleteIn(BaseModel):
    facts_decision: Literal["confirmed", "skipped"]
    approved_fact_ids: list[int] = Field(default_factory=list, max_length=250)
    rejected_fact_ids: list[int] = Field(default_factory=list, max_length=250)
    question_decision: Literal["answered", "skipped", "no_question"]
    question_id: int | None = Field(default=None, ge=1)
    question_answer: str = Field(default="", max_length=2000)

    @field_validator("approved_fact_ids", "rejected_fact_ids")
    @classmethod
    def unique_review_ids(cls, values: list[int]) -> list[int]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_review_decisions(self):
        approved = set(self.approved_fact_ids)
        rejected = set(self.rejected_fact_ids)
        if approved & rejected:
            raise ValueError("A profile fact cannot be both confirmed and rejected.")
        if self.facts_decision == "skipped" and (approved or rejected):
            raise ValueError("Skipped fact reviews cannot include fact decisions.")
        if self.question_decision == "answered":
            if self.question_id is None or not self.question_answer.strip():
                raise ValueError("Answer the selected clarification question before continuing.")
        elif self.question_decision == "skipped":
            if self.question_id is None:
                raise ValueError("Choose the clarification question to skip.")
            if self.question_answer.strip():
                raise ValueError("A skipped clarification question cannot include an answer.")
        elif self.question_id is not None or self.question_answer.strip():
            raise ValueError("No-question reviews cannot include a question or answer.")
        return self


class ProfileFactPatchIn(BaseModel):
    value: str = Field(min_length=1, max_length=1000)
    review_status: Literal["pending", "approved", "rejected"] = "approved"


class ProfileFactBulkReviewIn(BaseModel):
    fact_ids: list[int] = Field(min_length=1, max_length=100)
    review_status: Literal["approved", "rejected"]

    @field_validator("fact_ids")
    @classmethod
    def unique_fact_ids(cls, values: list[int]) -> list[int]:
        return list(dict.fromkeys(values))


class ProfileFactCreateIn(BaseModel):
    fact_type: Literal[
        "skill",
        "project",
        "experience",
        "education",
        "language",
        "location",
        "availability",
        "work_authorization",
        "semesters_left",
        "years_experience",
        "about_me",
    ]
    value: str = Field(min_length=1, max_length=1000)


class ClarificationAnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


class RequirementGroupModel(BaseModel):
    priority: str
    mode: str
    skills: list[str] = Field(default_factory=list)
    evidence: str = ""


class RequirementModel(BaseModel):
    must_have_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    all_skills: list[str] = Field(default_factory=list)
    min_years_experience: float = 0.0
    seniority: str = "unspecified"
    education: str = ""
    work_mode: str = ""
    domain: str = ""
    summary: str = ""
    languages: list[str] = Field(default_factory=list)
    location_requirement: str = ""
    work_authorization: str = ""
    availability: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    evidence_by_requirement: dict[str, str] = Field(default_factory=dict)
    ontology_version: str = "skills-v1.2.0"
    skill_groups: list[RequirementGroupModel] = Field(default_factory=list)
    experience_requirement_known: bool = False
    reader_version: str = ""
    extraction_completeness: float = 0.0


class ResumeAdviceOut(BaseModel):
    projects: list[str]
    skill_order: list[str]
    about_text: str
    template_id: str = ""
    evidence: list[str] = Field(default_factory=list)


class JobStatusEventOut(BaseModel):
    status: JobStatus
    created_at: datetime


class JobMatchOut(BaseModel):
    id: int
    score: float
    fit_level: FitLevel
    confidence: float
    status: JobStatus
    matched_evidence: list[str]
    missing_blockers: list[str]
    gaps: list[str]
    model_version: str = "fit-v1.0.0"
    ontology_version: str = "skills-v1.2.0"
    component_scores: dict[str, float] = Field(default_factory=dict)
    applied_caps: list[str] = Field(default_factory=list)
    status_history: list[JobStatusEventOut] = Field(default_factory=list)
    resume_advice: ResumeAdviceOut
    analyzed_at: datetime


class JobMatchSummaryOut(BaseModel):
    id: int
    score: float
    fit_level: FitLevel
    confidence: float
    status: JobStatus
    analyzed_at: datetime


class AgentStepOut(BaseModel):
    id: int
    step_key: str
    title: str
    status: str
    attempt: int = 1
    progress: str = ""
    output: dict[str, object] = Field(default_factory=dict)
    error: str = ""
    started_at: datetime
    completed_at: datetime | None = None


class AgentRunOut(BaseModel):
    id: int
    workflow_type: str
    subject_type: str = ""
    subject_id: int | None = None
    status: str
    version: str
    summary: str = ""
    error: str = ""
    created_at: datetime
    completed_at: datetime | None = None
    steps: list[AgentStepOut] = Field(default_factory=list)


class JobSummaryOut(BaseModel):
    id: int
    source_url: str
    company: str
    role: str
    location: str
    source_confidence: float
    application_link: str
    status: str
    error: str
    created_at: datetime
    updated_at: datetime
    requirement_summary: str = ""
    top_skills: list[str] = Field(default_factory=list)
    min_years_experience: float = 0.0
    extraction_completeness: float = 0.0
    primary_signal: str = ""
    match: JobMatchSummaryOut | None = None


class JobOut(BaseModel):
    id: int
    source_url: str
    company: str
    role: str
    location: str
    description_text: str
    source_title: str
    source_confidence: float
    application_link: str
    status: str
    error: str
    created_at: datetime
    updated_at: datetime
    requirements: RequirementModel
    match: JobMatchOut | None
    agent_run: AgentRunOut | None = None


class WorkspaceBootstrapOut(BaseModel):
    user_id: str
    profile: ProfileOut
    jobs: list[JobSummaryOut] = Field(default_factory=list)
    jobs_next_cursor: str | None = None
    jobs_watermark: datetime | None = None


class AccountSourceExportOut(BaseModel):
    source_type: str
    title: str
    content_text: str
    updated_at: datetime


class AccountFeedbackExportOut(BaseModel):
    fact_type: str
    action: str
    original_value: str
    corrected_value: str
    created_at: datetime


class AccountRequirementFeedbackOut(BaseModel):
    job_id: int
    original_requirements: dict[str, object] = Field(default_factory=dict)
    corrected_requirements: dict[str, object] = Field(default_factory=dict)
    changed_fields: list[str] = Field(default_factory=list)
    created_at: datetime


class AccountNotificationPreferenceOut(BaseModel):
    email_enabled: bool = False
    unsubscribed_at: datetime | None = None


class AccountNotificationDeliveryOut(BaseModel):
    recommendation_id: int
    channel: str
    status: str
    attempts: int
    created_at: datetime
    sent_at: datetime | None = None


class AccountRecommendationEventOut(BaseModel):
    recommendation_id: int
    event_type: str
    dismiss_reason: str
    score: float
    score_band: str
    career_field: str
    source_name: str
    model_version: str
    created_at: datetime


class AccountExportOut(BaseModel):
    exported_at: datetime
    profile: ProfileOut
    sources: list[AccountSourceExportOut] = Field(default_factory=list)
    fact_feedback: list[AccountFeedbackExportOut] = Field(default_factory=list)
    requirement_feedback: list[AccountRequirementFeedbackOut] = Field(default_factory=list)
    discovery_market: str = ""
    notification_preference: AccountNotificationPreferenceOut | None = None
    notification_deliveries: list[AccountNotificationDeliveryOut] = Field(default_factory=list)
    recommendation_feedback: list[AccountRecommendationEventOut] = Field(default_factory=list)
    jobs: list[JobOut] = Field(default_factory=list)


class AccountDeleteIn(BaseModel):
    confirmation: Literal["DELETE"]


class JobCreateIn(BaseModel):
    source_url: str = Field(default="", max_length=2000)
    company: str = Field(default="", max_length=160)
    role: str = Field(default="", max_length=220)
    description_text: str = Field(default="", max_length=70000)

    @model_validator(mode="after")
    def require_source(self):
        if not self.source_url.strip() and not self.description_text.strip():
            raise ValueError("Provide a job URL or paste the job description.")
        return self


class JobStatusPatchIn(BaseModel):
    status: JobStatus


class JobRequirementsReviewIn(BaseModel):
    must_have_skills: list[str] = Field(default_factory=list, max_length=50)
    preferred_skills: list[str] = Field(default_factory=list, max_length=50)
    nice_to_have_skills: list[str] = Field(default_factory=list, max_length=50)
    min_years_experience: float = Field(default=0, ge=0, le=50)
    experience_requirement_known: bool = False
    seniority: str = Field(default="unspecified", max_length=80)
    education: str = Field(default="", max_length=500)
    work_mode: str = Field(default="", max_length=120)
    domain: str = Field(default="", max_length=160)
    location_requirement: str = Field(default="", max_length=500)

    @field_validator("must_have_skills", "preferred_skills", "nice_to_have_skills")
    @classmethod
    def clean_requirement_skills(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))


class JobScanOut(BaseModel):
    id: int
    status: Literal["queued", "running", "succeeded", "failed", "cancel_requested", "cancelled"]
    current_step: str
    progress: int
    result_job_id: int | None = None
    trace_id: str
    error_code: str = ""
    error_message: str = ""
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    result_job: JobOut | None = None


class JobSummaryPageOut(BaseModel):
    items: list[JobSummaryOut] = Field(default_factory=list)
    next_cursor: str | None = None
    watermark: datetime | None = None


class JobRecommendationOut(BaseModel):
    id: int
    catalog_job_id: int
    source_name: str = "community"
    source_url: str
    application_link: str
    company: str
    role: str
    location: str
    score: float
    fit_level: FitLevel
    confidence: float
    career_fields: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime


class JobRecommendationPatchIn(BaseModel):
    status: Literal["dismissed", "saved"]
    dismiss_reason: Literal[
        "too_senior",
        "wrong_field",
        "wrong_location",
        "missing_skills",
        "employment_type",
        "not_interested",
        "other",
    ] | None = None

    @model_validator(mode="after")
    def validate_dismiss_reason(self):
        if self.status == "dismissed" and self.dismiss_reason is None:
            raise ValueError("Choose why this recommendation is not suitable.")
        if self.status != "dismissed" and self.dismiss_reason is not None:
            raise ValueError("Dismiss reasons are only accepted for dismissed recommendations.")
        return self


class JobRecommendationEventIn(BaseModel):
    event_type: Literal["viewed"]


class JobRecommendationActionOut(BaseModel):
    recommendation: JobRecommendationOut
    job: JobOut | None = None


class NotificationPreferenceOut(BaseModel):
    eligible: bool = False
    delivery_available: bool = False
    email_enabled: bool = False


class NotificationPreferenceIn(BaseModel):
    email_enabled: bool


class ProfileAnalyzeResult(BaseModel):
    profile: ProfileOut
    generated_facts: int
    open_questions: int
