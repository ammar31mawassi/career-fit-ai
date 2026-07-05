"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Check, FileText, Github, Linkedin, Pencil, Plus, RefreshCw, Save, Sparkles, X } from "lucide-react";
import { useAppData } from "@/components/AppDataProvider";
import { CareerInterestPicker } from "@/components/CareerInterestPicker";
import {
  addProfileFact,
  analyzeProfile,
  answerProfileQuestion,
  formatDate,
  saveProfileSources,
  saveProfilePreferences,
  updateProfileFact,
  uploadCv,
  uploadLinkedInPdf,
  type ProfileFact
} from "@/lib/api";

const ADDABLE_FACT_TYPES = ["skill", "experience", "project", "education", "language", "location", "availability", "about_me"];

export function ProfileClient() {
  const { profile, setProfile, profileLoading, dataError, refreshProfile } = useAppData();
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinText, setLinkedinText] = useState("");
  const [manualInfo, setManualInfo] = useState("");
  const [careerInterests, setCareerInterests] = useState<string[]>([]);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [linkedinFile, setLinkedinFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

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

  const factsByType = useMemo(() => {
    const grouped = new Map<string, ProfileFact[]>();
    for (const fact of profile?.facts ?? []) {
      const list = grouped.get(fact.fact_type) ?? [];
      list.push(fact);
      grouped.set(fact.fact_type, list);
    }
    return grouped;
  }, [profile]);

  const openQuestions = useMemo(
    () => (profile?.questions ?? []).filter((question) => question.status === "open"),
    [profile]
  );
  const visibleFactTypes = useMemo(() => {
    const extracted = Array.from(factsByType.keys());
    return [...ADDABLE_FACT_TYPES, ...extracted.filter((type) => !ADDABLE_FACT_TYPES.includes(type))];
  }, [factsByType]);

  async function submitSources(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const saved = await persistSources();
      setProfile(saved);
      setMessage("Sources saved. Run analysis to rebuild the profile.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile sources.");
    } finally {
      setSaving(false);
    }
  }

  async function runAnalysis() {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await persistSources();
      const result = await analyzeProfile();
      setProfile(result.profile);
      if (result.profile.status === "ready") {
        setMessage(`Profile analyzed: ${result.generated_facts} facts, ${result.open_questions} open questions.`);
      } else if (result.profile.status === "cv_unreadable") {
        setError("We couldn't read text from this CV. Upload a text-based PDF rather than a scanned image, then analyze again.");
      } else {
        setError("Profile analysis did not finish. Review your sources and analyze again.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyze profile.");
    } finally {
      setSaving(false);
    }
  }

  async function persistSources() {
    if (cvFile) {
      await uploadCv(cvFile);
      setCvFile(null);
    }
    if (linkedinFile) {
      await uploadLinkedInPdf(linkedinFile);
      setLinkedinFile(null);
    }
    return saveProfileSources({ github_url: githubUrl, linkedin_text: linkedinText, manual_info: manualInfo });
  }

  async function reviewFact(fact: ProfileFact, value: string, status: ProfileFact["review_status"]) {
    const updated = await updateProfileFact(fact.id, value, status);
    setProfile(updated);
  }

  async function answer(questionId: number, value: string) {
    if (!value.trim()) return;
    const updated = await answerProfileQuestion(questionId, value);
    setProfile(updated);
  }

  async function addFact(type: string, value: string) {
    const updated = await addProfileFact(type, value);
    setProfile(updated);
  }

  async function saveInterests() {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const updated = await saveProfilePreferences(careerInterests);
      setProfile(updated);
      setMessage("Career interests updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save career interests.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
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

      <form className="panel source-form" onSubmit={submitSources}>
        <div className="section-heading">
          <div>
            <span className="section-kicker">Source studio</span>
            <h2>Build your evidence base</h2>
            <p>Your CV anchors the profile. LinkedIn, GitHub, and notes add context and confidence.</p>
          </div>
          <FileText size={20} aria-hidden />
        </div>
        <div className="form-grid">
          <label className="field upload-field">
            <span>CV PDF (required)</span>
            <input accept="application/pdf" onChange={(event) => setCvFile(event.target.files?.[0] ?? null)} type="file" />
            <small>{profile?.sources.find((source) => source.source_type === "cv") ? "CV uploaded; selecting a new file replaces it." : "Upload one CV to unlock matching."}</small>
          </label>
          <label className="field upload-field">
            <span>LinkedIn PDF (optional)</span>
            <input accept="application/pdf" onChange={(event) => setLinkedinFile(event.target.files?.[0] ?? null)} type="file" />
            <small>Use PDF export or paste text below. No LinkedIn scraping.</small>
          </label>
        </div>
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
          <button className="button primary" disabled={saving} onClick={() => void saveInterests()} type="button"><Save size={16} /> Save interests</button>
        </div>
      </section>

      <section className={`content-grid ${openQuestions.length ? "" : "single"}`}>
        <div className="panel facts-panel">
          <div className="section-heading facts-heading">
            <div><span className="section-kicker">Evidence map</span><h2>Profile facts</h2></div>
            <span className="review-count">{profile?.facts.filter((fact) => fact.review_status === "approved").length ?? 0} confirmed</span>
          </div>
          <div className="fact-groups">
            {visibleFactTypes.map((type) => (
              <FactGroup
                addable={ADDABLE_FACT_TYPES.includes(type)}
                facts={factsByType.get(type) ?? []}
                key={type}
                onAdd={addFact}
                onReview={reviewFact}
                type={type}
              />
            ))}
          </div>
        </div>

        {openQuestions.length ? <div className="panel questions-panel">
          <span className="section-kicker">Complete the signal</span>
          <h2>A few things need your input</h2>
          <p className="panel-intro">Each answer disappears once saved and may reveal the next useful question.</p>
          <div className="question-list">
            {openQuestions.map((question) => <QuestionRow key={question.id} question={question} onAnswer={answer} />)}
          </div>
        </div> : null}
      </section>
    </>
  );
}

