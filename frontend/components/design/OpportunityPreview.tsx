"use client";

import { useMemo, useState, type FormEvent } from "react";
import { Search, Sparkles } from "lucide-react";
import { JobScanner } from "@/components/home/JobScanner";
import { JobSummaryCard } from "@/components/home/JobSummaryCard";
import { OpportunityInspector } from "@/components/home/OpportunityInspector";
import type { JobCreate, JobMatchSummary, TrackedJob, TrackedJobSummary } from "@/lib/api";

const previewMatch: JobMatchSummary = {
  id: 101,
  score: 87,
  fit_level: "Strong",
  confidence: .92,
  status: "Lead",
  analyzed_at: "2026-07-17T09:00:00.000Z"
};

const previewJobs: TrackedJobSummary[] = [
  summary(1, "Northstar Labs", "Senior Frontend Engineer", 87, "Strong", "Remote"),
  summary(2, "Clearline Health", "Full Stack Engineer", 74, "Strong", "Hybrid"),
  summary(3, "Atlas Systems", "Frontend Engineer", 62, "Medium", "Remote"),
  summary(4, "Lumina", "Staff UI Engineer", 48, "Weak", "London"),
  summary(5, "Brightline", "Web Engineer", 36, "Weak", "Remote")
];

const previewJob: TrackedJob = {
  id: 1,
  source_url: "https://northstar.example/jobs/frontend",
  company: "Northstar Labs",
  role: "Senior Frontend Engineer",
  location: "Remote",
  description_text: "",
  source_title: "Senior Frontend Engineer · Northstar Labs",
  source_confidence: .96,
  application_link: "https://northstar.example/jobs/frontend",
  status: "ready",
  error: "",
  created_at: "2026-07-17T08:55:00.000Z",
  updated_at: "2026-07-17T09:00:00.000Z",
  requirements: {
    must_have_skills: ["React", "TypeScript", "component systems", "testing"],
    preferred_skills: ["Next.js", "CI/CD", "performance optimization"],
    nice_to_have_skills: ["GraphQL"],
    all_skills: ["React", "TypeScript", "Next.js", "testing", "CI/CD", "performance optimization"],
    min_years_experience: 5,
    seniority: "senior",
    education: "",
    work_mode: "Full-time",
    domain: "developer tools",
    summary: "Lead frontend platform work across a product engineering organization.",
    languages: ["TypeScript"],
    location_requirement: "Remote",
    work_authorization: "",
    availability: "",
    responsibilities: ["Own shared frontend architecture", "Improve performance and developer experience", "Mentor product engineers"],
    evidence_by_requirement: {},
    ontology_version: "2026.07",
    skill_groups: [],
    experience_requirement_known: true,
    reader_version: "job-reader-v2",
    extraction_completeness: .94
  },
  match: {
    id: 101,
    score: 87,
    fit_level: "Strong",
    confidence: .92,
    status: "Lead",
    matched_evidence: [
      "React, TypeScript, and Next.js from work experience",
      "Design systems and reusable component APIs",
      "Modular frontend architecture from projects",
      "Testing with Jest and Playwright",
      "GitHub Actions and CI/CD from repositories"
    ],
    missing_blockers: [],
    gaps: ["Performance optimization impact is not quantified in the current resume."],
    model_version: "career-fit-v2",
    ontology_version: "2026.07",
    component_scores: {
      frontend_architecture: 94,
      component_systems: 91,
      performance: 84,
      testing_and_quality: 88,
      ci_cd_automation: 79
    },
    applied_caps: [],
    status_history: [{ status: "Lead", created_at: "2026-07-17T09:00:00.000Z" }],
    resume_advice: {
      projects: ["Add one bullet that quantifies frontend performance impact using a before/after metric."],
      skill_order: ["React", "TypeScript", "Design systems", "Testing", "CI/CD"],
      about_text: "Frontend engineer who builds reliable product platforms, reusable systems, and evidence-led developer experiences.",
      template_id: "evidence-first",
      evidence: []
    },
    analyzed_at: "2026-07-17T09:00:00.000Z"
  },
  agent_run: {
    id: 20,
    workflow_type: "job_scan",
    subject_type: "job",
    subject_id: 1,
    status: "completed",
    version: "v2",
    summary: "Role read, evidence compared, and action plan prepared.",
    error: "",
    created_at: "2026-07-17T08:55:00.000Z",
    completed_at: "2026-07-17T09:00:00.000Z",
    steps: [
      { id: 1, step_key: "extract_job", title: "Read role", status: "completed", attempt: 1, progress: "Requirements captured", output: {}, error: "", started_at: "2026-07-17T08:55:00.000Z", completed_at: "2026-07-17T08:56:00.000Z" },
      { id: 2, step_key: "match_profile_evidence", title: "Compare evidence", status: "completed", attempt: 1, progress: "Evidence mapped", output: {}, error: "", started_at: "2026-07-17T08:56:00.000Z", completed_at: "2026-07-17T08:58:00.000Z" },
      { id: 3, step_key: "validate_resume_advice", title: "Build action plan", status: "completed", attempt: 1, progress: "Advice ready", output: {}, error: "", started_at: "2026-07-17T08:58:00.000Z", completed_at: "2026-07-17T09:00:00.000Z" }
    ]
  }
};

