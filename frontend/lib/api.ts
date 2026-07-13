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
  career_interests: string[];
  last_analyzed_at: string | null;
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
};

export type AccountExport = {
  exported_at: string;
  profile: Profile;
  sources: Array<{ source_type: string; title: string; content_text: string; updated_at: string }>;
  fact_feedback: Array<{ fact_type: string; action: string; original_value: string; corrected_value: string; created_at: string }>;
  jobs: TrackedJob[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";

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
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep generic error.
    }
    throw new Error(message);
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

export function saveProfilePreferences(careerInterests: string[]) {
  return request<Profile>("/api/profile/preferences", {
    method: "PUT",
    body: JSON.stringify({ career_interests: careerInterests })
  });
}

export function completeOnboarding() {
  return request<Profile>("/api/profile/onboarding/complete", { method: "POST" });
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

export function getJob(jobId: number) {
  return request<TrackedJob>(`/api/jobs/${jobId}`);
}

export function createJob(payload: JobCreate, signal?: AbortSignal) {
  return request<TrackedJob>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
    signal
  });
}

export function kickRecommendationWorker() {
  return request<{ processed: boolean }>("/api/recommendations/process-pending", {
    method: "POST",
    keepalive: true
  });
}

export function updateJobStatus(jobId: number, status: JobStatus) {
  return request<TrackedJob>(`/api/jobs/${jobId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status })
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
