"use client";

import { useMemo, useState, type FormEvent } from "react";
import { Search, Sparkles } from "lucide-react";
import { JobScanner } from "@/components/home/JobScanner";
import { JobSummaryCard } from "@/components/home/JobSummaryCard";
import { OpportunityInspector } from "@/components/home/OpportunityInspector";
import type { JobCreate, JobMatchSummary, TrackedJob, TrackedJobSummary } from "@/lib/api";

const previewMatch: JobMatchSummary = {
  id: 101,
  score: 39,
  fit_level: "Weak",
  confidence: .86,
  status: "Lead",
  analyzed_at: "2026-07-17T09:00:00.000Z"
};

const previewJobs: TrackedJobSummary[] = [
  summary(1, "Siemens", "Application Engineering Student", 39, "Weak", "Israel, Tel Aviv, Remote, Hybrid"),
  summary(2, "Clearline Health", "Full Stack Engineer", 74, "Strong", "Hybrid"),
  summary(3, "Atlas Systems", "Frontend Engineer", 62, "Medium", "Remote"),
  summary(4, "Lumina", "Staff UI Engineer", 48, "Weak", "London"),
  summary(5, "Brightline", "Web Engineer", 36, "Weak", "Remote")
];

const previewJob: TrackedJob = {
  id: 1,
  source_url: "https://jobs.example/application-engineering-student",
  company: "Siemens",
  role: "Application Engineering Student",
  location: "Israel, Tel Aviv, Remote, Hybrid",
  description_text: "",
  source_title: "Application Engineering Student · Siemens",
  source_confidence: .96,
  application_link: "https://jobs.example/application-engineering-student",
  status: "ready",
  error: "",
  created_at: "2026-07-17T08:55:00.000Z",
  updated_at: "2026-07-17T09:00:00.000Z",
  requirements: {
    must_have_skills: ["Go", "English", "current engineering studies"],
    preferred_skills: ["automation", "systems thinking"],
    nice_to_have_skills: ["GraphQL"],
    all_skills: ["Go", "English", "automation", "systems thinking"],
    min_years_experience: 0,
    seniority: "student",
    education: "",
    work_mode: "remote, hybrid, part-time",
    domain: "application engineering",
    summary: "A student application engineering role requiring Go, English, and current engineering studies.",
    languages: ["TypeScript"],
    location_requirement: "Remote",
    work_authorization: "",
    availability: "",
    responsibilities: ["Support application engineering projects", "Work with product and engineering teams", "Automate repeatable workflows"],
    evidence_by_requirement: {
      go: "Go is listed as a must-have skill for the role.",
      english: "Professional English is required for cross-team collaboration.",
      logistics: "The role is part-time and supports remote or hybrid work in Tel Aviv."
    },
    ontology_version: "2026.07",
    skill_groups: [],
    experience_requirement_known: true,
    reader_version: "job-reader-v2",
    extraction_completeness: .94
  },
  match: {
    id: 101,
    score: 39,
    fit_level: "Weak",
    confidence: .86,
    status: "Lead",
    matched_evidence: [
      "Career stage aligns with the student role."
    ],
    missing_blockers: ["Missing must-have skill: Go. Job evidence: Go is listed as a must-have skill for the role."],
    gaps: [],
    model_version: "career-fit-v2",
    ontology_version: "2026.07",
    component_scores: {
      education_language: 100,
      experience_seniority: 100,
      logistics: 75,
      must_have_skills: 20,
      responsibility_domain: 14
    },
    applied_caps: [],
    status_history: [{
      previous_status: null,
      status: "Lead",
      occurred_at: "2026-07-17T09:00:00.000Z",
      source: "system",
      note: "",
      created_at: "2026-07-17T09:00:00.000Z"
    }],
    resume_advice: {
      projects: ["Add one or two verified projects with concrete implementation details and outcomes."],
      skill_order: ["English", "Automation", "Systems thinking"],
      about_text: "Engineering student with verified profile evidence in English, automation, and systems thinking, seeking an application engineering opportunity where those documented skills match the role requirements.",
      template_id: "T04",
      evidence: ["The reviewed profile contains verified automation and systems-thinking project work."],
      template_version: "about-v1.1.0",
      quality_policy_version: "resume-output-v1.0.0",
      quality_checked: true,
      quality_repaired: false,
      quality_findings: []
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
      { id: 1, step_key: "extract_job", title: "Read role", status: "completed", attempt: 1, progress: "Requirements captured", output: { reader_strategy: "json_ld", reader_version: "reader-v2.4.0" }, error: "", started_at: "2026-07-17T08:55:00.000Z", completed_at: "2026-07-17T08:56:00.000Z" },
      { id: 2, step_key: "match_profile_evidence", title: "Compare evidence", status: "completed", attempt: 1, progress: "Evidence mapped", output: {}, error: "", started_at: "2026-07-17T08:56:00.000Z", completed_at: "2026-07-17T08:58:00.000Z" },
      { id: 3, step_key: "validate_resume_advice", title: "Build action plan", status: "completed", attempt: 1, progress: "Advice ready", output: {}, error: "", started_at: "2026-07-17T08:58:00.000Z", completed_at: "2026-07-17T09:00:00.000Z" }
    ]
  }
};

export function OpportunityPreview() {
  const [form, setForm] = useState<JobCreate>({
    source_url: "",
    company: "",
    role: "",
    description_text: "",
    contribute_public_posting: false
  });
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
    match: previewJob.match ? {
      ...previewJob.match,
      ...selectedSummary.match,
      ...(selectedSummary.id === 1 ? {} : { missing_blockers: [], gaps: [] })
    } : null
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
