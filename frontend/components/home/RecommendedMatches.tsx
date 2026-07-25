"use client";

import { useState, type CSSProperties } from "react";
import { ArrowUpRight, BookmarkPlus, MapPin, Radar, RefreshCw, Sparkles, X } from "lucide-react";
import {
  updateRecommendation,
  type JobRecommendation,
  type TrackedJob
} from "@/lib/api";

export function RecommendedMatches({
  items,
  loading,
  onItemsChange,
  onSaved,
  onRefresh,
  showEmpty = false
}: {
  items: JobRecommendation[];
  loading: boolean;
  onItemsChange: (items: JobRecommendation[]) => void;
  onSaved: (job: TrackedJob) => void;
  onRefresh?: () => void;
  showEmpty?: boolean;
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

  if (!loading && !items.length && !showEmpty) return null;

  return (
    <section className={`recommendation-rail ${showEmpty ? "discovery-feed" : ""}`} aria-busy={loading} aria-labelledby="recommendation-title">
      <div className="recommendation-heading">
        <div>
          <span className="section-kicker"><Sparkles size={13} /> Private discovery</span>
          <h2 id="recommendation-title">{items.length ? "Your strongest matches" : "Your discovery feed"}</h2>
          <p>Filtered by your career direction, then scored against evidence in your private profile.</p>
        </div>
        <span className="recommendation-privacy">{items.length ? `${items.length} live ${items.length === 1 ? "match" : "matches"}` : "Private scoring"}</span>
      </div>
      {error ? <div className="notice error compact-notice" role="alert">{error}</div> : null}
      <div className="recommendation-track">
        {loading && !items.length ? [0, 1, 2].map((item) => <div className="recommendation-card is-loading" key={item}><span className="skeleton-block wide" /><span className="skeleton-block text" /></div>) : null}
        {!loading && !items.length && showEmpty ? (
          <div className="recommendation-empty">
            <span className="recommendation-empty-radar"><Radar size={24} /></span>
            <div><strong>No confident match yet</strong><p>Discovery is working. New Goozali and community-scanned roles will appear here as soon as they clear your experience, direction, evidence, and confidence checks.</p></div>
            {onRefresh ? <button className="button quiet" onClick={onRefresh} type="button"><RefreshCw size={15} /> Check now</button> : null}
          </div>
        ) : null}
        {items.map((item) => {
          const score = Math.max(0, Math.min(100, Math.round(item.score)));
          return (
            <article className="recommendation-card" key={item.id}>
              <div
                className={`recommendation-score score-${item.fit_level.toLowerCase()}`}
                style={{ "--score": `${score}%` } as CSSProperties}
              >
                <strong>{score}%</strong><span>{item.fit_level}</span>
              </div>
              <div className="recommendation-copy">
                <span>{item.company || "Company not listed"}</span>
                <h3>{item.role}</h3>
                <small className="recommendation-reason-label">Why it fits</small>
                <p>{item.reasons[0] || "Strong evidence alignment with your approved profile."}</p>
                <div className="recommendation-tags">
                  <span>{item.source_name === "goozali" ? "Goozali" : "Community scan"}</span>
                  {item.career_fields.slice(0, 1).map((field) => <span key={field}>{field}</span>)}
                  {item.location ? <span><MapPin size={11} aria-hidden />{item.location}</span> : null}
                </div>
              </div>
              <div className="recommendation-actions">
                <button aria-label={`Dismiss ${item.role}`} className="icon-button" disabled={busyId === item.id} onClick={() => void dismiss(item)} title="Not for me" type="button"><X size={15} /></button>
                {item.source_url || item.application_link ? (
                  <a className="button compact recommendation-open" href={item.application_link || item.source_url} rel="noreferrer" target="_blank">
                    View job <ArrowUpRight size={14} />
                  </a>
                ) : null}
                <button className="button compact primary" disabled={busyId === item.id} onClick={() => void save(item)} type="button"><BookmarkPlus size={14} /> {busyId === item.id ? "Saving…" : "Save"}</button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
