"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { FileCheck2, FileText, Github, Linkedin, RefreshCw, Save, ScanText, Sparkles, UploadCloud } from "lucide-react";
import { useAppData } from "@/components/AppDataProvider";
import { CareerInterestPicker } from "@/components/CareerInterestPicker";
import { LongTaskProgress } from "@/components/LongTaskProgress";
import { ClarificationPanel } from "@/components/profile/ClarificationPanel";
import { AccountControls } from "@/components/profile/AccountControls";
import { ProfileFactsEditor } from "@/components/profile/ProfileFactsEditor";
import { recognizePdfInBrowser } from "@/lib/browserOcr";
import {
  addProfileFact,
  analyzeProfile,
  answerProfileQuestion,
  bulkUpdateProfileFacts,
  formatDate,
  saveBrowserOcr,
  saveProfileSources,
  saveProfilePreferences,
  updateProfileFact,
  uploadCv,
  uploadLinkedInPdf,
  type ProfileFact
} from "@/lib/api";

export function ProfileClient() {
  const { profile, setProfile, profileLoading, dataError, refreshProfile } = useAppData();
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinText, setLinkedinText] = useState("");
  const [manualInfo, setManualInfo] = useState("");
  const [careerInterests, setCareerInterests] = useState<string[]>([]);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [linkedinFile, setLinkedinFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [interestsSyncing, setInterestsSyncing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [task, setTask] = useState<{ title: string; detail: string; progress: number; activeStep: number } | null>(null);

  async function refresh() {
    await refreshProfile();
  }

  useEffect(() => {
    if (!profile) return;
    setGithubUrl(profile.github_url);
    setLinkedinText(profile.linkedin_text);
    setManualInfo(profile.manual_info);
    setCareerInterests(profile.career_interests);
  }, [profile?.id, profile?.github_url, profile?.linkedin_text, profile?.manual_info, profile?.career_interests]);

  const openQuestions = useMemo(
    () => (profile?.questions ?? []).filter((question) => question.status === "open"),
    [profile]
  );
  const cvSource = profile?.sources.find((source) => source.source_type === "cv");
  const linkedinSource = profile?.sources.find((source) => source.source_type === "linkedin_pdf");
  async function submitSources(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    setTask({ title: "Updating your evidence", detail: "Preparing your selected sources", progress: 4, activeStep: 0 });
    try {
      const saved = await persistSources();
      setProfile(saved);
      setMessage("Sources saved. Run analysis to rebuild the profile.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile sources.");
    } finally {
      setSaving(false);
      setTask(null);
    }
  }

  async function runAnalysis() {
    setSaving(true);
    setError("");
    setMessage("");
    setTask({ title: "Rebuilding your profile", detail: "Preparing your selected sources", progress: 4, activeStep: 0 });
    try {
      await persistSources();
      setTask({ title: "Rebuilding your profile", detail: "Extracting facts and checking supporting evidence", progress: 82, activeStep: 3 });
      const result = await analyzeProfile();
      setProfile(result.profile);
      if (result.profile.status === "ready") {
        setMessage(`Profile analyzed: ${result.generated_facts} facts, ${result.open_questions} open questions.`);
      } else if (result.profile.status === "cv_unreadable") {
        setError("We couldn't recover enough text from this CV. Try a clearer scan or upload a text-based PDF, then analyze again.");
      } else {
        setError("Profile analysis did not finish. Review your sources and analyze again.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyze profile.");
    } finally {
      setSaving(false);
      setTask(null);
    }
  }

  async function persistSources() {
    if (cvFile) {
      const selectedCv = cvFile;
      setTask((current) => ({
        title: current?.title || "Updating your evidence",
        detail: "Securely uploading your CV",
        progress: 8,
        activeStep: 0
      }));
      let uploaded = await uploadCv(selectedCv);
      setProfile(uploaded);
      const uploadedCv = uploaded.sources.find((source) => source.source_type === "cv");
      if (uploadedCv?.ocr_recommended) {
        setTask((current) => ({ ...(current || { title: "Reading your CV", activeStep: 1 }), detail: "Preparing private browser OCR", progress: 18, activeStep: 1 }));
        const ocr = await recognizePdfInBrowser(selectedCv, (update) => {
          setTask((current) => ({
            title: current?.title || "Reading your CV",
            detail: update.detail,
            progress: 18 + update.progress * 46,
            activeStep: 1
          }));
        });
        uploaded = await saveBrowserOcr(ocr);
        setProfile(uploaded);
      }
      setCvFile(null);
    }
    if (linkedinFile) {
      setTask((current) => ({
        title: current?.title || "Updating your evidence",
        detail: "Reading your LinkedIn export",
        progress: 66,
        activeStep: 2
      }));
      await uploadLinkedInPdf(linkedinFile);
      setLinkedinFile(null);
    }
    setTask((current) => ({
      title: current?.title || "Updating your evidence",
      detail: "Connecting CV, GitHub, LinkedIn, and your notes",
      progress: 72,
      activeStep: 2
    }));
    return saveProfileSources({ github_url: githubUrl, linkedin_text: linkedinText, manual_info: manualInfo });
  }

  async function reviewFact(fact: ProfileFact, value: string, status: ProfileFact["review_status"]) {
    setError("");
    setProfile((current) => current ? {
      ...current,
      facts: current.facts.map((item) => item.id === fact.id ? {
        ...item,
        value,
        review_status: status,
        user_approved: status === "approved"
      } : item)
    } : current);
    try {
      setProfile(await updateProfileFact(fact.id, value, status));
    } catch (caught) {
      setProfile((current) => current ? {
        ...current,
        facts: current.facts.map((item) => item.id === fact.id ? fact : item)
      } : current);
      setError(caught instanceof Error ? `Fact update was rolled back: ${caught.message}` : "Fact update was rolled back.");
    }
  }

  async function reviewFacts(facts: ProfileFact[], status: "approved" | "rejected") {
    const originals = new Map(facts.map((fact) => [fact.id, fact]));
    const ids = facts.map((fact) => fact.id);
    setError("");
    setProfile((current) => current ? {
      ...current,
      facts: current.facts.map((fact) => originals.has(fact.id) ? {
        ...fact,
        review_status: status,
        user_approved: status === "approved"
      } : fact)
    } : current);
    try {
      setProfile(await bulkUpdateProfileFacts(ids, status));
    } catch (caught) {
      setProfile((current) => current ? {
        ...current,
        facts: current.facts.map((fact) => originals.get(fact.id) ?? fact)
      } : current);
      const message = caught instanceof Error ? caught.message : "Could not save the selected reviews.";
      setError(`Bulk review was rolled back: ${message}`);
      throw caught;
    }
  }

  async function answer(questionId: number, value: string) {
    if (!value.trim()) return;
    const originalQuestion = profile?.questions.find((question) => question.id === questionId);
    setError("");
    setProfile((current) => current ? {
      ...current,
      questions: current.questions.filter((question) => question.id !== questionId)
    } : current);
    try {
      setProfile(await answerProfileQuestion(questionId, value));
    } catch (caught) {
      if (originalQuestion) {
        setProfile((current) => current ? {
          ...current,
          questions: current.questions.some((question) => question.id === questionId)
            ? current.questions
            : [...current.questions, originalQuestion]
        } : current);
      }
      setError(caught instanceof Error ? `Answer was restored: ${caught.message}` : "Answer was restored because it could not be saved.");
    }
  }

  async function addFact(type: string, value: string) {
    const temporaryId = -Date.now();
    setError("");
    setProfile((current) => current ? {
      ...current,
      facts: [...current.facts, {
        id: temporaryId,
        fact_type: type,
        value,
        evidence: "Added manually by you.",
        confidence: 1,
        user_approved: true,
        review_status: "approved",
        support_count: 1,
        source_ids: [],
        source_id: null
      }]
    } : current);
    try {
      setProfile(await addProfileFact(type, value));
    } catch (caught) {
      setProfile((current) => current ? {
        ...current,
        facts: current.facts.filter((item) => item.id !== temporaryId)
      } : current);
      setError(caught instanceof Error ? `New fact was removed: ${caught.message}` : "New fact was removed because it could not be saved.");
    }
  }

  async function saveInterests() {
    const previousInterests = profile?.career_interests ?? [];
    setInterestsSyncing(true);
    setError("");
    setMessage("Career interests updated.");
    setProfile((current) => current ? { ...current, career_interests: careerInterests } : current);
    try {
      const updated = await saveProfilePreferences(careerInterests);
      setProfile(updated);
    } catch (err) {
      setProfile((current) => current ? { ...current, career_interests: previousInterests } : current);
      setError(err instanceof Error ? `Interest changes were rolled back: ${err.message}` : "Interest changes were rolled back.");
      setMessage("");
    } finally {
      setInterestsSyncing(false);
    }
  }

  return (
    <>
      {task ? (
        <LongTaskProgress
          activeStep={task.activeStep}
          detail={task.detail}
          progress={task.progress}
          steps={[
            { label: "Secure upload" },
            { label: "Read CV", detail: "Local OCR runs only when needed" },
            { label: "Connect evidence" },
            { label: "Rebuild profile" }
          ]}
          title={task.title}
        />
      ) : null}
      <header className="page-heading profile-hero">
        <div>
          <span className="eyebrow"><Sparkles size={14} /> Profile intelligence</span>
          <h1>Your evidence,<br /><em>under your control.</em></h1>
          <p>Connect your sources, review every extracted fact, and shape the profile used for job matching.</p>
        </div>
        <button className="button quiet" onClick={() => void refresh()} type="button"><RefreshCw size={16} /> Refresh</button>
      </header>

      {error || dataError ? <div className="notice error">{error || dataError}</div> : null}
      {message ? <div className="notice success">{message}</div> : null}

      <section className="profile-status">
        <div className={profile?.status === "ready" ? "status-card ready" : "status-card warning"}>
          <span>Profile state</span>
          <strong>{profileLoading ? "Syncing…" : profile?.status === "ready" ? "Ready to match" : "Needs attention"}</strong>
          <p>{profile?.summary || "Upload a CV to build an evidence-backed profile."}</p>
        </div>
        <div className="status-card">
          <span>Evidence footprint</span>
          <strong>{formatDate(profile?.last_analyzed_at ?? null)}</strong>
          <p>{profile?.sources.length ?? 0} sources · {profile?.facts.length ?? 0} facts · {openQuestions.length} open questions</p>
        </div>
      </section>

      <section className={`content-grid profile-review-grid ${openQuestions.length ? "" : "single"}`}>
        <ProfileFactsEditor facts={profile?.facts ?? []} onAdd={addFact} onBulkReview={reviewFacts} onReview={reviewFact} />
        {openQuestions.length ? <ClarificationPanel onAnswer={answer} questions={openQuestions} /> : null}
      </section>

      <form className="panel source-form" onSubmit={submitSources}>
        <div className="section-heading">
          <div>
            <span className="section-kicker">Source studio</span>
            <h2>Build your evidence base</h2>
            <p>Your CV anchors the profile. LinkedIn, GitHub, and notes add context and confidence.</p>
          </div>
          <FileText size={20} aria-hidden />
        </div>
        <div className="form-grid source-upload-grid">
          <label className={`source-upload-card ${cvFile || cvSource ? "has-file" : ""}`}>
            <input accept="application/pdf" onChange={(event) => setCvFile(event.target.files?.[0] ?? null)} type="file" />
            <span className="source-upload-icon">{cvFile || cvSource ? <FileCheck2 size={20} /> : <UploadCloud size={20} />}</span>
            <span className="source-upload-copy">
              <strong>{cvFile?.name || cvSource?.title || "Choose your CV PDF"}</strong>
              <small>{cvSource ? "Ready · choose another file to replace it" : "Required to unlock matching"}</small>
            </span>
            <span className="source-upload-action">{cvFile || cvSource ? "Replace" : "Browse"}</span>
          </label>
          <label className={`source-upload-card ${linkedinFile || linkedinSource ? "has-file" : ""}`}>
            <input accept="application/pdf" onChange={(event) => setLinkedinFile(event.target.files?.[0] ?? null)} type="file" />
            <span className="source-upload-icon">{linkedinFile || linkedinSource ? <FileCheck2 size={20} /> : <UploadCloud size={20} />}</span>
            <span className="source-upload-copy">
              <strong>{linkedinFile?.name || linkedinSource?.title || "Add a LinkedIn PDF"}</strong>
              <small>Optional · PDF export or pasted text</small>
            </span>
            <span className="source-upload-action">{linkedinFile || linkedinSource ? "Replace" : "Browse"}</span>
          </label>
        </div>
        {cvSource?.scanned_pdf_detected ? (
          <div className={`source-read-status ${["ocr_service", "browser_ocr"].includes(cvSource.read_method) ? "recovered" : "warning"}`}>
            <ScanText size={17} />
            <div>
              <strong>{["ocr_service", "browser_ocr"].includes(cvSource.read_method) ? `${cvSource.read_method === "browser_ocr" ? "Scanned CV recovered privately in your browser" : "Scanned CV recovered with OCR"}` : "Scanned CV needs a clearer source"}</strong>
              <span>{["ocr_service", "browser_ocr"].includes(cvSource.read_method) && cvSource.ocr_confidence !== null ? `${Math.round(cvSource.ocr_confidence * 100)}% OCR confidence · review extracted facts below` : "OCR could not recover enough reliable text. A text-based PDF will give better results."}</span>
            </div>
          </div>
        ) : null}
        <label className="field">
          <span><Github size={14} /> GitHub URL or username (optional)</span>
          <input onChange={(event) => setGithubUrl(event.target.value)} placeholder="https://github.com/username" value={githubUrl} />
        </label>
        <label className="field">
          <span><Linkedin size={14} /> LinkedIn profile text (optional)</span>
          <textarea onChange={(event) => setLinkedinText(event.target.value)} placeholder="Paste profile About, Experience, Education, Projects..." value={linkedinText} />
        </label>
        <label className="field">
          <span>Extra typed info (optional)</span>
          <textarea onChange={(event) => setManualInfo(event.target.value)} placeholder="Availability, preferred roles, location constraints, missing projects, experience details..." value={manualInfo} />
        </label>
        <div className="form-actions">
          <button className="button" disabled={saving} type="submit"><Save size={16} /> Save sources</button>
          <button className="button primary" disabled={saving || !profile?.sources.some((source) => source.source_type === "cv") && !cvFile} onClick={() => void runAnalysis()} type="button">
            <Sparkles size={16} /> Analyze profile
          </button>
        </div>
      </form>

      <section className="panel profile-interests-panel">
        <div className="section-heading">
          <div>
            <span className="section-kicker">Career direction</span>
            <h2>Fields you want to explore</h2>
            <p>These preferences guide future discovery and filtering. They do not inflate your qualification score.</p>
          </div>
          <span className="review-count">{careerInterests.length} selected</span>
        </div>
        <CareerInterestPicker disabled={saving} onChange={setCareerInterests} selected={careerInterests} />
        <div className="form-actions">
          <button className="button primary" disabled={interestsSyncing} onClick={() => void saveInterests()} type="button"><Save size={16} /> {interestsSyncing ? "Saved · syncing" : "Save interests"}</button>
        </div>
      </section>

      <AccountControls />
    </>
  );
}
