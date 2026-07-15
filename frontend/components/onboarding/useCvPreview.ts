"use client";

import { useRef, useState } from "react";
import { recognizePdfInBrowser } from "@/lib/browserOcr";
import {
  analyzeProfile,
  saveBrowserOcr,
  uploadCv,
  type Profile,
  type ProfileAnalyzeResult
} from "@/lib/api";
import type { CvPreviewState } from "@/components/onboarding/CvDiscoveryPanel";

const EMPTY_PREVIEW: CvPreviewState = { status: "idle", progress: 0, detail: "", fileName: "" };

export function useCvPreview(onProfile: (profile: Profile) => void) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CvPreviewState>(EMPTY_PREVIEW);
  const [skills, setSkills] = useState<string[]>([]);
  const pending = useRef<Promise<ProfileAnalyzeResult> | null>(null);
  const run = useRef(0);
  const active = ["uploading", "reading", "analyzing"].includes(preview.status);

  function start(nextFile: File | null) {
    setFile(nextFile);
    if (!nextFile) return;
    const runId = run.current + 1;
    run.current = runId;
    setSkills([]);
    setPreview({ status: "uploading", progress: 5, detail: "Securely uploading your CV", fileName: nextFile.name });
    const task = analyze(nextFile, runId);
    pending.current = task;
    void task.catch(() => undefined);
  }

  async function analyze(nextFile: File, runId: number): Promise<ProfileAnalyzeResult> {
    try {
      const uploadedProfile = await uploadCv(nextFile);
      if (runId !== run.current) return { profile: uploadedProfile, generated_facts: 0, open_questions: 0 };
      onProfile(uploadedProfile);
      setPreview({ status: "reading", progress: 24, detail: "Reading experience, projects, and education", fileName: nextFile.name });
      const cvSource = uploadedProfile.sources.find((source) => source.source_type === "cv");
      if (cvSource?.ocr_recommended) {
        const ocr = await recognizePdfInBrowser(nextFile, (update) => {
          if (runId !== run.current) return;
          setPreview({
            status: "reading",
            progress: 24 + update.progress * 44,
            detail: update.detail,
            fileName: nextFile.name
          });
        });
        const recoveredProfile = await saveBrowserOcr(ocr);
        if (runId === run.current) onProfile(recoveredProfile);
      }
      if (runId === run.current) {
        setPreview({ status: "analyzing", progress: 76, detail: "Connecting skills to real evidence", fileName: nextFile.name });
      }
      const result = await analyzeProfile();
      if (runId !== run.current) return result;
      onProfile(result.profile);
      const discovered = topProfileSkills(result.profile);
      setSkills(discovered);
      setPreview({
        status: "ready",
        progress: 100,
        detail: discovered.length ? `Found ${discovered.length} strong skill signals` : "Your CV preview is ready",
        fileName: nextFile.name
      });
      return result;
    } catch (cause) {
      if (runId === run.current) {
        const message = cause instanceof Error ? cause.message : "Could not preview this CV.";
        setPreview({ status: "error", progress: 0, detail: message, fileName: nextFile.name });
      }
      throw cause;
    }
  }

  return {
    active,
    clearFile: () => setFile(null),
    file,
    preview,
    skills,
    start,
    wait: () => pending.current
  };
}

function topProfileSkills(profile: Profile) {
  return profile.facts
    .filter((fact) => fact.fact_type === "skill" && fact.review_status !== "rejected")
    .sort((left, right) => right.confidence - left.confidence)
    .map((fact) => fact.value)
    .filter((value, index, values) => values.indexOf(value) === index)
    .slice(0, 6);
}
