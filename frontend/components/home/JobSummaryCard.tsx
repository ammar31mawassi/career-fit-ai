import type { TrackedJobSummary } from "@/lib/api";

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

  return (
    <button
      aria-pressed={active}
      className={`job-summary-card${active ? " active" : ""}`}
      onFocus={onPreview}
      onMouseEnter={onPreview}
      onClick={onSelect}
      type="button"
    >
      <span className="job-summary-main">
        <span className="job-title"><strong>{job.company}</strong><span>{job.role}</span></span>
        <span className="job-signal">{job.primary_signal || job.requirement_summary || job.error || "Open to inspect the evidence."}</span>
        <span className="skill-strip">{job.top_skills.slice(0, 4).map((skill) => <span key={skill}>{skill}</span>)}</span>
      </span>
      <span className="job-summary-side">
        <span className={`fit ${match?.fit_level.toLowerCase() ?? "weak"}`}>{match ? `${score}% ${match.fit_level}` : "No match"}</span>
        <span className="chip">{match?.status ?? "Lead"}</span>
      </span>
    </button>
  );
}
