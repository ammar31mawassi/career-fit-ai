"use client";

import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { Check, Circle, CircleStop, LoaderCircle, ScanText, Sparkles } from "lucide-react";

type ProgressStep = { label: string; detail?: string };

export function LongTaskProgress({
  title,
  detail,
  progress,
  activeStep,
  steps,
  mode = "overlay",
  cancelLabel = "Stop local OCR",
  onCancel,
  children
}: {
  title: string;
  detail: string;
  progress: number;
  activeStep: number;
  steps: ProgressStep[];
  mode?: "overlay" | "page";
  cancelLabel?: string;
  onCancel?: () => void;
  children?: ReactNode;
}) {
  const percentage = useSmoothedProgress(progress);
  const titleId = useId();
  const detailId = useId();
  const privacyId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCancelRef = useRef(onCancel);
  const [portalReady, setPortalReady] = useState(false);
  const modal = mode === "overlay";
  onCancelRef.current = onCancel;

  useEffect(() => {
    setPortalReady(modal);
  }, [modal]);
  useModalBehavior(modal && portalReady, dialogRef, onCancelRef);

  const activeStepIndex = Math.max(0, Math.min(steps.length - 1, activeStep));
  const activeLabel = steps[activeStepIndex]?.label || "Working";
  const announcement = percentage >= 100
    ? `${title}. ${detail}`
    : `${title}. Step ${activeStepIndex + 1} of ${steps.length}: ${activeLabel}.`;

  const content = (
    <section
      aria-busy="true"
      aria-labelledby={modal ? undefined : titleId}
      className={`long-task ${mode}`}
    >
      <div
        aria-describedby={modal ? `${detailId} ${privacyId}` : undefined}
        aria-labelledby={modal ? titleId : undefined}
        aria-modal={modal ? "true" : undefined}
        className="long-task-card"
        ref={dialogRef}
        role={modal ? "dialog" : undefined}
        tabIndex={modal ? -1 : undefined}
      >
        <span aria-atomic="true" aria-live="polite" className="sr-only" role="status">
          {announcement}
        </span>
        <div className="long-task-visual" aria-hidden>
          <span className="long-task-orbit"><ScanText size={23} /></span>
          <Sparkles className="long-task-spark" size={15} />
        </div>
        <div className="long-task-heading">
          <span>CareerFit is working</span>
          <h2 id={titleId}>{title}</h2>
          <p id={detailId}>{detail}</p>
        </div>
        <div
          aria-label={title}
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={percentage}
          aria-valuetext={`${percentage}% complete. ${detail}`}
          className="long-task-progress"
          role="progressbar"
        >
          <span style={{ width: `${percentage}%` }} />
        </div>
        <div className="long-task-meta">
          <span>{percentage}%</span>
          <small>Keep this tab open</small>
        </div>
        <ol className="long-task-steps">
          {steps.map((step, index) => {
            const state = index < activeStep ? "complete" : index === activeStep ? "active" : "pending";
            return (
              <li className={state} key={step.label}>
                <span aria-hidden>
                  {state === "complete"
                    ? <Check size={13} />
                    : state === "active"
                      ? <LoaderCircle size={13} />
                      : <Circle size={11} />}
                </span>
                <div>
                  <strong>{step.label}</strong>
                  {step.detail ? <small>{step.detail}</small> : null}
                </div>
              </li>
            );
          })}
        </ol>
        {children ? <div className="long-task-discovery">{children}</div> : null}
        <p className="long-task-privacy" id={privacyId}>
          When OCR is needed, scanned page images are rendered only on this device.
          Source files you choose and recovered text are still uploaded to and stored by CareerFit.
        </p>
        {onCancel ? (
          <div className="long-task-actions">
            <button className="button quiet" onClick={onCancel} type="button">
              <CircleStop size={16} aria-hidden /> {cancelLabel}
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );

  if (modal) {
    return portalReady ? createPortal(content, document.body) : null;
  }
  return content;
}

function useModalBehavior(
  active: boolean,
  dialogRef: RefObject<HTMLDivElement | null>,
  onCancelRef: RefObject<(() => void) | undefined>
) {
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!active || !dialog) return;
    const activeDialog = dialog;

    const restoreFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const portalRoot = activeDialog.parentElement;
    const background = Array.from(document.body.children)
      .filter((element): element is HTMLElement => (
        element instanceof HTMLElement && element !== portalRoot
      ))
      .map((element) => ({ element, inert: element.inert }));
    for (const { element } of background) element.inert = true;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusFrame = requestAnimationFrame(() => activeDialog.focus({ preventScroll: true }));

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && onCancelRef.current) {
        event.preventDefault();
        onCancelRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(activeDialog.querySelectorAll<HTMLElement>(
        "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), "
        + "textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
      )).filter((element) => !element.hidden && !element.inert);
      if (!focusable.length) {
        event.preventDefault();
        activeDialog.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === activeDialog)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      } else if (!activeDialog.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      for (const { element, inert } of background) element.inert = inert;
      if (restoreFocus?.isConnected) restoreFocus.focus({ preventScroll: true });
    };
  }, [active, dialogRef, onCancelRef]);
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