function FactGroup({
  type,
  facts,
  addable,
  onAdd,
  onReview
}: {
  type: string;
  facts: ProfileFact[];
  addable: boolean;
  onAdd: (type: string, value: string) => Promise<void>;
  onReview: (fact: ProfileFact, value: string, status: ProfileFact["review_status"]) => Promise<void>;
}) {
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const label = type.replaceAll("_", " ");

  async function save() {
    if (!value.trim()) return;
    setSaving(true);
    try {
      await onAdd(type, value);
      setValue("");
      setAdding(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="fact-group">
      <div className="fact-group-heading">
        <h3>{label}</h3>
        {addable ? <button className="add-fact-button" onClick={() => setAdding((current) => !current)} type="button"><Plus size={13} /> Add</button> : null}
      </div>
      {adding ? <div className="add-fact-form">
        <input autoFocus onChange={(event) => setValue(event.target.value)} placeholder={`Add ${label}`} value={value} />
        <button className="button compact primary" disabled={saving || !value.trim()} onClick={() => void save()} type="button">Save</button>
        <button className="button compact quiet" disabled={saving} onClick={() => { setAdding(false); setValue(""); }} type="button">Cancel</button>
      </div> : null}
      {facts.length ? facts.map((fact) => <FactRow fact={fact} key={fact.id} onReview={onReview} />) : <p className="fact-empty">Nothing added yet.</p>}
    </section>
  );
}

function FactRow({
  fact,
  onReview
}: {
  fact: ProfileFact;
  onReview: (fact: ProfileFact, value: string, status: ProfileFact["review_status"]) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(fact.value);
  const [saving, setSaving] = useState(false);

  async function review(status: ProfileFact["review_status"]) {
    setSaving(true);
    try {
      await onReview(fact, value, status);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={`fact-row ${fact.review_status}`}>
      {editing ? (
        <input onChange={(event) => setValue(event.target.value)} value={value} />
      ) : (
        <div>
          <strong>{fact.value}</strong>
          <span>{Math.round(fact.confidence * 100)}% confidence · {fact.support_count} {fact.support_count === 1 ? "source" : "sources"} · {fact.review_status}</span>
          <p>{fact.evidence}</p>
        </div>
      )}
      <div className="fact-actions">
        {editing ? (
          <>
            <button className="button compact" disabled={saving} onClick={() => { setValue(fact.value); setEditing(false); }} type="button">Cancel</button>
            <button className="button compact primary" disabled={saving || !value.trim()} onClick={() => void review("approved")} type="button"><Check size={13} /> Save &amp; confirm</button>
          </>
        ) : (
          <>
            {fact.review_status !== "approved" ? <button className="button compact approve" disabled={saving} onClick={() => void review("approved")} type="button"><Check size={13} /> Confirm</button> : null}
            {fact.review_status !== "rejected" ? <button className="button compact reject" disabled={saving} onClick={() => void review("rejected")} type="button"><X size={13} /> Reject</button> : null}
            <button className="button compact" disabled={saving} onClick={() => setEditing(true)} type="button"><Pencil size={13} /> Edit</button>
          </>
        )}
      </div>
    </div>
  );
}

function QuestionRow({
  question,
  onAnswer
}: {
  question: { id: number; question: string; status: string; answer: string };
  onAnswer: (id: number, answer: string) => Promise<void>;
}) {
  const [answer, setAnswer] = useState(question.answer);
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      await onAnswer(question.id, answer);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="question-row">
      <span className={`chip ${question.status === "answered" ? "ready-chip" : ""}`}>{question.status}</span>
      <strong>{question.question}</strong>
      <textarea onChange={(event) => setAnswer(event.target.value)} value={answer} />
      <button className="button compact" disabled={saving || !answer.trim()} onClick={() => void submit()} type="button">Save answer</button>
    </div>
  );
}
