"use client";

import { useMemo, useState, type FormEvent } from "react";
import { ArrowUpRight, ExternalLink, FileText, RefreshCw, Search, Sparkles } from "lucide-react";
import { useAppData } from "@/components/AppDataProvider";
import {
  createJob,
  formatDate,
  updateJobStatus,
  type JobCreate,
  type JobStatus,
  type TrackedJob
} from "@/lib/api";

const emptyJob: JobCreate = { source_url: "", company: "", role: "", description_text: "" };

export function HomeClient() {
  const { profile, jobs, profileLoading, jobsLoading, dataError, setJobs, refreshAll } = useAppData();
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(emptyJob);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const profileReady = profile ? profile.status === "ready" : true;
  const profileConfirmedIncomplete = !profileLoading && profile !== null && profile.status !== "ready";
  const visibleJobs = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return jobs;
    return jobs.filter((job) =>
      [job.company, job.role, job.location, job.description_text, ...job.requirements.all_skills]
        .join(" ")
        .toLowerCase()
        .includes(normalized)
    );
  }, [jobs, query]);
  const stats = useMemo(() => {
    const scanned = jobs.length;
    const applied = jobs.filter((job) => job.match && !["Lead", "Withdrawn"].includes(job.match.status)).length;
    const strong = jobs.filter((job) => job.match?.fit_level === "Strong").length;
    return { scanned, applied, strong };
  }, [jobs]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const job = await createJob(form);
      setMessage(job.status === "failed" ? job.error : `${job.company} — ${job.role} analyzed and saved.`);
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setForm(emptyJob);
      setQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyze this job.");
    } finally {
      setSubmitting(false);
    }
  }

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  function updateCachedJob(updated: TrackedJob) {
    setJobs((current) => current.map((job) => job.id === updated.id ? updated : job));
  }

  return (
    <>
      <header className="page-heading home-hero">
        <div>
          <span className="eyebrow"><Sparkles size={14} /> Your career signal</span>
          <h1>Know where you fit.<br /><em>Know what to change.</em></h1>
          <p>CareerFit turns your real experience into clear job-fit evidence and practical resume direction.</p>
        </div>
        <button className="button quiet" onClick={() => void refreshAll()} type="button"><RefreshCw size={16} /> Refresh</button>
      </header>

      {error || dataError ? <div className="notice error">{error || dataError}</div> : null}
      {message ? <div className="notice success">{message}</div> : null}
      {profileConfirmedIncomplete ? (
        <section className="panel warning-panel">
          <FileText size={22} aria-hidden />
          <div>
            <h2>Profile is not ready</h2>
            <p>Upload one CV and run profile analysis before job matching. GitHub and LinkedIn are optional.</p>
          </div>
          <a className="button primary" href="/profile">Complete profile</a>
        </section>
      ) : null}

      <section className="stats signal-stats" aria-label="Job search overview">
        <div><span>Opportunities mapped</span><strong>{stats.scanned}</strong><small>Your searchable career library</small></div>
        <div><span>Strong signals</span><strong>{stats.strong}</strong><small>Roles worth prioritizing</small></div>
        <div><span>In motion</span><strong>{stats.applied}</strong><small>Applications beyond lead stage</small></div>
      </section>

      <form className="panel job-form" onSubmit={submit}>
        <div className="section-heading">
          <div>
            <span className="section-kicker">New opportunity</span>
            <h2>Map a role to your profile</h2>
            <p>Start with the job link. Add the description only when the career site blocks extraction.</p>
          </div>
          <span className="section-orbit"><ArrowUpRight size={20} aria-hidden /></span>
        </div>
        <label className="field">
          <span>Job URL</span>
          <input onChange={(event) => setForm({ ...form, source_url: event.target.value })} placeholder="https://company.com/careers/job/..." type="url" value={form.source_url} />
        </label>
        <div className="form-grid">
          <label className="field"><span>Company (optional)</span><input onChange={(event) => setForm({ ...form, company: event.target.value })} value={form.company} /></label>
          <label className="field"><span>Role (optional)</span><input onChange={(event) => setForm({ ...form, role: event.target.value })} value={form.role} /></label>
        </div>
        <label className="field">
          <span>Job description fallback</span>
          <textarea onChange={(event) => setForm({ ...form, description_text: event.target.value })} placeholder="Paste the full job description here..." value={form.description_text} />
        </label>
        <button className="button primary action-button" disabled={submitting || !profileReady || (!form.source_url.trim() && !form.description_text.trim())} type="submit">
          {submitting ? "Analyzing..." : "Save and match"}
        </button>
      </form>

      <section className="panel flush">
        <div className="list-header">
          <div>
            <span className="section-kicker">Opportunity library</span>
            <h2>Your saved roles</h2>
            <p>Search instantly. Repeated links reuse the existing analysis.</p>
          </div>
          <form className="search-box" onSubmit={search}>
            <Search size={16} aria-hidden />
            <input onChange={(event) => setQuery(event.target.value)} placeholder="Search company, role, skill..." value={query} />
          </form>
        </div>
        {jobsLoading && !jobs.length ? <div className="empty loading-state"><span className="pulse-dot" /> Mapping your opportunities…</div> : visibleJobs.length ? (
          <div className="job-list">
            {visibleJobs.map((job) => <JobCard job={job} key={job.id} onStatusChanged={updateCachedJob} />)}
          </div>
        ) : <div className="empty">{jobs.length ? "No roles match that search." : "Your first opportunity will appear here."}</div>}
      </section>
    </>
  );
}

