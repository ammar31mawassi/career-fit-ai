"use client";

import { Check, CircleStop, FileSearch, LoaderCircle, Sparkles } from "lucide-react";

export type CvPreviewState = {
  status: "idle" | "uploading" | "reading" | "analyzing" | "ready" | "error" | "cancelled";
  progress: number;
  detail: string;
  disclosure: string;
  fileName: string;
};

export function CvDiscoveryPanel({
  canCancelOcr = false,
  onCancelOcr,
  preview,
  skills
}: {
  canCancelOcr?: boolean;
  onCancelOcr?: () => void;
  preview: CvPreviewState;
  skills: string[];
}) {
  if (preview.status === "idle") return null;
  const ready = preview.status === "ready";
  const failed = preview.status === "error";
  const cancelled = preview.status === "cancelled";
  return (
    <aside
      aria-busy={!ready && !failed && !cancelled}
      className={`cv-discovery ${ready ? "ready" : ""} ${failed ? "error" : ""} ${cancelled ? "cancelled" : ""}`}
    >
      <span
        aria-atomic="true"
        aria-live={failed ? "assertive" : "polite"}
        className="sr-only"
        role={failed ? "alert" : "status"}
      >
        {previewAnnouncement(preview)}
      </span>
      <span className="cv-discovery-icon" aria-hidden>
        {ready
          ? <Check size={16} />
          : cancelled
            ? <CircleStop size={16} />
            : failed
              ? <FileSearch size={16} />
              : <LoaderCircle size={16} />}
      </span>
      <div className="cv-discovery-copy">
        <small>
          {ready
            ? "First signals found"
            : failed
              ? "Preview needs attention"
              : cancelled
                ? "Local OCR stopped"
                : "CV preview running"}
        </small>
        <strong>
          {ready && skills.length
            ? `You seem strongest in ${skills.slice(0, 2).join(" and ")}.`
            : preview.detail}
        </strong>
        <span>
          {ready
            ? preview.disclosure || "Your CV and extracted text are stored by CareerFit."
            : preview.fileName}
        </span>
      </div>
      {!ready && !failed && !cancelled ? (
        <div
          aria-label="CV preview"
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={Math.round(preview.progress)}
          className="cv-discovery-progress"
          role="progressbar"
        >
          <span style={{ transform: `scaleX(${Math.max(0, Math.min(1, preview.progress / 100))})` }} />
        </div>
      ) : null}
      {canCancelOcr && onCancelOcr ? (
        <button
          className="button quiet compact cv-discovery-cancel"
          onClick={onCancelOcr}
          type="button"
        >
          <CircleStop size={14} aria-hidden /> Stop local OCR
        </button>
      ) : null}
      {ready && skills.length ? (
        <div className="cv-discovery-skills" aria-label="Skills found in your CV">
          <Sparkles size={13} aria-hidden />
          {skills.slice(0, 6).map((skill) => <span key={skill}>{skill}</span>)}
        </div>
      ) : null}
    </aside>
  );
}

function previewAnnouncement(preview: CvPreviewState) {
  switch (preview.status) {
    case "uploading":
      return "Uploading your CV to CareerFit.";
    case "reading":
      return "Reading your CV. Scanned page images are rendered on this device.";
    case "analyzing":
      return "Analyzing evidence from your CV.";
    case "ready":
      return `CV preview ready. ${preview.disclosure || preview.detail}`;
    case "error":
      return `CV preview failed. ${preview.detail}`;
    case "cancelled":
      return preview.detail;
    default:
      return "";
  }
}