export function OpportunityPreview() {
  const [form, setForm] = useState<JobCreate>({ source_url: "", company: "", role: "", description_text: "" });
  const [selectedId, setSelectedId] = useState(1);
  const [query, setQuery] = useState("");
  const visibleJobs = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return previewJobs;
    return previewJobs.filter((job) => [job.role, job.company, job.location, ...job.top_skills]
      .join(" ")
      .toLowerCase()
      .includes(normalized));
  }, [query]);
  const selectedSummary = previewJobs.find((job) => job.id === selectedId) ?? previewJobs[0];
  const selectedJob = useMemo<TrackedJob>(() => ({
    ...previewJob,
    id: selectedSummary.id,
    company: selectedSummary.company,
    role: selectedSummary.role,
    location: selectedSummary.location,
    source_title: `${selectedSummary.role} · ${selectedSummary.company}`,
    match: previewJob.match ? { ...previewJob.match, ...selectedSummary.match } : null
  }), [selectedSummary]);
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); }

  return (
    <>
      <section className="workbench-intro">
        <header className="page-heading home-hero"><div><span className="eyebrow"><Sparkles size={14} /> Your career signal, clarified</span><h1>Know why a role fits.<br /><em>Know what to improve.</em></h1><p>Paste a job URL, compare it against your verified profile, and focus on the roles that are the best fit.</p></div></header>
        <JobScanner form={form} onCancel={() => undefined} onSubmit={submit} profileReady scanProgress={{ status: "succeeded", currentStep: "validate_resume_advice", progress: 100, traceId: "preview" }} scanStartedAt={Date.now()} setForm={setForm} submitting={false} />
      </section>
      <section className="opportunity-workbench">
        <div className="panel flush opportunity-library">
          <div className="list-header"><div><h2>Saved opportunities</h2><p>5 roles · 2 strong signals</p></div><form className="search-box" onSubmit={(event) => event.preventDefault()}><Search aria-hidden size={15} /><input aria-label="Search saved opportunities" onChange={(event) => setQuery(event.target.value)} placeholder="Search roles" value={query} /></form></div>
          <div className="job-list compact-list">{visibleJobs.length ? visibleJobs.map((job) => <JobSummaryCard active={job.id === selectedId} job={job} key={job.id} onPreview={() => undefined} onSelect={() => setSelectedId(job.id)} />) : <div className="empty">No roles match that search.</div>}</div>
        </div>
        <OpportunityInspector detailError="" job={selectedJob} loading={false} onJobChanged={() => undefined} profileUpdatedAt={null} summary={selectedSummary} />
      </section>
    </>
  );
}

function summary(id: number, company: string, role: string, score: number, fit: "Strong" | "Medium" | "Weak", location: string): TrackedJobSummary {
  return {
    id,
    source_url: "",
    company,
    role,
    location,
    source_confidence: .9,
    application_link: "",
    status: "ready",
    error: "",
    created_at: "2026-07-17T08:00:00.000Z",
    updated_at: "2026-07-17T09:00:00.000Z",
    requirement_summary: "Evidence-backed role analysis",
    top_skills: ["React", "TypeScript"],
    min_years_experience: 4,
    extraction_completeness: .9,
    primary_signal: fit === "Weak" ? "Several core requirements need evidence." : "Strong alignment across the role's core requirements.",
    match: id === 1 ? previewMatch : { ...previewMatch, id: 100 + id, score, fit_level: fit }
  };
}
