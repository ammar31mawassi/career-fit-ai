"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import {
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  CircleAlert,
  CircleDot,
  ExternalLink,
  Gauge,
  Loader2,
  MapPin,
  Radar,
  RefreshCw,
  Sparkles,
  Target,
  Waypoints,
  Zap
} from "lucide-react";
import { RequirementReviewPanel } from "@/components/home/RequirementReviewPanel";
import {
  formatDate,
  rematchJob,
  updateJobStatus,
  type AgentRun,
  type JobMatch,
  type JobStatus,
  type TrackedJob,
  type TrackedJobSummary
} from "@/lib/api";

type InspectorTab = "overview" | "evidence" | "requirements" | "details";

const inspectorTabs: Array<{ id: InspectorTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence map" },
  { id: "requirements", label: "Requirements" },
  { id: "details", label: "Job details" }
];

export function OpportunityInspector({
  summary,
  job,
  loading,
  detailError,
  onJobChanged,
  profileUpdatedAt
}: {
  summary: TrackedJobSummary | null;
  job: TrackedJob | null;
  loading: boolean;
  detailError: string;
  onJobChanged: (job: TrackedJob) => void;
  profileUpdatedAt: string | null;
}) {
  const [saving, setSaving] = useState(false);
  const [rematching, setRematching] = useState(false);
  const [statusError, setStatusError] = useState("");
  const [activeTab, setActiveTab] = useState<InspectorTab>("evidence");
  const match = job?.match ?? null;
  const matchStale = Boolean(match && profileUpdatedAt && new Date(profileUpdatedAt).getTime() > new Date(match.analyzed_at).getTime());

  useEffect(() => setActiveTab("evidence"), [job?.id]);

  async function setStatus(status: JobStatus) {
    if (!job?.match || job.match.status === status) return;
    const previous = job;
    const optimistic: TrackedJob = {
      ...job,
      match: {
        ...job.match,
        status,
        status_history: [...job.match.status_history, { status, created_at: new Date().toISOString() }]
      }
    };
    onJobChanged(optimistic);
    setStatusError("");
    setSaving(true);
    try {
      onJobChanged(await updateJobStatus(job.id, status));
    } catch (caught) {
      onJobChanged(previous);
      setStatusError(caught instanceof Error ? `Stage change was rolled back: ${caught.message}` : "Stage change was rolled back.");
    } finally {
      setSaving(false);
    }
  }

  async function refreshMatch() {
    if (!job) return;
    setRematching(true);
    setStatusError("");
    try {
      onJobChanged(await rematchJob(job.id));
    } catch (caught) {
      setStatusError(caught instanceof Error ? caught.message : "Could not refresh this match.");
    } finally {
      setRematching(false);
    }
  }

  if (!summary) return <aside className="panel opportunity-inspector"><div className="empty compact">Select a saved opportunity to inspect its evidence.</div></aside>;
  if (loading && !job) return <aside className="panel opportunity-inspector"><InspectorSkeleton summary={summary} /></aside>;
  if (detailError) return <aside className="panel opportunity-inspector"><div className="notice error">{detailError}</div></aside>;
  if (!job) return <aside className="panel opportunity-inspector"><InspectorSkeleton summary={summary} /></aside>;

  return (
    <aside className="panel opportunity-inspector">
      <div className="inspector-hero">
        <span className="inspector-company-mark" aria-hidden><BriefcaseBusiness size={24} strokeWidth={1.65} /></span>
        <div>
          <h2>{job.role}</h2>
          <p>{job.company}</p>
          <div className="inspector-meta">
            {job.location ? <span><MapPin size={13} /> {job.location}</span> : null}
            <span><BriefcaseBusiness size={13} /> {job.requirements.work_mode || "Role details"}</span>
            <span>Analyzed {formatDate(match?.analyzed_at ?? job.updated_at)}</span>
          </div>
        </div>
        <ScoreOrb score={match?.score ?? 0} fit={match?.fit_level ?? "Weak"} />
      </div>

      <div className="inspector-toolbar">
        <div className="inspector-actions">
          {job.source_url || job.application_link ? (
            <a className="button compact quiet" href={job.application_link || job.source_url} rel="noreferrer" target="_blank">
              <ExternalLink size={14} /> Open job
            </a>
          ) : null}
          {match ? (
            <label className="status-control">
              <span>Stage</span>
              <select disabled={saving} onChange={(event) => void setStatus(event.target.value as JobStatus)} value={match.status}>
                {(["Lead", "Applied", "Interview", "Rejected", "Withdrawn", "Offer"] as JobStatus[]).map((status) => <option key={status}>{status}</option>)}
              </select>
              {saving ? <small>Syncing</small> : null}
            </label>
          ) : null}
          {matchStale ? <button className="button compact quiet" disabled={rematching} onClick={() => void refreshMatch()} type="button"><RefreshCw className={rematching ? "spin" : ""} size={14} /> {rematching ? "Refreshing…" : "Refresh match"}</button> : null}
        </div>
      </div>

      {matchStale ? <div className="stale-match-note"><CircleAlert size={14} /><span>Your profile changed after this score. Refresh when you want to recalculate it.</span></div> : null}
      {statusError ? <div className="notice error compact-notice" role="alert">{statusError}</div> : null}

      <div aria-label="Opportunity details" className="inspector-tabs" role="tablist">
        {inspectorTabs.map((tab) => (
          <button
            aria-controls={`inspector-panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            className={activeTab === tab.id ? "active" : ""}
            id={`inspector-tab-${tab.id}`}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div aria-labelledby={`inspector-tab-${activeTab}`} className="inspector-tab-panel" id={`inspector-panel-${activeTab}`} role="tabpanel">
        {!match ? (
          <section className="analysis-section"><h3>Match unavailable</h3><p>{job.error || "This job has not produced a match yet."}</p></section>
        ) : activeTab === "evidence" ? (
          <EvidenceMap job={job} match={match} onReviewAdvice={() => setActiveTab("overview")} />
        ) : activeTab === "overview" ? (
          <Overview job={job} match={match} />
        ) : activeTab === "requirements" ? (
          <Requirements job={job} onJobChanged={onJobChanged} />
        ) : (
          <JobDetails job={job} match={match} />
        )}
      </div>
    </aside>
  );
}

function EvidenceMap({ job, match, onReviewAdvice }: { job: TrackedJob; match: JobMatch; onReviewAdvice: () => void }) {
  const strengths = useMemo(() => {
    const components = Object.entries(match.component_scores)
      .filter(([, value]) => value > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, value]) => ({ name: titleCase(name), detail: `${Math.round(value)}% evidence coverage` }));
    if (components.length) return components;
    return job.requirements.all_skills.slice(0, 5).map((name) => ({ name, detail: "Supported by your profile" }));
  }, [job.requirements.all_skills, match.component_scores]);
  const gap = match.missing_blockers[0] || match.gaps[0] || "No material gap detected";

  return (
    <>
      <div className="evidence-map-layout">
        <section className="evidence-strengths" aria-labelledby="strengths-title">
          <h3 id="strengths-title">Evidence-backed strengths</h3>
          <ul>
            {strengths.map((item) => <li key={item.name}><span><Check size={14} /></span><div><strong>{item.name}</strong><small>{item.detail}</small></div><em>Strong</em></li>)}
          </ul>
        </section>

        <div className="evidence-orbit" role="img" aria-label={`${strengths.length} matching evidence areas and one gap to close`}>
          <span className="orbit-ring ring-one" aria-hidden />
          <span className="orbit-ring ring-two" aria-hidden />
          <span className="orbit-ring ring-three" aria-hidden />
          <span className="orbit-core" aria-hidden><Waypoints size={34} strokeWidth={1.7} /></span>
          {strengths.map((item, index) => <span className={`orbit-node node-${index + 1}`} key={item.name} title={item.name}><Check size={15} strokeWidth={3} /></span>)}
          <span className="orbit-node orbit-gap" title={gap}><CircleAlert size={17} /></span>
        </div>

        <section className="matching-evidence" aria-labelledby="matching-title">
          <h3 id="matching-title">Matching evidence</h3>
          <ul>{match.matched_evidence.slice(0, 5).map((item) => <li key={item}><CheckCircle2 size={15} /><span>{item}</span></li>)}</ul>
          <div className="evidence-gap"><strong><CircleAlert size={16} /> One gap to close</strong><span>{gap}</span></div>
        </section>
      </div>
      <section className="resume-action">
        <span><Sparkles size={20} /></span>
        <div><strong>Resume action</strong><p>{match.resume_advice.projects[0] || match.resume_advice.about_text || "Bring your strongest matching evidence into the first third of your resume."}</p></div>
        <button className="button resume-action-button" onClick={onReviewAdvice} type="button">Review advice <ExternalLink size={14} /></button>
      </section>
    </>
  );
}

function Overview({ job, match }: { job: TrackedJob; match: JobMatch }) {
  return (
    <>
      <div className="detail-grid inspector-metrics">
        <Detail icon={<Gauge size={14} />} label="Match confidence" value={`${Math.round(match.confidence * 100)}%`} />
        <Detail icon={<Radar size={14} />} label="Reader confidence" value={`${Math.round(job.source_confidence * 100)}%`} />
        <Detail icon={<Target size={14} />} label="Requirements captured" value={`${Math.round(job.requirements.extraction_completeness * 100)}%`} />
        <Detail icon={<Zap size={14} />} label="Experience required" value={job.requirements.min_years_experience ? `${job.requirements.min_years_experience}+ years` : "Not stated"} />
      </div>
      <div className="overview-columns">
        <AnalysisList title="Matched evidence" items={match.matched_evidence} />
        <AnalysisList title="Gaps to address" items={[...match.missing_blockers, ...match.gaps]} />
      </div>
      <section className="analysis-section resume-advice">
        <span className="analysis-kicker">Resume action</span>
        <h3>Shape the first impression around your strongest proof</h3>
        <div className="resume-grid">
          <div><span>Projects</span><ul>{match.resume_advice.projects.map((item) => <li key={item}>{item}</li>)}</ul></div>
          <div><span>Skill order</span><p>{match.resume_advice.skill_order.join(" · ") || "Add more profile skills first."}</p></div>
        </div>
        <div><span>Suggested summary · {match.resume_advice.template_id || "evidence summary"}</span><p>{match.resume_advice.about_text}</p></div>
      </section>
    </>
  );
}

function Requirements({ job, onJobChanged }: { job: TrackedJob; onJobChanged: (job: TrackedJob) => void }) {
  return (
    <>
      <RequirementReviewPanel job={job} onSaved={onJobChanged} />
      <div className="overview-columns">
        <AnalysisList title="Must-have skills" items={job.requirements.must_have_skills} />
        <AnalysisList title="Preferred skills" items={job.requirements.preferred_skills} />
      </div>
      <AnalysisList title="Responsibilities" items={job.requirements.responsibilities} />
    </>
  );
}

function JobDetails({ job, match }: { job: TrackedJob; match: JobMatch }) {
  return (
    <>
      <AgentWorkflowTrace run={job.agent_run} />
      <section className="analysis-section">
        <h3>Score components</h3>
        <div className="component-bars">
          {Object.entries(match.component_scores).map(([name, value]) => (
            <div className="component-bar" key={name}>
              <span>{titleCase(name)}</span><strong>{Math.round(value)}%</strong>
              <i style={{ "--bar": `${Math.max(0, Math.min(100, value))}%` } as CSSProperties} />
            </div>
          ))}
        </div>
      </section>
      {match.applied_caps.length ? <AnalysisList title="Score caps applied" items={match.applied_caps} /> : null}
      <AnalysisList title="Application history" items={match.status_history.map((event) => `${event.status} · ${formatDate(event.created_at)}`)} />
    </>
  );
}

function AgentWorkflowTrace({ run }: { run: AgentRun | null }) {
  if (!run) return <section className="analysis-section agent-trace muted-trace"><h3>Agent workflow</h3><p>No workflow trace exists for this older saved job. Rescanning creates one.</p></section>;
  return (
    <section className="analysis-section agent-trace">
      <div className="agent-trace-heading"><div><h3>Agent workflow</h3><p>{run.summary || run.version}</p></div><span className={`agent-status ${run.status}`}>{run.status}</span></div>
      <ol>{run.steps.map((step) => { const Icon = step.status === "failed" ? CircleAlert : step.status === "completed" ? CheckCircle2 : CircleDot; return <li className={step.status} key={step.id}><Icon size={15} aria-hidden /><span><strong>{step.title}</strong><small>{step.error || step.progress || step.step_key}</small></span></li>; })}</ol>
    </section>
  );
}

function ScoreOrb({ score, fit }: { score: number; fit: "Strong" | "Medium" | "Weak" }) {
  const rounded = Math.round(score);
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") { setVisible(true); return; }
    const observer = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) { setVisible(true); observer.disconnect(); } }, { threshold: .45 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return <div ref={ref} className={`score-orb ${fit.toLowerCase()}`} style={{ "--score": visible ? `${Math.max(0, Math.min(100, rounded))}%` : "0%" } as CSSProperties}><strong>{rounded}%</strong><span>{fit} fit</span><small>Fit confidence: {fit === "Strong" ? "High" : fit}</small></div>;
}

function Detail({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return <div className="detail">{icon}<span>{label}</span><strong>{value}</strong></div>;
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  return <section className="analysis-section"><h3>{title}</h3>{items.length ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No items found.</p>}</section>;
}

function InspectorSkeleton({ summary }: { summary: TrackedJobSummary }) {
  return <div className="inspector-skeleton" role="status" aria-label="Loading job evidence"><div className="inspector-hero"><div><span className="section-kicker">Evidence inspector</span><h2>{summary.role}</h2><p>{summary.company}</p></div><Loader2 className="loader-icon" size={28} aria-hidden /></div><span className="skeleton-block wide" /><span className="skeleton-block text" /><span className="skeleton-block text short" /></div>;
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
