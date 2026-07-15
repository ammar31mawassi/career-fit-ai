"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRight, FileCheck2, Github, Linkedin, Sparkles, Waypoints } from "lucide-react";
import { useRouter } from "next/navigation";
import { CareerInterestPicker } from "@/components/CareerInterestPicker";
import { LongTaskProgress } from "@/components/LongTaskProgress";
import { CvDiscoveryPanel } from "@/components/onboarding/CvDiscoveryPanel";
import { SkillConfirmationPanel } from "@/components/onboarding/SkillConfirmationPanel";
import { useCvPreview } from "@/components/onboarding/useCvPreview";
import {
  clearOnboardingSyncing,
  markOnboardingSyncing,
  useAppData
} from "@/components/AppDataProvider";
import {
  analyzeOnboardingProfile,
  bulkUpdateProfileFacts,
  completeOnboarding,
  uploadLinkedInPdf
} from "@/lib/api";

export function OnboardingClient() {
  const router = useRouter();
  const { profile, profileLoading, dataError, setProfile, refreshAll, reportDataError } = useAppData();
  const [linkedinFile, setLinkedinFile] = useState<File | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinText, setLinkedinText] = useState("");
  const [manualInfo, setManualInfo] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [stage, setStage] = useState<"form" | "analyzing" | "review">("form");
  const [progress, setProgress] = useState("");
  const [progressValue, setProgressValue] = useState(0);
  const [activeStep, setActiveStep] = useState(0);
  const [error, setError] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [skillReviewSkipped, setSkillReviewSkipped] = useState(false);
  const selectedSkillsRef = useRef<string[]>([]);
  const skillReviewSkippedRef = useRef(false);
  const cvPreview = useCvPreview(setProfile);
  const hasCv = Boolean(profile?.sources.some((source) => source.source_type === "cv"));

  useEffect(() => {
    if (!profile || stage !== "form") return;
    setGithubUrl(profile.github_url);
    setLinkedinText(profile.linkedin_text);
    setManualInfo(profile.manual_info);
    setInterests(profile.career_interests);
  }, [profile?.id, stage]);

  useEffect(() => {
    if (stage !== "analyzing" || !cvPreview.active) return;
    setActiveStep(cvPreview.preview.status === "uploading" ? 0 : 1);
    setProgressValue(Math.max(4, Math.min(55, cvPreview.preview.progress * .55)));
    setProgress(cvPreview.preview.detail);
  }, [cvPreview.active, cvPreview.preview.detail, cvPreview.preview.progress, cvPreview.preview.status, stage]);

  function selectSkills(values: string[]) {
    selectedSkillsRef.current = values;
    setSelectedSkills(values);
  }

  function toggleSkill(skill: string) {
    skillReviewSkippedRef.current = false;
    setSkillReviewSkipped(false);
    const next = selectedSkillsRef.current.includes(skill)
      ? selectedSkillsRef.current.filter((value) => value !== skill)
      : [...selectedSkillsRef.current, skill];
    selectSkills(next);
  }

  function confirmAllSkills() {
    skillReviewSkippedRef.current = false;
    setSkillReviewSkipped(false);
    selectSkills(cvPreview.skills);
  }

  function skipSkillReview() {
    skillReviewSkippedRef.current = true;
    setSkillReviewSkipped(true);
    selectSkills([]);
  }

  function startCvPreview(file: File | null) {
    setError("");
    selectSkills([]);
    skillReviewSkippedRef.current = false;
    setSkillReviewSkipped(false);
    cvPreview.start(file);
  }

  async function buildProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasCv && !cvPreview.file) {
      setError("Upload your CV to build the profile.");
      return;
    }
    if (!interests.length) {
      setError("Choose at least one career interest.");
      return;
    }
    setStage("analyzing");
    setError("");
    setActiveStep(0);
    setProgressValue(4);
    setProgress("Finishing your CV preview");
    try {
      const pendingPreview = cvPreview.wait();
      if (pendingPreview) await pendingPreview;
      let resolvedLinkedinText = linkedinText;
      if (linkedinFile) {
        setActiveStep(2);
        setProgressValue(58);
        setProgress("Adding LinkedIn context");
        const uploaded = await uploadLinkedInPdf(linkedinFile);
        setProfile(uploaded);
        setLinkedinFile(null);
        if (!resolvedLinkedinText.trim()) resolvedLinkedinText = uploaded.linkedin_text;
      }
      setActiveStep(2);
      setProgressValue(70);
      setProgress("Connecting CV, GitHub, LinkedIn, and your notes");
      setActiveStep(3);
      setProgressValue(82);
      setProgress("Building and cross-checking your evidence profile");
      const result = await analyzeOnboardingProfile({
        github_url: githubUrl,
        linkedin_text: resolvedLinkedinText,
        manual_info: manualInfo,
        career_interests: interests
      });
      let completedProfile = result.profile;
      const confirmedValues = skillReviewSkippedRef.current ? [] : selectedSkillsRef.current;
      const confirmedIds = completedProfile.facts
        .filter((fact) => fact.fact_type === "skill" && confirmedValues.includes(fact.value))
        .map((fact) => fact.id);
      if (confirmedIds.length) {
        setProgressValue(94);
        setProgress("Saving the skills you confirmed");
        completedProfile = await bulkUpdateProfileFacts(confirmedIds, "approved");
      }
      setProfile(completedProfile);
      cvPreview.clearFile();
      setProgressValue(100);
      setProgress("Profile analysis complete");
      if (completedProfile.status !== "ready") {
        setError(profileAnalysisError(completedProfile.status));
        setStage("form");
        return;
      }
      setProgress("");
      setStage("review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not build your profile.");
      setProgress("");
      setStage("form");
    }
  }

  function finish() {
    if (profile?.status !== "ready") {
      setError(profileAnalysisError(profile?.status ?? "needs_analysis"));
      setStage("form");
      return;
    }
    const previousProfile = profile;
    markOnboardingSyncing();
    setProfile({ ...profile, onboarding_completed: true });
    setError("");
    const completion = completeOnboarding();
    router.replace("/");
    void completion
      .then((completed) => {
        clearOnboardingSyncing();
        setProfile(completed);
        void refreshAll().catch(() => undefined);
      })
      .catch((err) => {
        clearOnboardingSyncing();
        setProfile(previousProfile);
        reportDataError(err instanceof Error ? err.message : "Could not finish onboarding.");
        router.replace("/onboarding");
      });
  }

  if (stage === "analyzing") {
    return (
      <LongTaskProgress
        activeStep={activeStep}
        detail={progress || "Preparing your evidence"}
        mode="page"
        progress={progressValue}
        steps={[
          { label: "Secure upload", detail: "Store the selected sources" },
          { label: "Read your CV", detail: "Use local OCR only if PDF text is unreadable" },
          { label: "Connect evidence", detail: "Cross-check optional professional sources" },
          { label: "Build your profile", detail: "Extract facts and clarification questions" }
        ]}
        title={activeStep < 2 ? "Reading your professional story" : "Building your evidence profile"}
      >
        <SkillConfirmationPanel
          onConfirmAll={confirmAllSkills}
          onSkip={skipSkillReview}
          onToggle={toggleSkill}
          selected={selectedSkills}
          skipped={skillReviewSkipped}
          skills={cvPreview.skills}
        />
      </LongTaskProgress>
    );
  }

  if (stage === "review") {
    const openQuestions = profile?.questions.filter((question) => question.status === "open").length ?? 0;
    return (
      <main className="onboarding-shell">
        <section className="onboarding-complete">
          <span className="onboarding-logo"><FileCheck2 size={26} /></span>
          <h1>Your profile is ready.</h1>
          <p>{profile?.summary}</p>
          <div className="onboarding-result-stats">
            <div><strong>{profile?.facts.length ?? 0}</strong><span>facts extracted</span></div>
            <div><strong>{profile?.career_interests.length ?? interests.length}</strong><span>career interests</span></div>
            <div><strong>{openQuestions}</strong><span>questions to refine later</span></div>
          </div>
          {error ? <div className="notice error">{error}</div> : null}
          <button className="button primary onboarding-continue" onClick={finish} type="button">
            Enter CareerFit <ArrowRight size={16} />
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="onboarding-shell">
      <header className="onboarding-header">
        <div className="brand">
          <span className="brand-mark"><Waypoints size={18} /></span>
          <span className="brand-copy"><strong>CareerFit</strong><small>Build your profile</small></span>
        </div>
        <span>One required source. Everything else improves the signal.</span>
      </header>

      <form className="onboarding-layout" onSubmit={buildProfile}>
        <section className="onboarding-intro">
          <span>Set up your profile</span>
          <h1>Start with evidence.<br /><em>Finish with direction.</em></h1>
          <p>We turn your CV and optional professional sources into the profile used for every job match.</p>
          <ol className="onboarding-steps">
            <li className="active"><strong>01</strong><span>Upload your CV</span></li>
            <li><strong>02</strong><span>Add useful context</span></li>
            <li><strong>03</strong><span>Choose your direction</span></li>
          </ol>
        </section>

        <div className="onboarding-form-panel">
          {error || dataError ? <div className="notice error">{error || dataError}</div> : null}
          <section className="onboarding-section">
            <div className="onboarding-section-heading"><span>01</span><div><h2>Your CV</h2><p>The required source for profile analysis.</p></div></div>
            <label className="onboarding-upload">
              <FileCheck2 size={22} />
              <span><strong>{cvPreview.file?.name || (hasCv ? "CV already uploaded" : "Choose a CV PDF")}</strong><small>{hasCv ? "Choose another file to replace it." : "PDF, up to your configured upload limit."}</small></span>
              <input accept="application/pdf" disabled={cvPreview.active} onChange={(event) => startCvPreview(event.target.files?.[0] ?? null)} type="file" />
            </label>
            <CvDiscoveryPanel preview={cvPreview.preview} skills={cvPreview.skills} />
          </section>

          <section className="onboarding-section">
            <div className="onboarding-section-heading"><span>02</span><div><h2>Add more context</h2><p>Optional sources improve coverage and confidence.</p></div></div>
            <div className="onboarding-fields">
              <label className="field"><span><Github size={14} /> GitHub URL or username</span><input onChange={(event) => setGithubUrl(event.target.value)} placeholder="github.com/username" value={githubUrl} /></label>
              <label className="field"><span><Linkedin size={14} /> LinkedIn PDF</span><input accept="application/pdf" onChange={(event) => setLinkedinFile(event.target.files?.[0] ?? null)} type="file" /></label>
              <label className="field full"><span>LinkedIn profile text</span><textarea onChange={(event) => setLinkedinText(event.target.value)} placeholder="Paste About, Experience, Education, or Projects…" value={linkedinText} /></label>
              <label className="field full"><span>Anything else we should know?</span><textarea onChange={(event) => setManualInfo(event.target.value)} placeholder="Availability, certifications, projects, constraints, or context missing from your CV…" value={manualInfo} /></label>
            </div>
          </section>

          <section className="onboarding-section interests-section">
            <div className="onboarding-section-heading"><span>03</span><div><h2>What are you interested in?</h2><p>Select one or more fields. You can change these later.</p></div></div>
            <CareerInterestPicker onChange={setInterests} selected={interests} />
            <small className="interest-source">Role taxonomy adapted from Goozali’s public Israeli tech job board.</small>
          </section>

          <div className="onboarding-actions">
            <span>{interests.length ? `${interests.length} field${interests.length === 1 ? "" : "s"} selected` : "Choose at least one field"}</span>
            <button className="button primary" disabled={profileLoading} type="submit">
              <Sparkles size={16} /> Build my CareerFit profile
            </button>
          </div>
        </div>
      </form>
    </main>
  );
}

function profileAnalysisError(status: string) {
  if (status === "cv_unreadable") {
    return "We couldn't recover enough text from this CV. Try a clearer scan or upload a text-based PDF, then analyze again.";
  }
  if (status === "needs_cv") {
    return "Upload a readable CV PDF before continuing.";
  }
  return "Profile analysis did not finish. Review your sources and analyze again.";
}
