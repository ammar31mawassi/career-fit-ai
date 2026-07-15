export type ProfileSource = {
  id: number;
  source_type: string;
  title: string;
  has_text: boolean;
  read_method: string;
  scanned_pdf_detected: boolean;
  ocr_attempted: boolean;
  ocr_confidence: number | null;
  ocr_recommended: boolean;
  updated_at: string;
};

export type ProfileFact = {
  id: number;
  fact_type: string;
  value: string;
  evidence: string;
  confidence: number;
  user_approved: boolean;
  review_status: "pending" | "approved" | "rejected";
  support_count: number;
  source_ids: number[];
  source_id: number | null;
};

export type ClarificationQuestion = {
  id: number;
  field_key: string;
  question: string;
  answer: string;
  status: string;
};

export type Profile = {
  id: number | null;
  summary: string;
  status: string;
  github_url: string;
  linkedin_text: string;
  manual_info: string;
  years_experience: number;
  onboarding_completed: boolean;
  recommendations_enabled: boolean;
  career_interests: string[];
  last_analyzed_at: string | null;
  updated_at: string | null;
  sources: ProfileSource[];
  facts: ProfileFact[];
  questions: ClarificationQuestion[];
};

export type ResumeAdvice = {
  projects: string[];
  skill_order: string[];
  about_text: string;
  template_id: string;
  evidence: string[];
};

export type JobStatus = "Lead" | "Applied" | "Interview" | "Rejected" | "Withdrawn" | "Offer";

export type JobMatch = {
  id: number;
  score: number;
  fit_level: "Strong" | "Medium" | "Weak";
  confidence: number;
  status: JobStatus;
  matched_evidence: string[];
  missing_blockers: string[];
  gaps: string[];
  model_version: string;
  ontology_version: string;
  component_scores: Record<string, number>;
  applied_caps: string[];
  status_history: Array<{ status: JobStatus; created_at: string }>;
  resume_advice: ResumeAdvice;
  analyzed_at: string;
};

export type JobMatchSummary = {
  id: number;
  score: number;
  fit_level: "Strong" | "Medium" | "Weak";
  confidence: number;
  status: JobStatus;
  analyzed_at: string;
};

export type AgentStep = {
  id: number;
  step_key: string;
  title: string;
  status: string;
  attempt: number;
  progress: string;
  output: Record<string, unknown>;
  error: string;
  started_at: string;
  completed_at: string | null;
};

export type AgentRun = {
  id: number;
  workflow_type: string;
  subject_type: string;
  subject_id: number | null;
  status: string;
  version: string;
  summary: string;
  error: string;
  created_at: string;
  completed_at: string | null;
  steps: AgentStep[];
};

export type JobRequirements = {
  must_have_skills: string[];
  preferred_skills: string[];
  nice_to_have_skills: string[];
  all_skills: string[];
  min_years_experience: number;
  seniority: string;
  education: string;
  work_mode: string;
  domain: string;
  summary: string;
  languages: string[];
  location_requirement: string;
  work_authorization: string;
  availability: string;
  responsibilities: string[];
  evidence_by_requirement: Record<string, string>;
  ontology_version: string;
  skill_groups: Array<{
    priority: string;
    mode: string;
    skills: string[];
    evidence: string;
  }>;
  experience_requirement_known: boolean;
  reader_version: string;
  extraction_completeness: number;
};

export type TrackedJobSummary = {
  id: number;
  source_url: string;
  company: string;
  role: string;
  location: string;
  source_confidence: number;
  application_link: string;
  status: string;
  error: string;
  created_at: string;
  updated_at: string;
  requirement_summary: string;
  top_skills: string[];
  min_years_experience: number;
  extraction_completeness: number;
  primary_signal: string;
  match: JobMatchSummary | null;
};

export type TrackedJob = {
  id: number;
  source_url: string;
  company: string;
  role: string;
  location: string;
  description_text: string;
  source_title: string;
  source_confidence: number;
  application_link: string;
  status: string;
  error: string;
  created_at: string;
  updated_at: string;
  requirements: JobRequirements;
  match: JobMatch | null;
  agent_run: AgentRun | null;
};

export type JobCreate = {
  source_url: string;
  company: string;
  role: string;
  description_text: string;
};

export type ProfileAnalyzeResult = {
  profile: Profile;
  generated_facts: number;
  open_questions: number;
};

export type WorkspaceBootstrap = {
  user_id: string;
  profile: Profile;
  jobs: TrackedJobSummary[];
  jobs_next_cursor: string | null;
  jobs_watermark: string | null;
};

