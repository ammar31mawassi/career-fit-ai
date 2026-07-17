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
        <div className="inspector-copy">
          <h2>{job.role}</h2>
          <p>{job.company}</p>
          <div className="inspector-meta">
            {job.location ? <span><MapPin size={13} /> {job.location}</span> : null}
            <span><BriefcaseBusiness size={13} /> {job.requirements.work_mode || "Role details"}</span>
            <span>Analyzed {formatDate(match?.analyzed_at ?? job.updated_at)}</span>
          </div>
        </div>
        <div className="inspector-side">
          <ScoreSummary confidence={match?.confidence ?? 0} score={match?.score ?? 0} fit={match?.fit_level ?? "Weak"} />
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
      .map(([key, value]) => {
        const score = Math.round(value);
        const name = titleCase(key);
        const tokens = evidenceTokens(key);
        return {
          id: `strength-${key}`,
          kind: "strength" as const,
          name,
          score,
          band: coverageBand(score),
          tone: coverageTone(score),
          reason: componentReason(name, score),
          profileEvidence: matchingItems(match.matched_evidence, tokens),
          roleEvidence: requirementEvidence(job, tokens)
        };
      });
    if (components.length) return components;
    return job.requirements.all_skills.slice(0, 5).map((name, index) => ({
      id: `strength-fallback-${index}`,
      kind: "strength" as const,
      name,
      score: 50,
      band: "Supported",
      tone: "supported",
      reason: "This skill appears in the role and has supporting profile evidence, but this scan did not return a component-level percentage.",
      profileEvidence: matchingItems(match.matched_evidence, evidenceTokens(name)),
      roleEvidence: requirementEvidence(job, evidenceTokens(name))
    }));
  }, [job, match.component_scores, match.matched_evidence]);
  const gap = match.missing_blockers[0] || match.gaps[0] || null;
  const gapIsCritical = Boolean(match.missing_blockers[0]);
  const overallPoint = useMemo<EvidencePoint>(() => ({
    id: "overall",
    kind: "overall",
    name: "Overall fit",
    score: Math.round(match.score),
    band: `${match.fit_level} fit`,
    tone: match.fit_level.toLowerCase(),
    reason: "The overall score combines requirement coverage, verified profile evidence, seniority, logistics, and any score caps caused by blockers.",
    profileEvidence: match.matched_evidence.slice(0, 5),
    roleEvidence: overallRoleEvidence(job)
  }), [job, match.fit_level, match.matched_evidence, match.score]);
  const gapPoint = useMemo<EvidencePoint | null>(() => gap ? ({
    id: "gap",
    kind: "gap",
    name: gapIsCritical ? "Critical blocker" : "Gap to close",
    band: gapIsCritical ? "Critical" : "Needs attention",
    tone: "critical",
    reason: gapIsCritical
      ? "This is marked as a must-have requirement. Missing it can cap the total match score even when other areas are strong."
      : "This area is missing or weak in the verified profile and is reducing the strength of the match.",
    profileEvidence: [],
    roleEvidence: [gap]
  }) : null, [gap, gapIsCritical]);
  const points = useMemo(() => [overallPoint, ...strengths, ...(gapPoint ? [gapPoint] : [])], [gapPoint, overallPoint, strengths]);
  const [selectedId, setSelectedId] = useState("overall");
  useEffect(() => setSelectedId("overall"), [job.id, match.id]);
  const selectedPoint = points.find((point) => point.id === selectedId) ?? overallPoint;

  return (
    <>
      <div className="evidence-map-layout">
        <section className="evidence-strengths" aria-labelledby="strengths-title">
          <h3 id="strengths-title">Evidence-backed strengths</h3>
          <ul>
            {strengths.map((item) => (
              <li className={selectedId === item.id ? "selected" : ""} key={item.id}>
                <button aria-controls="evidence-explainer" aria-pressed={selectedId === item.id} onClick={() => setSelectedId(item.id)} type="button">
                  <span className={`evidence-status ${item.tone}`}><EvidenceStatusIcon score={item.score} /></span>
                  <span><strong>{item.name}</strong><small>{item.score}% evidence coverage</small></span>
                  <em className={item.tone}>{item.band}</em>
                </button>
              </li>
            ))}
          </ul>
          {gapPoint ? (
            <button aria-controls="evidence-explainer" aria-pressed={selectedId === gapPoint.id} className={`evidence-gap-link${selectedId === gapPoint.id ? " selected" : ""}`} onClick={() => setSelectedId(gapPoint.id)} type="button">
              <CircleAlert size={17} /><span><strong>{gapPoint.name}</strong><small>{gapPoint.band}</small></span>
            </button>
          ) : <div className="evidence-clear"><CheckCircle2 size={17} /><span>No critical gaps detected</span></div>}
        </section>

        <div aria-label="Interactive match evidence map" className="evidence-orbit" role="group">
          <span className="orbit-ring ring-one" aria-hidden />
          <span className="orbit-ring ring-two" aria-hidden />
          <span className="orbit-ring ring-three" aria-hidden />
          <button aria-controls="evidence-explainer" aria-label={`Overall fit: ${Math.round(match.score)}%. Show score explanation`} aria-pressed={selectedId === "overall"} className={`orbit-core${selectedId === "overall" ? " selected" : ""}`} onClick={() => setSelectedId("overall")} onFocus={() => setSelectedId("overall")} onMouseEnter={() => setSelectedId("overall")} type="button"><Waypoints size={34} strokeWidth={1.7} /></button>
          {strengths.map((item, index) => (
            <button
              aria-controls="evidence-explainer"
              aria-label={`${item.name}: ${item.score}% evidence coverage, ${item.band}. Show evidence`}
              aria-pressed={selectedId === item.id}
              className={`orbit-node node-${index + 1} ${item.tone}${selectedId === item.id ? " selected" : ""}`}
              key={item.id}
              onClick={() => setSelectedId(item.id)}
              onFocus={() => setSelectedId(item.id)}
              onMouseEnter={() => setSelectedId(item.id)}
              type="button"
            >
              <EvidenceStatusIcon score={item.score} />
            </button>
          ))}
          {gapPoint ? <button aria-controls="evidence-explainer" aria-label={`${gapPoint.name}. Show why this matters`} aria-pressed={selectedId === gapPoint.id} className={`orbit-node orbit-gap${selectedId === gapPoint.id ? " selected" : ""}`} onClick={() => setSelectedId(gapPoint.id)} onFocus={() => setSelectedId(gapPoint.id)} onMouseEnter={() => setSelectedId(gapPoint.id)} type="button"><CircleAlert size={17} /></button> : null}
          <p className="orbit-instruction">Hover, focus, or select a point</p>
        </div>

        <section aria-live="polite" className={`evidence-explainer ${selectedPoint.tone}`} id="evidence-explainer">
          <header>
            <div><span>{selectedPoint.kind === "gap" ? "Why this matters" : "Why this counts"}</span><h3>{selectedPoint.name}</h3></div>
            {typeof selectedPoint.score === "number" ? <strong>{selectedPoint.score}%</strong> : <strong>{selectedPoint.band}</strong>}
          </header>
          <p>{selectedPoint.reason}</p>
          <EvidenceSource title="Profile evidence" items={selectedPoint.profileEvidence} empty="No component-specific verified profile fact was returned for this point." />
          <EvidenceSource title="Role evidence" items={selectedPoint.roleEvidence} empty="No requirement excerpt was returned for this point." />
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

function ScoreSummary({ score, fit, confidence }: { score: number; fit: "Strong" | "Medium" | "Weak"; confidence: number }) {
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
  return <div aria-label={`${rounded}% match, ${fit} fit, ${Math.round(confidence * 100)}% confidence`} ref={ref} className={`score-summary ${fit.toLowerCase()}${visible ? " visible" : ""}`}><strong>{rounded}%</strong><span>{fit} fit</span><small>{Math.round(confidence * 100)}% confidence</small></div>;
}

type EvidencePoint = {
  id: string;
  kind: "overall" | "strength" | "gap";
  name: string;
  score?: number;
  band: string;
  tone: string;
  reason: string;
  profileEvidence: string[];
  roleEvidence: string[];
};

function EvidenceSource({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return <div className="evidence-source"><strong>{title}</strong>{items.length ? <ul>{items.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ul> : <p>{empty}</p>}</div>;
}

function EvidenceStatusIcon({ score }: { score: number }) {
  if (score >= 75) return <Check size={15} strokeWidth={3} />;
  if (score >= 50) return <CheckCircle2 size={15} />;
  if (score >= 25) return <CircleDot size={15} />;
  return <CircleAlert size={15} />;
}

function coverageBand(score: number) {
  if (score >= 75) return "Strong";
  if (score >= 50) return "Supported";
  if (score >= 25) return "Partial";
  return "Limited";
}

function coverageTone(score: number) {
  if (score >= 75) return "strong";
  if (score >= 50) return "supported";
  if (score >= 25) return "partial";
  return "limited";
}

function componentReason(name: string, score: number) {
  if (score >= 75) return `${name} has strong verified coverage and actively supports the overall match.`;
  if (score >= 50) return `${name} is supported, but some role evidence is not yet backed by an equally strong profile fact.`;
  if (score >= 25) return `${name} has partial coverage. It helps the match, but the missing evidence limits its contribution.`;
  return `${name} has limited verified coverage. It contributes little to the score and should not be treated as a strong match.`;
}

function evidenceTokens(value: string) {
  const normalized = value.toLowerCase().replaceAll("-", "_");
  const tokens = normalized.split(/[_\s/]+/).filter((token) => token.length > 2);
  const aliases: Record<string, string[]> = {
    education_language: ["education", "degree", "language", "english", "hebrew"],
    experience_seniority: ["experience", "seniority", "career", "stage", "junior", "senior", "years"],
    logistics: ["location", "remote", "hybrid", "onsite", "availability", "authorization", "work mode"],
    must_have_skills: ["must-have", "required", "skill"],
    preferred_skills: ["preferred", "skill"],
    responsibility_domain: ["responsibility", "domain", "industry"],
    relevant_evidence: ["project", "work", "repository", "experience", "evidence"]
  };
  for (const [key, values] of Object.entries(aliases)) {
    if (normalized.includes(key)) tokens.push(...values);
  }
  return [...new Set(tokens)];
}

function matchingItems(items: string[], tokens: string[]) {
  return items.filter((item) => {
    const normalized = item.toLowerCase();
    return tokens.some((token) => normalized.includes(token));
  });
}

function requirementEvidence(job: TrackedJob, tokens: string[]) {
  const matches = Object.entries(job.requirements.evidence_by_requirement)
    .filter(([key, value]) => {
      const normalized = `${key} ${value}`.toLowerCase();
      return tokens.some((token) => normalized.includes(token));
    })
    .map(([, value]) => value);
  return [...new Set(matches)].slice(0, 3);
}

function overallRoleEvidence(job: TrackedJob) {
  const evidence = Object.values(job.requirements.evidence_by_requirement).filter(Boolean);
  if (evidence.length) return [...new Set(evidence)].slice(0, 3);
  return job.requirements.summary ? [job.requirements.summary] : [];
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
