"use client";

import { Check, FastForward, Sparkles } from "lucide-react";

export function SkillConfirmationPanel({
  skills,
  selected,
  skipped,
  onToggle,
  onConfirmAll,
  onSkip
}: {
  skills: string[];
  selected: string[];
  skipped: boolean;
  onToggle: (skill: string) => void;
  onConfirmAll: () => void;
  onSkip: () => void;
}) {
  if (!skills.length) return null;
  return (
    <section className={`skill-confirmation ${skipped ? "skipped" : ""}`} aria-labelledby="skill-confirmation-title">
      <div className="skill-confirmation-heading">
        <span aria-hidden><Sparkles size={15} /></span>
        <div>
          <strong id="skill-confirmation-title">A quick check while we finish</strong>
          <small>Select skills that accurately describe you. This is optional.</small>
        </div>
      </div>
      <div className="skill-confirmation-chips">
        {skills.map((skill) => {
          const active = selected.includes(skill) && !skipped;
          return (
            <button aria-pressed={active} className={active ? "selected" : ""} disabled={skipped} key={skill} onClick={() => onToggle(skill)} type="button">
              {active ? <Check size={12} /> : null}{skill}
            </button>
          );
        })}
      </div>
      <div className="skill-confirmation-actions">
        <button className="button compact secondary" disabled={skipped} onClick={onConfirmAll} type="button"><Check size={13} /> Looks right</button>
        <button className="skill-skip" onClick={onSkip} type="button"><FastForward size={13} /> {skipped ? "Skipped" : "Skip for now"}</button>
      </div>
    </section>
  );
}
