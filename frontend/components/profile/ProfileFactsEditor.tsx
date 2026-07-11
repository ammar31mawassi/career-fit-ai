"use client";

import { useMemo, useState } from "react";
import { Check, Pencil, Plus, X } from "lucide-react";
import type { ProfileFact } from "@/lib/api";

const ADDABLE_FACT_TYPES = ["skill", "experience", "project", "education", "language", "location", "availability", "about_me"];

export function ProfileFactsEditor({
  facts,
  onAdd,
  onReview
}: {
  facts: ProfileFact[];
  onAdd: (type: string, value: string) => Promise<void>;
  onReview: (fact: ProfileFact, value: string, status: ProfileFact["review_status"]) => Promise<void>;
}) {
  const factsByType = useMemo(() => {
    const grouped = new Map<string, ProfileFact[]>();
    for (const fact of facts) grouped.set(fact.fact_type, [...(grouped.get(fact.fact_type) ?? []), fact]);
    return grouped;
  }, [facts]);
  const visibleTypes = useMemo(() => {
    const extracted = Array.from(factsByType.keys());
    return [...ADDABLE_FACT_TYPES, ...extracted.filter((type) => !ADDABLE_FACT_TYPES.includes(type))];
  }, [factsByType]);

  return (
    <div className="panel facts-panel">
      <div className="section-heading facts-heading">
        <div><span className="section-kicker">Evidence map</span><h2>Profile facts</h2></div>
        <span className="review-count">{facts.filter((fact) => fact.review_status === "approved").length} confirmed</span>
      </div>
      <div className="fact-groups">
        {visibleTypes.map((type) => <FactGroup addable={ADDABLE_FACT_TYPES.includes(type)} facts={factsByType.get(type) ?? []} key={type} onAdd={onAdd} onReview={onReview} type={type} />)}
      </div>
    </div>
  );
}
function FactGroup({ type, facts, addable, onAdd, onReview }: {
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
    try { await onAdd(type, value); setValue(""); setAdding(false); } finally { setSaving(false); }
  }

  return (
    <section className="fact-group">
      <div className="fact-group-heading"><h3>{label}</h3>{addable ? <button className="add-fact-button" onClick={() => setAdding((current) => !current)} type="button"><Plus size={13} /> Add</button> : null}</div>
      {adding ? <div className="add-fact-form"><input autoFocus onChange={(event) => setValue(event.target.value)} placeholder={`Add ${label}`} value={value} /><button className="button compact primary" disabled={saving || !value.trim()} onClick={() => void save()} type="button">Save</button><button className="button compact quiet" disabled={saving} onClick={() => { setAdding(false); setValue(""); }} type="button">Cancel</button></div> : null}
      {facts.length ? facts.map((fact) => <FactRow fact={fact} key={fact.id} onReview={onReview} />) : <p className="fact-empty">Nothing added yet.</p>}
    </section>
  );
}

function FactRow({ fact, onReview }: {
  fact: ProfileFact;
  onReview: (fact: ProfileFact, value: string, status: ProfileFact["review_status"]) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(fact.value);
  const [saving, setSaving] = useState(false);
  async function review(status: ProfileFact["review_status"]) {
    setSaving(true);
    try { await onReview(fact, value, status); setEditing(false); } finally { setSaving(false); }
  }
  return (
    <div className={`fact-row ${fact.review_status}`}>
      {editing ? <input onChange={(event) => setValue(event.target.value)} value={value} /> : <div><strong>{fact.value}</strong><span>{Math.round(fact.confidence * 100)}% confidence · {fact.support_count} {fact.support_count === 1 ? "source" : "sources"} · {fact.review_status}</span><p>{fact.evidence}</p></div>}
      <div className="fact-actions">
        {editing ? <><button className="button compact" disabled={saving} onClick={() => { setValue(fact.value); setEditing(false); }} type="button">Cancel</button><button className="button compact primary" disabled={saving || !value.trim()} onClick={() => void review("approved")} type="button"><Check size={13} /> Save &amp; confirm</button></> : <>{fact.review_status !== "approved" ? <button className="button compact approve" disabled={saving} onClick={() => void review("approved")} type="button"><Check size={13} /> Confirm</button> : null}{fact.review_status !== "rejected" ? <button className="button compact reject" disabled={saving} onClick={() => void review("rejected")} type="button"><X size={13} /> Reject</button> : null}<button className="button compact" disabled={saving} onClick={() => setEditing(true)} type="button"><Pencil size={13} /> Edit</button></>}
      </div>
    </div>
  );
}
