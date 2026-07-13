"use client";

import { useState } from "react";
import { ArrowUpRight, BookmarkPlus, Sparkles, X } from "lucide-react";
import {
  updateRecommendation,
  type JobRecommendation,
  type TrackedJob
} from "@/lib/api";

export function RecommendedMatches({
  items,
  loading,
  onItemsChange,
  onSaved
}: {
  items: JobRecommendation[];
  loading: boolean;
  onItemsChange: (items: JobRecommendation[]) => void;
  onSaved: (job: TrackedJob) => void;
}) {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function dismiss(item: JobRecommendation) {
    const previous = items;
    onItemsChange(items.filter((candidate) => candidate.id !== item.id));
    setError("");
    try {
      await updateRecommendation(item.id, "dismissed");
    } catch (caught) {
      onItemsChange(previous);
      setError(caught instanceof Error ? caught.message : "Could not dismiss the recommendation.");
    }
  }

  async function save(item: JobRecommendation) {
    setBusyId(item.id);
    setError("");
    try {
      const result = await updateRecommendation(item.id, "saved");
      onItemsChange(items.filter((candidate) => candidate.id !== item.id));
      if (result.job) onSaved(result.job);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save the recommendation.");
    } finally {
      setBusyId(null);
    }
  }

  if (!loading && !items.length) return null;

  return (
    <section className="recommendation-rail" aria-busy={loading} aria-labelledby="recommendation-title">
      <div className="recommendation-heading">
        <div>
          <span className="section-kicker"><Sparkles size={13} /> Shared signal</span>
          <h2 id="recommendation-title">Strong roles found for you</h2>
          <p>Jobs scanned by the community, shortlisted by your interests and scored only against your private profile.</p>
        </div>
        <span className="recommendation-privacy">Opt-in · private scoring</span>
      </div>
      {error ? <div className="notice error compact-notice" role="alert">{error}</div> : null}
      <div className="recommendation-track">
        {loading && !items.length ? [0, 1].map((item) => <div className="recommendation-card is-loading" key={item}><span className="skeleton-block wide" /><span className="skeleton-block text" /></div>) : null}
        {items.map((item) => (
          <article className="recommendation-card" key={item.id}>
            <div className="recommendation-score"><strong>{Math.round(item.score)}%</strong><span>{item.fit_level}</span></div>
            <div className="recommendation-copy">
              <span>{item.company}</span>
              <h3>{item.role}</h3>
              <p>{item.reasons[0] || "Strong evidence alignment with your approved profile."}</p>
              <div className="recommendation-tags">{item.career_fields.slice(0, 2).map((field) => <span key={field}>{field}</span>)}{item.location ? <span>{item.location}</span> : null}</div>
            </div>
            <div className="recommendation-actions">
              <button aria-label={`Dismiss ${item.role}`} className="icon-button" disabled={busyId === item.id} onClick={() => void dismiss(item)} title="Dismiss" type="button"><X size={15} /></button>
              {item.source_url || item.application_link ? <a aria-label={`Open ${item.role}`} className="icon-button" href={item.application_link || item.source_url} rel="noreferrer" target="_blank" title="Open job"><ArrowUpRight size={15} /></a> : null}
              <button className="button compact primary" disabled={busyId === item.id} onClick={() => void save(item)} type="button"><BookmarkPlus size={14} /> {busyId === item.id ? "Saving…" : "Save to radar"}</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
