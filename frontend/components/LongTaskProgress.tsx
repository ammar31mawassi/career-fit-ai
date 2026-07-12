"use client";

import { Check, Circle, LoaderCircle, ScanText, Sparkles } from "lucide-react";

type ProgressStep = { label: string; detail?: string };

export function LongTaskProgress({
  title,
  detail,
  progress,
  activeStep,
  steps,
  mode = "overlay"
}: {
  title: string;
  detail: string;
  progress: number;
  activeStep: number;
  steps: ProgressStep[];
  mode?: "overlay" | "page";
}) {
  const percentage = Math.max(0, Math.min(100, Math.round(progress)));
  return (
    <section className={`long-task ${mode}`} role="status" aria-live="polite" aria-busy="true">
      <div className="long-task-card">
        <div className="long-task-visual" aria-hidden>
          <span className="long-task-orbit"><ScanText size={23} /></span>
          <Sparkles className="long-task-spark" size={15} />
        </div>
        <div className="long-task-heading">
          <span>CareerFit is working</span>
          <h2>{title}</h2>
          <p>{detail}</p>
        </div>
        <div
          className="long-task-progress"
          role="progressbar"
          aria-label={title}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percentage}
        >
          <span style={{ width: `${percentage}%` }} />
        </div>
        <div className="long-task-meta"><span>{percentage}%</span><small>Keep this tab open</small></div>
        <ol className="long-task-steps">
          {steps.map((step, index) => {
            const state = index < activeStep ? "complete" : index === activeStep ? "active" : "pending";
            return (
              <li className={state} key={step.label}>
                <span aria-hidden>{state === "complete" ? <Check size={13} /> : state === "active" ? <LoaderCircle size={13} /> : <Circle size={11} />}</span>
                <div><strong>{step.label}</strong>{step.detail ? <small>{step.detail}</small> : null}</div>
              </li>
            );
          })}
        </ol>
        <p className="long-task-privacy">Scanned-page OCR runs on this device. Page images are not sent to an external OCR provider.</p>
      </div>
    </section>
  );
}
