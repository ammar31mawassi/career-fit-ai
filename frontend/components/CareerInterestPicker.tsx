"use client";

import { Check } from "lucide-react";
import { CAREER_INTERESTS } from "@/lib/career-interests";

export function CareerInterestPicker({
  selected,
  onChange,
  disabled = false
}: {
  selected: string[];
  onChange: (values: string[]) => void;
  disabled?: boolean;
}) {
  function toggle(value: string) {
    onChange(
      selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value]
    );
  }

  return (
    <fieldset className="interest-picker" disabled={disabled}>
      <legend className="sr-only">Career interests</legend>
      {CAREER_INTERESTS.map((interest) => {
        const active = selected.includes(interest);
        return (
          <button
            aria-pressed={active}
            className={active ? "interest-option selected" : "interest-option"}
            key={interest}
            onClick={() => toggle(interest)}
            type="button"
          >
            <span>{interest}</span>
            {active ? <Check aria-hidden size={14} /> : null}
          </button>
        );
      })}
    </fieldset>
  );
}