export type JobScan = {
  id: number;
  status: "queued" | "running" | "succeeded" | "failed" | "cancel_requested" | "cancelled";
  current_step: string;
  progress: number;
  result_job_id: number | null;
  trace_id: string;
  error_code: string;
  error_message: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  result_job: TrackedJob | null;
};

export type JobSummaryPage = {
  items: TrackedJobSummary[];
  next_cursor: string | null;
  watermark: string | null;
};

export type JobRecommendation = {
  id: number;
  catalog_job_id: number;
  source_url: string;
  application_link: string;
  company: string;
  role: string;
  location: string;
  score: number;
  fit_level: "Strong" | "Medium" | "Weak";
  confidence: number;
  career_fields: string[];
  reasons: string[];
  status: string;
  created_at: string;
};

export type JobRequirementsReview = Pick<JobRequirements,
  "must_have_skills" | "preferred_skills" | "nice_to_have_skills" |
  "min_years_experience" | "experience_requirement_known" | "seniority" |
  "education" | "work_mode" | "domain" | "location_requirement"
>;

export type AccountExport = {
  exported_at: string;
  profile: Profile;
  sources: Array<{ source_type: string; title: string; content_text: string; updated_at: string }>;
  fact_feedback: Array<{ fact_type: string; action: string; original_value: string; corrected_value: string; created_at: string }>;
  requirement_feedback: Array<{ job_id: number; original_requirements: Record<string, unknown>; corrected_requirements: Record<string, unknown>; changed_fields: string[]; created_at: string }>;
  jobs: TrackedJob[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";

export class ApiError extends Error {
  constructor(message: string, public status: number, public code = "", public traceId = "") {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    let code = "";
    let traceId = response.headers.get("x-trace-id") ?? "";
    try {
      const body = await response.json() as { detail?: string | { message?: string }; code?: string; trace_id?: string };
      message = typeof body.detail === "string" ? body.detail : body.detail?.message ?? message;
      code = body.code ?? "";
      traceId = body.trace_id ?? traceId;
    } catch {
      // Keep generic error.
    }
    if (traceId && response.status >= 500) message = `${message} Support code: ${traceId.slice(0, 12)}.`;
    throw new ApiError(message, response.status, code, traceId);
  }
  return response.json() as Promise<T>;
}

async function requestEmpty(path: string, options?: RequestInit): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(body.detail ?? `Request failed with ${response.status}`);
  }
}

export function getProfile() {
  return request<Profile>("/api/profile");
}

export function getWorkspaceBootstrap() {
  return request<WorkspaceBootstrap>("/api/workspace/bootstrap");
}

export function getAccountExport() {
  return request<AccountExport>("/api/account/export");
}

export function deleteCareerFitAccount() {
  return requestEmpty("/api/account", {
    method: "DELETE",
    body: JSON.stringify({ confirmation: "DELETE" })
  });
}

export function uploadCv(file: File) {
  const body = new FormData();
  body.set("file", file);
  return request<Profile>("/api/profile/cv", { method: "POST", body });
}

