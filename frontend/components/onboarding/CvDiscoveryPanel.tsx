"use client";

import { Check, FileSearch, LoaderCircle, Sparkles } from "lucide-react";

export type CvPreviewState = {
  status: "idle" | "uploading" | "reading" | "analyzing" | "ready" | "error";
  progress: number;
  detail: string;
  fileName: string;
};

export function CvDiscoveryPanel({ preview, skills }: { preview: CvPreviewState; skills: string[] }) {
  if (preview.status === "idle") return null;
  const ready = preview.status === "ready";
  const failed = preview.status === "error";
  return (
    <aside className={`cv-discovery ${ready ? "ready" : ""} ${failed ? "error" : ""}`} aria-live="polite">
      <span className="cv-discovery-icon" aria-hidden>
        {ready ? <Check size={16} /> : failed ? <FileSearch size={16} /> : <LoaderCircle size={16} />}
      </span>
      <div className="cv-discovery-copy">
        <small>{ready ? "First signals found" : failed ? "Preview needs attention" : "CV preview running"}</small>
        <strong>{ready && skills.length ? `You seem strongest in ${skills.slice(0, 2).join(" and ")}.` : preview.detail}</strong>
        <span>{ready ? "Keep adding context below—we’ll merge it before your final profile is ready." : preview.fileName}</span>
      </div>
      {!ready && !failed ? (
        <div className="cv-discovery-progress" role="progressbar" aria-label="CV preview" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(preview.progress)}>
          <span style={{ transform: `scaleX(${Math.max(0, Math.min(1, preview.progress / 100))})` }} />
        </div>
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
