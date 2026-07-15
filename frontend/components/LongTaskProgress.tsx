"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, Circle, LoaderCircle, ScanText, Sparkles } from "lucide-react";

type ProgressStep = { label: string; detail?: string };

export function LongTaskProgress({
  title,
  detail,
  progress,
  activeStep,
  steps,
  mode = "overlay",
  children
}: {
  title: string;
  detail: string;
  progress: number;
  activeStep: number;
  steps: ProgressStep[];
  mode?: "overlay" | "page";
  children?: ReactNode;
}) {
  const percentage = useSmoothedProgress(progress);
  return (
    <section className={`long-task ${mode}`} aria-busy="true">
      <div className="long-task-card">
        <div className="long-task-visual" aria-hidden>
          <span className="long-task-orbit"><ScanText size={23} /></span>
          <Sparkles className="long-task-spark" size={15} />
        </div>
        <div className="long-task-heading">
          <span>CareerFit is working</span>
          <h2>{title}</h2>
          <p aria-live="polite">{detail}</p>
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
        {children ? <div className="long-task-discovery">{children}</div> : null}
        <p className="long-task-privacy">Scanned-page OCR runs on this device. Page images are not sent to an external OCR provider.</p>
      </div>
    </section>
  );
}

function useSmoothedProgress(progress: number) {
  const target = Math.max(0, Math.min(100, progress));
  const [displayed, setDisplayed] = useState(0);
  const displayedRef = useRef(0);

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) {
      displayedRef.current = target;
      setDisplayed(target);
      return;
    }
    const startValue = displayedRef.current;
    const distance = target - startValue;
    if (Math.abs(distance) < 0.1) return;
    const startedAt = performance.now();
    const duration = Math.min(1800, Math.max(520, Math.abs(distance) * 28));
    let frame = 0;
    const animate = (now: number) => {
      const elapsed = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - elapsed, 3);
      const next = startValue + distance * eased;
      displayedRef.current = next;
      setDisplayed(next);
      if (elapsed < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [target]);

  return Math.max(0, Math.min(100, Math.round(displayed)));
}
