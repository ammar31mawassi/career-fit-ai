"use client";

import { useEffect, useState, type CSSProperties, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { ArrowRight, Check, ChevronDown, Link2, Radar, X } from "lucide-react";
import type { JobCreate } from "@/lib/api";

export function JobScanner({
  form,
  setForm,
  submitting,
  scanStartedAt,
  scanProgress,
  profileReady,
  onSubmit,
  onCancel
}: {
  form: JobCreate;
  setForm: Dispatch<SetStateAction<JobCreate>>;
  submitting: boolean;
  scanStartedAt: number;
  scanProgress: { status: string; currentStep: string; progress: number; traceId: string } | null;
  profileReady: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
}) {
  const scanComplete = scanProgress?.status === "succeeded";
  const flowProgress = submitting ? scanProgress?.progress ?? 4 : scanComplete ? 100 : 0;
  return (
    <form aria-busy={submitting} className={`panel job-form${submitting ? " is-scanning" : ""}`} onSubmit={onSubmit}>
      <div className="scan-heading">
        <span><Radar size={18} aria-hidden /></span>
        <div><h2>Scan a role</h2><p>Compare a real opportunity with your verified evidence.</p></div>
      </div>
      <div className="scan-entry-row">
        <label className="scan-url-field">
          <span className="sr-only">Job URL</span>
          <Link2 size={19} aria-hidden />
          <input
            autoComplete="url"
            disabled={submitting}
            onChange={(event) => setForm((current) => ({ ...current, source_url: event.target.value }))}
            placeholder="Paste a job URL"
            type="url"
            value={form.source_url}
          />
        </label>
        <button
          className="button primary action-button"
          disabled={submitting || !profileReady || (!form.source_url.trim() && !form.description_text.trim())}
          type="submit"
        >
          {submitting ? <><span className="button-spinner" /> Analyzing</> : <>Analyze fit <ArrowRight size={17} /></>}
        </button>
      </div>
      <div className="scan-flow" style={{ "--scan-flow-progress": `${flowProgress}%` } as CSSProperties}>
        {[
          { label: "Read role", threshold: 10 },
          { label: "Compare evidence", threshold: 52 },
          { label: "Build action plan", threshold: 88 }
        ].map((step, index) => {
          const complete = flowProgress >= step.threshold;
          return (
            <span className={complete ? "complete" : submitting && index === 0 ? "active" : ""} key={step.label}>
              <i>{complete ? <Check size={12} strokeWidth={3} /> : index + 1}</i>{step.label}
            </span>
          );
        })}
      </div>
      <details className="scan-options" open={Boolean(form.description_text || form.company || form.role)}>
        <summary><ChevronDown size={15} /> Add a description fallback</summary>
        <div className="scan-options-body">
          <div className="form-grid">
            <label className="field"><span>Company (optional)</span><input disabled={submitting} onChange={(event) => setForm((current) => ({ ...current, company: event.target.value }))} value={form.company} /></label>
            <label className="field"><span>Role (optional)</span><input disabled={submitting} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value }))} value={form.role} /></label>
          </div>
          <label className="field">
            <span>Job description fallback</span>
            <textarea disabled={submitting} onChange={(event) => setForm((current) => ({ ...current, description_text: event.target.value }))} placeholder="Paste the full job description when the career site blocks extraction..." value={form.description_text} />
          </label>
        </div>
      </details>
      {form.source_url.trim() ? (
        <label className="check-row">
          <input
            checked={form.contribute_public_posting}
            disabled={submitting}
            onChange={(event) => setForm((current) => ({ ...current, contribute_public_posting: event.target.checked }))}
            type="checkbox"
          />
          <span><strong>Contribute this public posting to discovery</strong><br />Only a posting CareerFit successfully verifies from this public URL can enter the shared catalog. Pasted fallback text never does.</span>
        </label>
      ) : null}
      {submitting ? <ScanProgress hasSourceUrl={Boolean(form.source_url.trim())} onCancel={onCancel} scanProgress={scanProgress} startedAt={scanStartedAt} /> : null}
    </form>
  );
}
function ScanProgress({ startedAt, hasSourceUrl, onCancel, scanProgress }: { startedAt: number; hasSourceUrl: boolean; onCancel: () => void; scanProgress: { status: string; currentStep: string; progress: number; traceId: string } | null }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  const stages = [
    { key: "queued", label: "Queued securely" },
    { key: "extract_job", label: hasSourceUrl ? "Opening the source" : "Validating pasted description" },
    { key: "classify_requirements", label: "Classifying requirements" },
    { key: "match_profile_evidence", label: "Matching profile evidence" },
    { key: "validate_resume_advice", label: "Preparing resume advice" }
  ];
  const persistedIndex = stages.findIndex((stage) => stage.key === scanProgress?.currentStep);
  const activeStage = persistedIndex >= 0 ? persistedIndex : Math.min(stages.length - 1, Math.floor((scanProgress?.progress ?? 0) / 22));

  return (
    <section className="scan-progress">
      <div className="scan-visual" aria-hidden><span /><i /><b /></div>
      <div className="scan-progress-copy">
        <span className="scan-progress-label">{scanProgress?.status === "queued" ? "Queued" : "Analysis in progress"} · <span aria-hidden="true">{elapsed}s · </span>{scanProgress?.progress ?? 0}%</span>
        <strong aria-atomic="true" aria-live="polite" role="status">{stages[activeStage]?.label ?? "Preparing the scan"}</strong>
        <small>{hasSourceUrl ? "Blocked career sites can take longer." : "The evidence model is classifying requirements and recalculating your match."} Progress is saved, so closing the tab will not lose the scan.</small>
        <ol className="scan-stage-list">
          {stages.map((stage, index) => <li className={index <= activeStage ? "active" : ""} key={stage.key}>{stage.label}</li>)}
        </ol>
        <button className="button compact quiet scan-cancel" onClick={onCancel} type="button"><X size={13} /> Cancel scan</button>
        {scanProgress?.traceId ? <small className="scan-support-code">Reference code {scanProgress.traceId.slice(0, 12)}</small> : null}
      </div>
      <div className="scan-progress-rail" aria-hidden><span /></div>
    </section>
  );
}