export function saveBrowserOcr(payload: {
  text: string;
  confidence: number;
  engine: "tesseract.js";
  pages: Array<{ page_number: number; confidence: number; word_count: number }>;
}) {
  return request<Profile>("/api/profile/cv/browser-ocr", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function uploadLinkedInPdf(file: File) {
  const body = new FormData();
  body.set("file", file);
  return request<Profile>("/api/profile/linkedin-pdf", { method: "POST", body });
}

export function saveProfileSources(payload: { github_url: string; linkedin_text: string; manual_info: string }) {
  return request<Profile>("/api/profile/sources", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function saveProfilePreferences(careerInterests: string[], recommendationsEnabled?: boolean) {
  return request<Profile>("/api/profile/preferences", {
    method: "PUT",
    body: JSON.stringify({
      career_interests: careerInterests,
      ...(recommendationsEnabled === undefined ? {} : { recommendations_enabled: recommendationsEnabled })
    })
  });
}

export function completeOnboarding() {
  return request<Profile>("/api/profile/onboarding/complete", { method: "POST" });
}

export function analyzeOnboardingProfile(payload: {
  github_url: string;
  linkedin_text: string;
  manual_info: string;
  career_interests: string[];
}) {
  return request<ProfileAnalyzeResult>("/api/profile/onboarding/analyze", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function analyzeProfile() {
  return request<ProfileAnalyzeResult>("/api/profile/analyze", { method: "POST" });
}

export function updateProfileFact(factId: number, value: string, reviewStatus: ProfileFact["review_status"] = "approved") {
  return request<Profile>(`/api/profile/facts/${factId}`, {
    method: "PATCH",
    body: JSON.stringify({ value, review_status: reviewStatus })
  });
}

export function bulkUpdateProfileFacts(factIds: number[], reviewStatus: "approved" | "rejected") {
  return request<Profile>("/api/profile/facts", {
    method: "PATCH",
    body: JSON.stringify({ fact_ids: factIds, review_status: reviewStatus })
  });
}

export function addProfileFact(factType: string, value: string) {
  return request<Profile>("/api/profile/facts", {
    method: "POST",
    body: JSON.stringify({ fact_type: factType, value })
  });
}

export function answerProfileQuestion(questionId: number, answer: string) {
  return request<Profile>(`/api/profile/questions/${questionId}`, {
    method: "PATCH",
    body: JSON.stringify({ answer })
  });
}

export function getJobs(query = "") {
  const suffix = query.trim() ? `?query=${encodeURIComponent(query.trim())}` : "";
  return request<TrackedJob[]>(`/api/jobs${suffix}`);
}

export function getJobSummaries(query = "") {
  const suffix = query.trim() ? `?query=${encodeURIComponent(query.trim())}` : "";
  return request<TrackedJobSummary[]>(`/api/jobs/summary${suffix}`);
}

export function getJobSummaryPage(cursor = "", limit = 30) {
  const parameters = new URLSearchParams({ limit: String(limit) });
  if (cursor) parameters.set("cursor", cursor);
  return request<JobSummaryPage>(`/api/jobs/summary-page?${parameters.toString()}`);
}

export function getJob(jobId: number) {
  return request<TrackedJob>(`/api/jobs/${jobId}`);
}

export function createJobScan(payload: JobCreate, signal?: AbortSignal) {
  return request<JobScan>("/api/job-scans", {
    method: "POST",
    body: JSON.stringify(payload),
    signal
  });
}

export function processJobScan(scanId: number, signal?: AbortSignal) {
  return request<JobScan>(`/api/job-scans/${scanId}/process`, { method: "POST", signal });
}

export function getJobScan(scanId: number) {
  return request<JobScan>(`/api/job-scans/${scanId}`);
}

export function cancelJobScan(scanId: number) {
  return request<JobScan>(`/api/job-scans/${scanId}`, { method: "DELETE" });
}

export function getRecommendations() {
  return request<JobRecommendation[]>("/api/recommendations");
}

export function updateRecommendation(recommendationId: number, status: "dismissed" | "saved") {
  return request<{ recommendation: JobRecommendation; job: TrackedJob | null }>(`/api/recommendations/${recommendationId}`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export function updateJobStatus(jobId: number, status: JobStatus) {
  return request<TrackedJob>(`/api/jobs/${jobId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export function rematchJob(jobId: number) {
  return request<TrackedJob>(`/api/jobs/${jobId}/rematch`, { method: "POST" });
}

export function reviewJobRequirements(jobId: number, payload: JobRequirementsReview) {
  return request<TrackedJob>(`/api/jobs/${jobId}/requirements`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function toJobSummary(job: TrackedJob): TrackedJobSummary {
  const missing = job.match?.missing_blockers[0];
  const gap = job.match?.gaps[0];
  return {
    id: job.id,
    source_url: job.source_url,
    company: job.company,
    role: job.role,
    location: job.location,
    source_confidence: job.source_confidence,
    application_link: job.application_link,
    status: job.status,
    error: job.error,
    created_at: job.created_at,
    updated_at: job.updated_at,
    requirement_summary: job.requirements.summary,
    top_skills: [
      ...job.requirements.must_have_skills,
      ...job.requirements.preferred_skills,
      ...job.requirements.nice_to_have_skills
    ].filter((skill, index, list) => skill && list.findIndex((candidate) => candidate.toLowerCase() === skill.toLowerCase()) === index).slice(0, 7),
    min_years_experience: job.requirements.min_years_experience,
    extraction_completeness: job.requirements.extraction_completeness,
    primary_signal: missing || gap || job.error || job.requirements.summary,
    match: job.match
      ? {
          id: job.match.id,
          score: job.match.score,
          fit_level: job.match.fit_level,
          confidence: job.match.confidence,
          status: job.match.status,
          analyzed_at: job.match.analyzed_at
        }
      : null
  };
}

export function formatDate(value: string | null) {
  if (!value) return "Not yet";
  return new Date(value).toLocaleDateString();
}
