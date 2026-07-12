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
    storage_path: str
    has_text: bool
    read_method: str = ""
    scanned_pdf_detected: bool = False
    ocr_attempted: bool = False
    ocr_confidence: float | None = None
    updated_at: datetime


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
    career_interests: list[str] = Field(default_factory=list)
    last_analyzed_at: datetime | None = None
    sources: list[ProfileSourceOut] = Field(default_factory=list)
    facts: list[ProfileFactOut] = Field(default_factory=list)
    questions: list[ClarificationQuestionOut] = Field(default_factory=list)


class ProfileSourcesIn(BaseModel):
    github_url: str = Field(default="", max_length=2000)
    linkedin_text: str = Field(default="", max_length=50000)
    manual_info: str = Field(default="", max_length=50000)


class ProfilePreferencesIn(BaseModel):
    career_interests: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("career_interests")
    @classmethod
    def validate_career_interests(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        invalid = [value for value in cleaned if value not in CAREER_INTEREST_SET]
        if invalid:
            raise ValueError(f"Unsupported career interest: {invalid[0]}")
        return cleaned


class ProfileFactPatchIn(BaseModel):
    value: str = Field(min_length=1, max_length=1000)
    review_status: Literal["pending", "approved", "rejected"] = "approved"


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


class ProfileAnalyzeResult(BaseModel):
    profile: ProfileOut
    generated_facts: int
    open_questions: int
