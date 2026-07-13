"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Check, ChevronDown, SlidersHorizontal, X } from "lucide-react";
import { reviewJobRequirements, type JobRequirementsReview, type TrackedJob } from "@/lib/api";

function joined(values: string[]) {
  return values.join(", ");
}

function splitSkills(value: string) {
  return [...new Set(value.split(/[,\n]/).map((item) => item.trim().toLowerCase()).filter(Boolean))];
}

export function RequirementReviewPanel({ job, onSaved }: { job: TrackedJob; onSaved: (job: TrackedJob) => void }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [must, setMust] = useState(joined(job.requirements.must_have_skills));
  const [preferred, setPreferred] = useState(joined(job.requirements.preferred_skills));
  const [nice, setNice] = useState(joined(job.requirements.nice_to_have_skills));
  const [years, setYears] = useState(String(job.requirements.min_years_experience || 0));
  const [known, setKnown] = useState(job.requirements.experience_requirement_known);
  const [seniority, setSeniority] = useState(job.requirements.seniority);
  const [workMode, setWorkMode] = useState(job.requirements.work_mode);
  const [location, setLocation] = useState(job.requirements.location_requirement);
  const [education, setEducation] = useState(job.requirements.education);
  const [domain, setDomain] = useState(job.requirements.domain);

  useEffect(() => {
    setMust(joined(job.requirements.must_have_skills));
    setPreferred(joined(job.requirements.preferred_skills));
    setNice(joined(job.requirements.nice_to_have_skills));
    setYears(String(job.requirements.min_years_experience || 0));
    setKnown(job.requirements.experience_requirement_known);
    setSeniority(job.requirements.seniority);
    setWorkMode(job.requirements.work_mode);
    setLocation(job.requirements.location_requirement);
    setEducation(job.requirements.education);
    setDomain(job.requirements.domain);
  }, [job]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const payload: JobRequirementsReview = {
      must_have_skills: splitSkills(must),
      preferred_skills: splitSkills(preferred),
      nice_to_have_skills: splitSkills(nice),
      min_years_experience: known ? Math.max(0, Number(years) || 0) : 0,
      experience_requirement_known: known,
      seniority: seniority.trim() || "unspecified",
      education: education.trim(),
      work_mode: workMode.trim(),
      domain: domain.trim(),
      location_requirement: location.trim()
    };
    try {
      onSaved(await reviewJobRequirements(job.id, payload));
      setOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save requirement corrections.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={`analysis-section requirement-review${open ? " open" : ""}`}>
      <button aria-expanded={open} className="requirement-review-toggle" onClick={() => setOpen((current) => !current)} type="button">
        <span><SlidersHorizontal size={15} /><span><strong>Review extracted requirements</strong><small>Correct high-impact reader mistakes before trusting the score.</small></span></span>
        <ChevronDown size={16} aria-hidden />
      </button>
      {open ? (
        <form className="requirement-review-form" onSubmit={submit}>
          <label className="field"><span>Must-have skills</span><textarea onChange={(event) => setMust(event.target.value)} rows={2} value={must} /></label>
          <label className="field"><span>Preferred skills</span><textarea onChange={(event) => setPreferred(event.target.value)} rows={2} value={preferred} /></label>
          <label className="field"><span>Nice-to-have skills</span><textarea onChange={(event) => setNice(event.target.value)} rows={2} value={nice} /></label>
          <div className="requirement-form-grid">
            <label className="field"><span>Seniority</span><select onChange={(event) => setSeniority(event.target.value)} value={seniority}><option value="unspecified">Not stated</option><option value="student">Student / intern</option><option value="junior">Junior</option><option value="experienced">Experienced</option><option value="senior">Senior</option></select></label>
            <label className="field"><span>Work mode</span><input onChange={(event) => setWorkMode(event.target.value)} placeholder="Remote, hybrid, onsite…" value={workMode} /></label>
            <label className="field"><span>Location</span><input onChange={(event) => setLocation(event.target.value)} value={location} /></label>
            <label className="field"><span>Domain</span><input onChange={(event) => setDomain(event.target.value)} value={domain} /></label>
          </div>
          <label className="check-row"><input checked={known} onChange={(event) => setKnown(event.target.checked)} type="checkbox" /><span>The posting explicitly requires professional experience</span></label>
          {known ? <label className="field compact-field"><span>Minimum years</span><input inputMode="decimal" min="0" onChange={(event) => setYears(event.target.value)} step="0.5" type="number" value={years} /></label> : null}
          <label className="field"><span>Education requirement</span><input onChange={(event) => setEducation(event.target.value)} value={education} /></label>
          {error ? <div className="notice error compact-notice" role="alert">{error}</div> : null}
          <div className="requirement-review-actions">
            <button className="button compact quiet" disabled={saving} onClick={() => setOpen(false)} type="button"><X size={14} /> Cancel</button>
            <button className="button compact primary" disabled={saving} type="submit"><Check size={14} /> {saving ? "Recalculating…" : "Save and recalculate"}</button>
          </div>
        </form>
      ) : null}
    </section>
  );
}