function JobCard({ job, onStatusChanged }: { job: TrackedJob; onStatusChanged: (job: TrackedJob) => void }) {
  const [saving, setSaving] = useState(false);
  const match = job.match;

  async function setStatus(status: JobStatus) {
    setSaving(true);
    try {
      const updated = await updateJobStatus(job.id, status);
      onStatusChanged(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <details className="job-card">
      <summary>
        <div className="job-title"><strong>{job.company}</strong><span>{job.role}</span></div>
        <div className="job-meta">
          {match ? <span className={`fit ${match.fit_level.toLowerCase()}`}>{Math.round(match.score)}% {match.fit_level}</span> : <span className="fit weak">No match</span>}
          <span className="chip">{match?.status ?? "Lead"}</span>
          <span className="chip">{job.location || "Not specified"}</span>
        </div>
        <p>{match?.missing_blockers[0] || match?.gaps[0] || job.error || job.requirements.summary}</p>
      </summary>
      <div className="job-detail">
        {job.source_url || job.application_link ? (
          <a className="button compact" href={job.application_link || job.source_url} rel="noreferrer" target="_blank">
            <ExternalLink size={15} /> Open Job Site
          </a>
        ) : null}
        {match ? (
          <label className="status-control">
            <span>Application stage</span>
            <select disabled={saving} onChange={(event) => void setStatus(event.target.value as JobStatus)} value={match.status}>
              {(["Lead", "Applied", "Interview", "Rejected", "Withdrawn", "Offer"] as JobStatus[]).map((status) => <option key={status}>{status}</option>)}
            </select>
          </label>
        ) : null}

        <div className="detail-grid">
          <Detail label="Match confidence" value={`${Math.round((match?.confidence ?? 0) * 100)}%`} />
          <Detail label="Reader confidence" value={`${Math.round(job.source_confidence * 100)}%`} />
          <Detail label="Requirements captured" value={`${Math.round(job.requirements.extraction_completeness * 100)}%`} />
          <Detail label="Experience required" value={job.requirements.min_years_experience ? `${job.requirements.min_years_experience}+ years` : "Not stated"} />
          <Detail label="Seniority" value={job.requirements.seniority} />
          <Detail label="Analyzed" value={formatDate(match?.analyzed_at ?? null)} />
          <Detail label="Model" value={match?.model_version ?? "Not available"} />
        </div>

        {match ? (
          <>
            <AnalysisList title="Matched evidence" items={match.matched_evidence} />
            <AnalysisList title="Missing blockers" items={match.missing_blockers.length ? match.missing_blockers : ["No hard blocker detected."]} />
            <AnalysisList title="Gaps to check" items={match.gaps} />
            {match.applied_caps.length ? <AnalysisList title="Score caps applied" items={match.applied_caps} /> : null}
            <AnalysisList title="Application history" items={match.status_history.map((event) => `${event.status} · ${formatDate(event.created_at)}`)} />
            <section className="analysis-section">
              <h3>Score components</h3>
              <div className="detail-grid">
                {Object.entries(match.component_scores).map(([name, value]) => <Detail key={name} label={name.replaceAll("_", " ")} value={`${Math.round(value)}%`} />)}
              </div>
            </section>
            <section className="analysis-section resume-advice">
              <h3>What to add to your Resume</h3>
              <div className="resume-grid">
                <div><span>Projects</span><ul>{match.resume_advice.projects.map((item) => <li key={item}>{item}</li>)}</ul></div>
                <div><span>Skill order</span><p>{match.resume_advice.skill_order.join(" · ") || "Add more profile skills first."}</p></div>
              </div>
              <div><span>Fitting About · {match.resume_advice.template_id || "evidence summary"}</span><p>{match.resume_advice.about_text}</p></div>
            </section>
          </>
        ) : null}
      </div>
    </details>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="detail"><span>{label}</span><strong>{value}</strong></div>;
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="analysis-section">
      <h3>{title}</h3>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}
