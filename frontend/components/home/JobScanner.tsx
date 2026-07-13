"use client";

import { useEffect, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { ArrowUpRight, ChevronDown, Radar } from "lucide-react";
import type { JobCreate } from "@/lib/api";

export function JobScanner({
  form,
  setForm,
  submitting,
  scanStartedAt,
  profileReady,
  onSubmit
}: {
  form: JobCreate;
  setForm: Dispatch<SetStateAction<JobCreate>>;
  submitting: boolean;
  scanStartedAt: number;
  profileReady: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
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
      {submitting ? <ScanProgress hasSourceUrl={Boolean(form.source_url.trim())} startedAt={scanStartedAt} /> : null}
    </form>
  );
}
function ScanProgress({ startedAt, hasSourceUrl }: { startedAt: number; hasSourceUrl: boolean }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  const stages = [
    hasSourceUrl ? "Opening the source" : "Validating pasted description",
    "Extracting requirements",
    "Classifying must-haves",
    "Matching profile evidence",
    "Preparing resume advice"
  ];
  const activeStage = Math.min(stages.length - 1, Math.floor(elapsed / 4));

  return (
    <section className="scan-progress" role="status" aria-live="polite">
      <div className="scan-visual" aria-hidden><span /><i /><b /></div>
      <div className="scan-progress-copy">
        <span className="scan-progress-label">Analysis in progress · {elapsed}s</span>
        <strong>{stages[activeStage]}</strong>
        <small>{hasSourceUrl ? "Some career sites take longer when they limit automated reading." : "The evidence model is classifying requirements and recalculating your match."} Keep this tab open.</small>
        <ol className="scan-stage-list">
          {stages.map((stage, index) => <li className={index <= activeStage ? "active" : ""} key={stage}>{stage}</li>)}
        </ol>
      </div>
      <div className="scan-progress-rail" aria-hidden><span /></div>
    </section>
  );
}
