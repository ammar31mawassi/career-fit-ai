import { useEffect, useRef } from "react";
import { Building2, ChevronRight } from "lucide-react";
import type { TrackedJobSummary } from "@/lib/api";

const PREVIEW_DWELL_MS = 180;

export function JobSummaryCard({
  job,
  active,
  onSelect,
  onPreview
}: {
  job: TrackedJobSummary;
  active: boolean;
  onSelect: () => void;
  onPreview: () => void;
}) {
  const match = job.match;
  const score = Math.round(match?.score ?? 0);
  const previewTimer = useRef<number | null>(null);
  const onPreviewRef = useRef(onPreview);
  onPreviewRef.current = onPreview;

  function cancelPreview() {
    if (previewTimer.current === null) return;
    window.clearTimeout(previewTimer.current);
    previewTimer.current = null;
  }

  function schedulePreview() {
    if (previewTimer.current !== null) return;
    previewTimer.current = window.setTimeout(() => {
      previewTimer.current = null;
      onPreviewRef.current();
    }, PREVIEW_DWELL_MS);
  }

  useEffect(() => () => {
    if (previewTimer.current !== null) window.clearTimeout(previewTimer.current);
    previewTimer.current = null;
  }, [job.id]);

  return (
    <button
      aria-controls="opportunity-inspector"
      aria-pressed={active}
      className={`job-summary-card${active ? " active" : ""}`}
      onBlur={cancelPreview}
      onFocus={schedulePreview}
      onMouseEnter={schedulePreview}
      onMouseLeave={cancelPreview}
      onClick={() => {
        cancelPreview();
        onSelect();
      }}
      type="button"
    >
      <span className={`company-mark company-mark-${Math.abs(job.id) % 4}`} aria-hidden>
        <Building2 size={20} strokeWidth={1.7} />
      </span>
      <span className="job-summary-main" dir="auto">
        <span className="job-title"><strong>{job.role}</strong><span>{job.company}{job.location ? ` · ${job.location}` : ""}</span></span>
        <span className="job-signal">{job.primary_signal || job.requirement_summary || job.error || "Open to inspect the evidence."}</span>
      </span>
      <span className="job-summary-side">
        <strong className={`fit-score ${match?.fit_level.toLowerCase() ?? "weak"}`} title="Evidence alignment guidance, not a hiring-outcome prediction">{match ? `${score}%` : "—"}</strong>
        <span className={`fit ${match?.fit_level.toLowerCase() ?? "weak"}`}>{match ? `${match.fit_level} fit` : "No match"}</span>
        <ChevronRight className="job-summary-chevron" size={17} aria-hidden />
      </span>
    </button>
  );
}
