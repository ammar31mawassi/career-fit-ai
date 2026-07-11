"use client";

import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type ReactNode
} from "react";
import {
  ArrowUpRight,
  ChevronDown,
  CheckCircle2,
  CircleAlert,
  CircleDot,
  ExternalLink,
  FileText,
  Gauge,
  Loader2,
  Radar,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  Zap
} from "lucide-react";
import { useAppData } from "@/components/AppDataProvider";
import {
  createJob,
  formatDate,
  getJob,
  getJobSummaries,
  toJobSummary,
  updateJobStatus,
  type JobCreate,
  type JobStatus,
  type AgentRun,
  type TrackedJob,
  type TrackedJobSummary
} from "@/lib/api";

const emptyJob: JobCreate = { source_url: "", company: "", role: "", description_text: "" };

export function HomeClient() {
  const { profile, jobs, profileLoading, jobsLoading, dataError, setJobs, refreshAll } = useAppData();
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(emptyJob);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [scanStartedAt, setScanStartedAt] = useState(0);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [jobDetailsById, setJobDetailsById] = useState<Record<number, TrackedJob>>({});
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [searchResults, setSearchResults] = useState<TrackedJobSummary[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const pendingDetailIds = useRef(new Set<number>());

  const profileReady = profile ? profile.status === "ready" : true;
  const profileConfirmedIncomplete = !profileLoading && profile !== null && profile.status !== "ready";
  const deferredQuery = useDeferredValue(query);
  const searchableJobs = useMemo(
    () =>
      jobs.map((job) => ({
        job,
        searchText: [
          job.company,
          job.role,
          job.location,
          job.source_url,
          job.requirement_summary,
          job.primary_signal,
          ...job.top_skills
        ]
          .join(" ")
          .toLowerCase()
      })),
    [jobs]
  );
  const visibleJobs = useMemo(() => {
    const normalized = deferredQuery.trim().toLowerCase();
    if (searchResults) return searchResults;
    if (!normalized) return jobs;
    return searchableJobs.filter(({ searchText }) => searchText.includes(normalized)).map(({ job }) => job);
  }, [deferredQuery, jobs, searchableJobs, searchResults]);
  const selectedSummary = selectedJobId ? visibleJobs.find((job) => job.id === selectedJobId) ?? null : null;
  const selectedJob = selectedJobId ? jobDetailsById[selectedJobId] ?? null : null;
  const stats = useMemo(() => {
    const scanned = jobs.length;
    const applied = jobs.filter((job) => job.match && !["Lead", "Withdrawn"].includes(job.match.status)).length;
    const strong = jobs.filter((job) => job.match?.fit_level === "Strong").length;
    return { scanned, applied, strong };
  }, [jobs]);

  useEffect(() => {
    const normalized = deferredQuery.trim();
    if (normalized.length < 2) {
      setSearchResults(null);
      setSearchLoading(false);
      setSearchError("");
      return;
    }

    let cancelled = false;
    setSearchLoading(true);
    setSearchError("");
    const timer = window.setTimeout(() => {
      void getJobSummaries(normalized)
        .then((results) => {
          if (!cancelled) setSearchResults(results);
        })
        .catch((err) => {
          if (!cancelled) {
            setSearchResults(null);
            setSearchError(err instanceof Error ? err.message : "Could not search saved jobs.");
          }
        })
        .finally(() => {
          if (!cancelled) setSearchLoading(false);
        });
    }, 260);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [deferredQuery]);

  const fetchJobDetail = useCallback(
    async (jobId: number, showLoading = false) => {
      if (jobDetailsById[jobId] || pendingDetailIds.current.has(jobId)) return;
      pendingDetailIds.current.add(jobId);
      if (showLoading) {
        setDetailsLoading(true);
        setDetailError("");
      }
      try {
        const job = await getJob(jobId);
        setJobDetailsById((current) => ({ ...current, [job.id]: job }));
      } catch (err) {
        if (showLoading) setDetailError(err instanceof Error ? err.message : "Could not load job details.");
      } finally {
        pendingDetailIds.current.delete(jobId);
        if (showLoading) setDetailsLoading(false);
      }
    },
    [jobDetailsById]
  );

  useEffect(() => {
    if (!visibleJobs.length) {
      setSelectedJobId(null);
      return;
    }
    if (!selectedJobId || !visibleJobs.some((job) => job.id === selectedJobId)) {
      setSelectedJobId(visibleJobs[0].id);
    }
  }, [selectedJobId, visibleJobs]);

  useEffect(() => {
    if (!selectedJobId || jobDetailsById[selectedJobId]) {
      setDetailsLoading(false);
      setDetailError("");
      return;
    }
    void fetchJobDetail(selectedJobId, true);
  }, [fetchJobDetail, jobDetailsById, selectedJobId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setScanStartedAt(Date.now());
    setError("");
    setMessage("");
    try {
      const job = await createJob(form);
      const summary = toJobSummary(job);
      setMessage(job.status === "failed" ? job.error : `${job.company} — ${job.role} analyzed and saved.`);
      setJobs((current) => [summary, ...current.filter((item) => item.id !== job.id)]);
      setSearchResults((current) => current ? [summary, ...current.filter((item) => item.id !== job.id)] : current);
      setJobDetailsById((current) => ({ ...current, [job.id]: job }));
      setSelectedJobId(job.id);
      setForm(emptyJob);
      setQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyze this job.");
    } finally {
      setSubmitting(false);
      setScanStartedAt(0);
    }
  }

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  function updateCachedJob(updated: TrackedJob) {
    const summary = toJobSummary(updated);
    setJobs((current) => current.map((job) => (job.id === updated.id ? summary : job)));
    setSearchResults((current) => current?.map((job) => (job.id === updated.id ? summary : job)) ?? current);
    setJobDetailsById((current) => ({ ...current, [updated.id]: updated }));
  }

  return (
    <>
      <header className="page-heading home-hero">
        <div>
          <span className="eyebrow"><Sparkles size={14} /> Career signal radar</span>
          <h1>Scan the role.<br /><em>Trust the evidence.</em></h1>
          <p>CareerFit reads an opportunity, compares it to your verified profile, and shows the exact resume changes that improve your fit.</p>
        </div>
        <button className="button quiet" onClick={() => void refreshAll()} type="button"><RefreshCw size={16} /> Refresh</button>
      </header>

      {error || dataError || searchError ? <div className="notice error">{error || dataError || searchError}</div> : null}
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

      <form aria-busy={submitting} className={`panel job-form${submitting ? " is-scanning" : ""}`} onSubmit={submit}>
        <div className="section-heading">
          <div>
            <span className="section-kicker">New opportunity</span>
            <h2>Map a role to your evidence profile</h2>
            <p>Start with the job link. Add the description only when the career site blocks extraction.</p>
          </div>
          <span className="section-orbit"><ArrowUpRight size={20} aria-hidden /></span>
        </div>
        <div className="scan-entry-row">
          <label className="field scan-url-field">
            <span>Job URL</span>
            <input
              autoComplete="url"
              onChange={(event) => setForm({ ...form, source_url: event.target.value })}
              placeholder="https://company.com/careers/job/..."
              type="url"
              value={form.source_url}
            />
          </label>
          <button
            className="button primary action-button"
            disabled={submitting || !profileReady || (!form.source_url.trim() && !form.description_text.trim())}
            type="submit"
          >
            {submitting ? <><span className="button-spinner" /> Analyzing</> : <><Radar size={16} /> Save and match</>}
          </button>
        </div>
        <details className="scan-options" open={Boolean(form.description_text || form.company || form.role)}>
          <summary><ChevronDown size={15} /> Add company, role, or a description fallback</summary>
          <div className="scan-options-body">
            <div className="form-grid">
              <label className="field"><span>Company (optional)</span><input onChange={(event) => setForm({ ...form, company: event.target.value })} value={form.company} /></label>
              <label className="field"><span>Role (optional)</span><input onChange={(event) => setForm({ ...form, role: event.target.value })} value={form.role} /></label>
            </div>
            <label className="field">
              <span>Job description fallback</span>
              <textarea onChange={(event) => setForm({ ...form, description_text: event.target.value })} placeholder="Paste the full job description when the career site blocks extraction..." value={form.description_text} />
            </label>
          </div>
        </details>
        {submitting ? <ScanProgress startedAt={scanStartedAt} /> : null}
      </form>

      <section className="stats signal-stats" aria-label="Job search overview">
        <div><span>Opportunities mapped</span><strong>{stats.scanned}</strong><small>Cached summaries for quick switching</small></div>
        <div><span>Strong signals</span><strong>{stats.strong}</strong><small>Roles worth prioritizing</small></div>
        <div><span>In motion</span><strong>{stats.applied}</strong><small>Applications beyond lead stage</small></div>
      </section>

      <section className="opportunity-workbench">
        <div className="panel flush opportunity-library">
          <div className="list-header">
            <div>
              <span className="section-kicker">Opportunity radar</span>
              <h2>Your saved roles</h2>
              <p>Search summaries instantly; longer searches query your saved database so old roles are still findable.</p>
            </div>
            <form className="search-box" onSubmit={search}>
              <Search size={16} aria-hidden />
              <input onChange={(event) => setQuery(event.target.value)} placeholder="Search company, role, skill..." value={query} />
              {searchLoading ? <span className="search-spinner" aria-label="Searching saved jobs" /> : null}
            </form>
          </div>
          {jobsLoading && !jobs.length ? <JobLibrarySkeleton /> : visibleJobs.length ? (
            <div className="job-list compact-list">
              {visibleJobs.map((job) => (
                <JobSummaryCard
                  active={job.id === selectedJobId}
                  job={job}
                  key={job.id}
                  onPreview={() => void fetchJobDetail(job.id)}
                  onSelect={() => setSelectedJobId(job.id)}
                />
              ))}
            </div>
          ) : <div className="empty">{jobs.length ? "No roles match that search." : "Your first opportunity will appear here."}</div>}
        </div>

        <OpportunityInspector
          detailError={detailError}
          job={selectedJob}
          loading={detailsLoading}
          onStatusChanged={updateCachedJob}
          summary={selectedSummary}
        />
      </section>
    </>
  );
}

function JobSummaryCard({
  job,
  active,
  onSelect,
  onPreview
}: {
  job: TrackedJobSummary;
  active: boolean;
  onSelect: () => void;
  onPreview: () => void;
}) {
  const match = job.match;
  const score = Math.round(match?.score ?? 0);

  return (
    <button
      aria-pressed={active}
      className={`job-summary-card${active ? " active" : ""}`}
      onFocus={onPreview}
      onMouseEnter={onPreview}
      onClick={onSelect}
      type="button"
    >
      <span className="job-summary-main">
        <span className="job-title">
          <strong>{job.company}</strong>
          <span>{job.role}</span>
        </span>
        <span className="job-signal">{job.primary_signal || job.requirement_summary || job.error || "Open to inspect the evidence."}</span>
        <span className="skill-strip">
          {job.top_skills.slice(0, 4).map((skill) => <span key={skill}>{skill}</span>)}
        </span>
      </span>
      <span className="job-summary-side">
        <span className={`fit ${match?.fit_level.toLowerCase() ?? "weak"}`}>{match ? `${score}% ${match.fit_level}` : "No match"}</span>
        <span className="chip">{match?.status ?? "Lead"}</span>
      </span>
    </button>
  );
}

function OpportunityInspector({
  summary,
  job,
  loading,
  detailError,
  onStatusChanged
}: {
  summary: TrackedJobSummary | null;
  job: TrackedJob | null;
  loading: boolean;
  detailError: string;
  onStatusChanged: (job: TrackedJob) => void;
}) {
  const [saving, setSaving] = useState(false);
  const match = job?.match ?? null;

  async function setStatus(status: JobStatus) {
    if (!job) return;
    setSaving(true);
    try {
      const updated = await updateJobStatus(job.id, status);
      onStatusChanged(updated);
    } finally {
      setSaving(false);
    }
  }

  if (!summary) {
    return (
      <aside className="panel opportunity-inspector">
        <div className="empty compact">Select a saved opportunity to inspect its evidence.</div>
      </aside>
    );
  }

  if (loading && !job) {
    return (
      <aside className="panel opportunity-inspector">
        <InspectorSkeleton summary={summary} />
      </aside>
    );
  }

  if (detailError) {
    return (
      <aside className="panel opportunity-inspector">
        <div className="notice error">{detailError}</div>
      </aside>
    );
  }

  if (!job) {
    return (
      <aside className="panel opportunity-inspector">
        <InspectorSkeleton summary={summary} />
      </aside>
    );
  }

  return (
    <aside className="panel opportunity-inspector">
      <div className="inspector-hero">
        <div>
          <span className="section-kicker">Evidence inspector</span>
          <h2>{job.role}</h2>
          <p>{job.company}{job.location ? ` · ${job.location}` : ""}</p>
        </div>
        <ScoreOrb score={match?.score ?? 0} fit={match?.fit_level ?? "Weak"} />
      </div>

      <div className="inspector-actions">
        {job.source_url || job.application_link ? (
          <a className="button compact primary" href={job.application_link || job.source_url} rel="noreferrer" target="_blank">
            <ExternalLink size={15} /> Open Job Site
          </a>
        ) : null}
        {match ? (
          <label className="status-control">
            <span>Stage</span>
            <select disabled={saving} onChange={(event) => void setStatus(event.target.value as JobStatus)} value={match.status}>
              {(["Lead", "Applied", "Interview", "Rejected", "Withdrawn", "Offer"] as JobStatus[]).map((status) => <option key={status}>{status}</option>)}
            </select>
          </label>
        ) : null}
      </div>

      <div className="detail-grid inspector-metrics">
        <Detail icon={<Gauge size={14} />} label="Match confidence" value={`${Math.round((match?.confidence ?? 0) * 100)}%`} />
        <Detail icon={<Radar size={14} />} label="Reader confidence" value={`${Math.round(job.source_confidence * 100)}%`} />
        <Detail icon={<Target size={14} />} label="Requirements captured" value={`${Math.round(job.requirements.extraction_completeness * 100)}%`} />
        <Detail icon={<Zap size={14} />} label="Experience required" value={job.requirements.min_years_experience ? `${job.requirements.min_years_experience}+ years` : "Not stated"} />
      </div>

      <AgentWorkflowTrace run={job.agent_run} />

      {match ? (
        <>
          <AnalysisList title="Matched evidence" items={match.matched_evidence} />
          <AnalysisList title="Missing blockers" items={match.missing_blockers.length ? match.missing_blockers : ["No hard blocker detected."]} />
          <AnalysisList title="Gaps to check" items={match.gaps} />
          {match.applied_caps.length ? <AnalysisList title="Score caps applied" items={match.applied_caps} /> : null}

          <section className="analysis-section">
            <h3>Score components</h3>
            <div className="component-bars">
              {Object.entries(match.component_scores).map(([name, value]) => (
                <div className="component-bar" key={name}>
                  <span>{name.replaceAll("_", " ")}</span>
                  <strong>{Math.round(value)}%</strong>
                  <i style={{ "--bar": `${Math.max(0, Math.min(100, value))}%` } as CSSProperties} />
                </div>
              ))}
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

          <AnalysisList title="Application history" items={match.status_history.map((event) => `${event.status} · ${formatDate(event.created_at)}`)} />
        </>
      ) : (
        <section className="analysis-section">
          <h3>Match unavailable</h3>
          <p>{job.error || "This job has not produced a match yet."}</p>
        </section>
      )}
    </aside>
  );
}

function AgentWorkflowTrace({ run }: { run: AgentRun | null }) {
  if (!run) {
    return (
      <section className="analysis-section agent-trace muted-trace">
        <h3>Agent workflow</h3>
        <p>No workflow trace exists for this older saved job. Rescanning creates one.</p>
      </section>
    );
  }

  return (
    <section className="analysis-section agent-trace">
      <div className="agent-trace-heading">
        <div>
          <h3>Agent workflow</h3>
          <p>{run.summary || run.version}</p>
        </div>
        <span className={`agent-status ${run.status}`}>{run.status}</span>
      </div>
      <ol>
        {run.steps.map((step) => {
          const failed = step.status === "failed";
          const completed = step.status === "completed";
          const Icon = failed ? CircleAlert : completed ? CheckCircle2 : CircleDot;
          return (
            <li className={step.status} key={step.id}>
              <Icon size={15} aria-hidden />
              <span>
                <strong>{step.title}</strong>
                <small>{step.error || step.progress || step.step_key}</small>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function ScoreOrb({ score, fit }: { score: number; fit: "Strong" | "Medium" | "Weak" }) {
  const rounded = Math.round(score);
  return (
    <div
      className={`score-orb ${fit.toLowerCase()}`}
      style={{ "--score": `${Math.max(0, Math.min(100, rounded))}%` } as CSSProperties}
    >
      <strong>{rounded}%</strong>
      <span>{fit}</span>
    </div>
  );
}

function Detail({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return <div className="detail">{icon}<span>{label}</span><strong>{value}</strong></div>;
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="analysis-section">
      <h3>{title}</h3>
      {items.length ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No items found.</p>}
    </section>
  );
}

function ScanProgress({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  const stages = [
    "Opening the source",
    "Extracting requirements",
    "Classifying must-haves",
    "Matching profile evidence",
    "Preparing resume advice"
  ];
  const activeStage = Math.min(stages.length - 1, Math.floor(elapsed / 4));
  const message = stages[activeStage];

  return (
    <section className="scan-progress" role="status" aria-live="polite">
      <div className="scan-visual" aria-hidden><span /><i /><b /></div>
      <div className="scan-progress-copy">
        <span className="scan-progress-label">Analysis in progress · {elapsed}s</span>
        <strong>{message}</strong>
        <small>Some career sites take longer when they limit automated reading. Keep this tab open.</small>
        <ol className="scan-stage-list">
          {stages.map((stage, index) => (
            <li className={index <= activeStage ? "active" : ""} key={stage}>{stage}</li>
          ))}
        </ol>
      </div>
      <div className="scan-progress-rail" aria-hidden><span /></div>
    </section>
  );
}

function JobLibrarySkeleton() {
  return (
    <div className="library-skeleton" role="status" aria-label="Loading saved opportunities">
      {[0, 1, 2].map((item) => (
        <div className="library-skeleton-row" key={item}>
          <span className="skeleton-block wide" />
          <span className="skeleton-block pill" />
          <span className="skeleton-block text" />
        </div>
      ))}
    </div>
  );
}

function InspectorSkeleton({ summary }: { summary: TrackedJobSummary }) {
  return (
    <div className="inspector-skeleton" role="status" aria-label="Loading job evidence">
      <div className="inspector-hero">
        <div>
          <span className="section-kicker">Evidence inspector</span>
          <h2>{summary.role}</h2>
          <p>{summary.company}</p>
        </div>
        <Loader2 className="loader-icon" size={28} aria-hidden />
      </div>
      <span className="skeleton-block wide" />
      <span className="skeleton-block text" />
      <span className="skeleton-block text" />
    </div>
  );
}
