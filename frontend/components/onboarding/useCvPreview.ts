"use client";

import { useEffect, useRef, useState } from "react";
import { recognizePdfInBrowser } from "@/lib/browserOcr";
import { isAbortError, validateBrowserOcrFile } from "@/lib/browser-ocr-policy.mjs";
import {
  analyzeProfile,
  saveBrowserOcr,
  uploadCv,
  type Profile,
  type ProfileAnalyzeResult
} from "@/lib/api";
import type { CvPreviewState } from "@/components/onboarding/CvDiscoveryPanel";

const EMPTY_PREVIEW: CvPreviewState = {
  status: "idle",
  progress: 0,
  detail: "",
  disclosure: "",
  fileName: ""
};

export function useCvPreview(onProfile: (profile: Profile) => void) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CvPreviewState>(EMPTY_PREVIEW);
  const [skills, setSkills] = useState<string[]>([]);
  const [canCancelOcr, setCanCancelOcr] = useState(false);
  const pending = useRef<Promise<ProfileAnalyzeResult> | null>(null);
  const ocrController = useRef<AbortController | null>(null);
  const run = useRef(0);
  const active = ["uploading", "reading", "analyzing"].includes(preview.status);

  useEffect(() => () => {
    run.current += 1;
    ocrController.current?.abort();
  }, []);

  function start(nextFile: File | null) {
    ocrController.current?.abort();
    const runId = run.current + 1;
    run.current = runId;
    pending.current = null;
    setCanCancelOcr(false);
    setSkills([]);
    if (!nextFile) {
      setFile(null);
      setPreview(EMPTY_PREVIEW);
      return true;
    }
    const filePolicy = validateBrowserOcrFile(nextFile);
    if (!filePolicy.ok) {
      setFile(null);
      setPreview({
        status: "error",
        progress: 0,
        detail: filePolicy.error,
        disclosure: "",
        fileName: nextFile.name
      });
      return false;
    }
    setFile(nextFile);
    setPreview({
      status: "uploading",
      progress: 5,
      detail: "Securely uploading your CV",
      disclosure: "",
      fileName: nextFile.name
    });
    const task = analyze(nextFile, runId);
    pending.current = task;
    void task.catch(() => undefined);
    return true;
  }

  async function analyze(nextFile: File, runId: number): Promise<ProfileAnalyzeResult> {
    let uploadedProfile: Profile | null = null;
    let coverageDisclosure = "";
    try {
      uploadedProfile = await uploadCv(nextFile);
      if (runId !== run.current) return { profile: uploadedProfile, generated_facts: 0, open_questions: 0 };
      onProfile(uploadedProfile);
      setPreview({
        status: "reading",
        progress: 24,
        detail: "Reading experience, projects, and education",
        disclosure: "",
        fileName: nextFile.name
      });
      const cvSource = uploadedProfile.sources.find((source) => source.source_type === "cv");
      if (cvSource?.ocr_recommended) {
        const controller = new AbortController();
        ocrController.current = controller;
        setCanCancelOcr(true);
        let ocr;
        try {
          ocr = await recognizePdfInBrowser(nextFile, (update) => {
            if (runId !== run.current) return;
            setPreview({
              status: "reading",
              progress: 24 + update.progress * 44,
              detail: update.detail,
              disclosure: update.stage === "complete" ? update.detail : "",
              fileName: nextFile.name
            });
          }, controller.signal);
        } finally {
          if (ocrController.current === controller) ocrController.current = null;
          if (runId === run.current) setCanCancelOcr(false);
        }
        coverageDisclosure = ocr.coverage_detail;
        controller.signal.throwIfAborted();
        const recoveredProfile = await saveBrowserOcr(ocr);
        if (runId !== run.current) {
          return { profile: recoveredProfile, generated_facts: 0, open_questions: 0 };
        }
        onProfile(recoveredProfile);
      }
      if (runId === run.current) {
        setPreview({
          status: "analyzing",
          progress: 76,
          detail: "Connecting skills to real evidence",
          disclosure: coverageDisclosure,
          fileName: nextFile.name
        });
      }
      const result = await analyzeProfile();
      if (runId !== run.current) return result;
      onProfile(result.profile);
      const discovered = topProfileSkills(result.profile);
      setSkills(discovered);
      setPreview({
        status: "ready",
        progress: 100,
        detail: discovered.length
          ? `Found ${discovered.length} strong skill signals`
          : "Your CV preview is ready",
        disclosure: coverageDisclosure,
        fileName: nextFile.name
      });
      return result;
    } catch (cause) {
      if (isAbortError(cause) && uploadedProfile) {
        if (runId === run.current) {
          setCanCancelOcr(false);
          setPreview({
            status: "cancelled",
            progress: 0,
            detail: "Local OCR stopped. Your uploaded CV is still stored by CareerFit.",
            disclosure: "",
            fileName: nextFile.name
          });
        }
        return { profile: uploadedProfile, generated_facts: 0, open_questions: 0 };
      }
      if (runId === run.current) {
        const rawMessage = cause instanceof Error ? cause.message : "Could not preview this CV.";
        const message = uploadedProfile
          ? `Your CV is stored, but its preview did not finish. ${rawMessage}`
          : rawMessage;
        setPreview({
          status: "error",
          progress: 0,
          detail: message,
          disclosure: coverageDisclosure,
          fileName: nextFile.name
        });
        throw new Error(message);
      }
      throw cause;
    }
  }

  function cancelOcr() {
    const controller = ocrController.current;
    if (!controller || controller.signal.aborted) return;
    controller.abort();
    setCanCancelOcr(false);
    setPreview((current) => current.status === "reading"
      ? { ...current, detail: "Stopping local OCR…" }
      : current);
  }

  function clearFile() {
    run.current += 1;
    ocrController.current?.abort();
    ocrController.current = null;
    pending.current = null;
    setCanCancelOcr(false);
    setFile(null);
  }

  return {
    active,
    canCancelOcr,
    cancelOcr,
    clearFile,
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
