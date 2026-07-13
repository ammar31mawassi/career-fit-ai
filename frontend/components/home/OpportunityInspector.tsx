"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { CheckCircle2, CircleAlert, CircleDot, ExternalLink, Gauge, Loader2, Radar, RefreshCw, Target, Zap } from "lucide-react";
import { RequirementReviewPanel } from "@/components/home/RequirementReviewPanel";
import {
  formatDate,
  rematchJob,
  updateJobStatus,
  type AgentRun,
  type JobStatus,
  type TrackedJob,
  type TrackedJobSummary
} from "@/lib/api";

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
  const match = job?.match ?? null;
  const matchStale = Boolean(match && profileUpdatedAt && new Date(profileUpdatedAt).getTime() > new Date(match.analyzed_at).getTime());

  async function setStatus(status: JobStatus) {
    if (!job?.match || job.match.status === status) return;
    const previous = job;
    const optimistic: TrackedJob = {
      ...job,
      match: {
        ...job.match,
        status,
        status_history: [
          ...job.match.status_history,
          { status, created_at: new Date().toISOString() }
        ]
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
            {saving ? <small>Saved · syncing</small> : null}
          </label>
        ) : null}
        {matchStale ? <button className="button compact quiet" disabled={rematching} onClick={() => void refreshMatch()} type="button"><RefreshCw className={rematching ? "spin" : ""} size={14} /> {rematching ? "Refreshing…" : "Refresh match"}</button> : null}
      </div>
      {matchStale ? <div className="stale-match-note"><CircleAlert size={14} /><span>Your profile changed after this score. Refresh explicitly when you want to recalculate it.</span></div> : null}
      {statusError ? <div className="notice error compact-notice" role="alert">{statusError}</div> : null}

      <div className="detail-grid inspector-metrics">
        <Detail icon={<Gauge size={14} />} label="Match confidence" value={`${Math.round((match?.confidence ?? 0) * 100)}%`} />
        <Detail icon={<Radar size={14} />} label="Reader confidence" value={`${Math.round(job.source_confidence * 100)}%`} />
        <Detail icon={<Target size={14} />} label="Requirements captured" value={`${Math.round(job.requirements.extraction_completeness * 100)}%`} />
        <Detail icon={<Zap size={14} />} label="Experience required" value={job.requirements.min_years_experience ? `${job.requirements.min_years_experience}+ years` : "Not stated"} />
      </div>

      <RequirementReviewPanel job={job} onSaved={onJobChanged} />

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
                  <span>{name.replaceAll("_", " ")}</span><strong>{Math.round(value)}%</strong>
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
        <section className="analysis-section"><h3>Match unavailable</h3><p>{job.error || "This job has not produced a match yet."}</p></section>
      )}
    </aside>
  );
}
function AgentWorkflowTrace({ run }: { run: AgentRun | null }) {
  if (!run) return <section className="analysis-section agent-trace muted-trace"><h3>Agent workflow</h3><p>No workflow trace exists for this older saved job. Rescanning creates one.</p></section>;
  return (
    <section className="analysis-section agent-trace">
      <div className="agent-trace-heading">
        <div><h3>Agent workflow</h3><p>{run.summary || run.version}</p></div>
        <span className={`agent-status ${run.status}`}>{run.status}</span>
      </div>
      <ol>
        {run.steps.map((step) => {
          const Icon = step.status === "failed" ? CircleAlert : step.status === "completed" ? CheckCircle2 : CircleDot;
          return <li className={step.status} key={step.id}><Icon size={15} aria-hidden /><span><strong>{step.title}</strong><small>{step.error || step.progress || step.step_key}</small></span></li>;
        })}
      </ol>
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
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setVisible(true); observer.disconnect(); }
    }, { threshold: .45 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return <div ref={ref} className={`score-orb ${fit.toLowerCase()}`} style={{ "--score": visible ? `${Math.max(0, Math.min(100, rounded))}%` : "0%" } as CSSProperties}><strong>{rounded}%</strong><span>{fit}</span></div>;
}

function Detail({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return <div className="detail">{icon}<span>{label}</span><strong>{value}</strong></div>;
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  return <section className="analysis-section"><h3>{title}</h3>{items.length ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No items found.</p>}</section>;
}

function InspectorSkeleton({ summary }: { summary: TrackedJobSummary }) {
  return (
    <div className="inspector-skeleton" role="status" aria-label="Loading job evidence">
      <div className="inspector-hero"><div><span className="section-kicker">Evidence inspector</span><h2>{summary.role}</h2><p>{summary.company}</p></div><Loader2 className="loader-icon" size={28} aria-hidden /></div>
      <span className="skeleton-block wide" /><span className="skeleton-block text" /><span className="skeleton-block text short" />
    </div>
  );
}
