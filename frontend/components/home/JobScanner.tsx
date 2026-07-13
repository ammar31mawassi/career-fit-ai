"use client";

import { useEffect, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { ArrowUpRight, ChevronDown, Radar, X } from "lucide-react";
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
  return (
    <form aria-busy={submitting} className={`panel job-form${submitting ? " is-scanning" : ""}`} onSubmit={onSubmit}>
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
            onChange={(event) => setForm((current) => ({ ...current, source_url: event.target.value }))}
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
            <label className="field"><span>Company (optional)</span><input onChange={(event) => setForm((current) => ({ ...current, company: event.target.value }))} value={form.company} /></label>
            <label className="field"><span>Role (optional)</span><input onChange={(event) => setForm((current) => ({ ...current, role: event.target.value }))} value={form.role} /></label>
          </div>
          <label className="field">
            <span>Job description fallback</span>
            <textarea onChange={(event) => setForm((current) => ({ ...current, description_text: event.target.value }))} placeholder="Paste the full job description when the career site blocks extraction..." value={form.description_text} />
          </label>
        </div>
      </details>
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
    <section className="scan-progress" role="status" aria-live="polite">
      <div className="scan-visual" aria-hidden><span /><i /><b /></div>
      <div className="scan-progress-copy">
        <span className="scan-progress-label">{scanProgress?.status === "queued" ? "Queued" : "Analysis in progress"} · {elapsed}s · {scanProgress?.progress ?? 0}%</span>
        <strong>{stages[activeStage]?.label ?? "Preparing the scan"}</strong>
        <small>{hasSourceUrl ? "Blocked career sites can take longer." : "The evidence model is classifying requirements and recalculating your match."} Progress is saved, so closing the tab will not lose the scan.</small>
        <ol className="scan-stage-list">
          {stages.map((stage, index) => <li className={index <= activeStage ? "active" : ""} key={stage.key}>{stage.label}</li>)}
        </ol>
        <button className="button compact quiet scan-cancel" onClick={onCancel} type="button"><X size={13} /> Cancel scan</button>
        {scanProgress?.traceId ? <small className="scan-support-code">Support code {scanProgress.traceId.slice(0, 12)}</small> : null}
      </div>
      <div className="scan-progress-rail" aria-hidden><span /></div>
    </section>
  );
}
