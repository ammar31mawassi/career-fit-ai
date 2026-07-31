"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Pencil, Plus, X } from "lucide-react";
import type { ProfileFact } from "@/lib/api";

const ADDABLE_FACT_TYPES = ["skill", "experience", "project", "education", "language", "location", "availability", "about_me"];
const IMPACT_ORDER = [
  "experience",
  "project",
  "education",
  "skill",
  "years_experience",
  "semesters_left",
  "work_authorization",
  "availability",
  "location",
  "language",
  "about_me",
  "domain"
];

export function ProfileFactsEditor({
  facts,
  onAdd,
  onBulkReview,
  onReview
}: {
  facts: ProfileFact[];
  onAdd: (type: string, value: string) => Promise<void>;
  onBulkReview: (facts: ProfileFact[], status: "approved" | "rejected") => Promise<void>;
  onReview: (fact: ProfileFact, value: string, status: ProfileFact["review_status"]) => Promise<void>;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkSaving, setBulkSaving] = useState(false);
  const selectAllRef = useRef<HTMLInputElement>(null);
  const factsByType = useMemo(() => {
    const grouped = new Map<string, ProfileFact[]>();
    for (const fact of facts) grouped.set(fact.fact_type, [...(grouped.get(fact.fact_type) ?? []), fact]);
    for (const [type, values] of grouped) {
      grouped.set(type, values.toSorted((left, right) => {
        const statusRank = { pending: 0, approved: 1, rejected: 2 };
        return statusRank[left.review_status] - statusRank[right.review_status]
          || right.support_count - left.support_count
          || right.confidence - left.confidence;
      }));
    }
    return grouped;
  }, [facts]);
  const visibleTypes = useMemo(() => {
    const extracted = Array.from(factsByType.keys());
    const all = [...ADDABLE_FACT_TYPES, ...extracted.filter((type) => !ADDABLE_FACT_TYPES.includes(type))];
    return all.toSorted((left, right) => {
      const leftPending = (factsByType.get(left) ?? []).some((fact) => fact.review_status === "pending");
      const rightPending = (factsByType.get(right) ?? []).some((fact) => fact.review_status === "pending");
      if (leftPending !== rightPending) return leftPending ? -1 : 1;
      return impactIndex(left) - impactIndex(right);
    });
  }, [factsByType]);
  const pendingFacts = useMemo(() => facts.filter((fact) => fact.review_status === "pending"), [facts]);
  const selectedFacts = useMemo(
    () => pendingFacts.filter((fact) => selected.has(fact.id)),
    [pendingFacts, selected]
  );

  useEffect(() => {
    const pendingIds = new Set(pendingFacts.map((fact) => fact.id));
    setSelected((current) => new Set([...current].filter((id) => pendingIds.has(id))));
  }, [pendingFacts]);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = selectedFacts.length > 0 && selectedFacts.length < pendingFacts.length;
    }
  }, [pendingFacts.length, selectedFacts.length]);

  async function bulkReview(status: "approved" | "rejected") {
    if (!selectedFacts.length) return;
    setBulkSaving(true);
    try {
      await onBulkReview(selectedFacts, status);
      setSelected(new Set());
    } catch {
      // The parent restores the optimistic state and displays the request error.
      // Keep the selection so the user can retry the same batch.
    } finally {
      setBulkSaving(false);
    }
  }

  return (
    <div className="panel facts-panel">
      <div className="section-heading facts-heading">
        <div><span className="section-kicker">Evidence map</span><h2>Review profile facts</h2><p>Confirm what is accurate. Demonstrated work still carries more weight than a simple skill listing.</p></div>
        <span className="review-count">{facts.filter((fact) => fact.review_status === "approved").length} confirmed · {pendingFacts.length} pending</span>
      </div>
      {pendingFacts.length ? (
        <div className="bulk-review-bar" aria-label="Bulk fact review">
          <label><input aria-checked={selectedFacts.length > 0 && selectedFacts.length < pendingFacts.length ? "mixed" : selectedFacts.length === pendingFacts.length} checked={selectedFacts.length === pendingFacts.length} onChange={(event) => setSelected(event.target.checked ? new Set(pendingFacts.map((fact) => fact.id)) : new Set())} ref={selectAllRef} type="checkbox" /> Select all pending</label>
          <span>{selectedFacts.length} selected</span>
          <button className="button compact approve" disabled={bulkSaving || !selectedFacts.length} onClick={() => void bulkReview("approved")} type="button"><Check size={13} /> Confirm selected</button>
          <button className="button compact reject" disabled={bulkSaving || !selectedFacts.length} onClick={() => void bulkReview("rejected")} type="button"><X size={13} /> Reject selected</button>
        </div>
      ) : <div className="review-complete"><Check size={15} /> Every extracted fact has been reviewed.</div>}
      <div className="fact-groups">
        {visibleTypes.map((type, index) => (
          <FactGroup
            addable={ADDABLE_FACT_TYPES.includes(type)}
            defaultExpanded={index === 0}
            facts={factsByType.get(type) ?? []}
            key={type}
            onAdd={onAdd}
            onReview={onReview}
            onSelectedChange={(factId, checked) => setSelected((current) => {
              const next = new Set(current);
              if (checked) next.add(factId); else next.delete(factId);
              return next;
            })}
            selected={selected}
            type={type}
          />
        ))}
      </div>
    </div>
  );
}

function FactGroup({ type, facts, addable, defaultExpanded, selected, onAdd, onReview, onSelectedChange }: {
  type: string;
  facts: ProfileFact[];
  addable: boolean;
  defaultExpanded: boolean;
  selected: Set<number>;
  onAdd: (type: string, value: string) => Promise<void>;
  onReview: (fact: ProfileFact, value: string, status: ProfileFact["review_status"]) => Promise<void>;
  onSelectedChange: (factId: number, checked: boolean) => void;
}) {
  const pendingCount = facts.filter((fact) => fact.review_status === "pending").length;
  const [expanded, setExpanded] = useState(defaultExpanded && pendingCount > 0);
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const label = type.replaceAll("_", " ");
  const groupId = `fact-group-${type.replace(/[^a-z0-9_-]/gi, "-")}`;
  const addInputId = `${groupId}-new-value`;

  useEffect(() => {
    if (defaultExpanded && pendingCount) setExpanded(true);
  }, [defaultExpanded, pendingCount]);

  async function save() {
    if (!value.trim()) return;
    setSaving(true);
    try {
      await onAdd(type, value);
      setValue("");
      setAdding(false);
      setExpanded(true);
    } catch {
      // The parent displays the error; preserve the draft for retry.
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={`fact-group ${expanded ? "expanded" : "collapsed"}`}>
      <div className="fact-group-heading">
        <button aria-controls={groupId} aria-expanded={expanded} className="fact-group-toggle" onClick={() => setExpanded((current) => !current)} type="button"><ChevronDown size={14} /><span>{label}</span><small>{facts.length} facts{pendingCount ? ` · ${pendingCount} pending` : ""}</small></button>
        {addable ? <button className="add-fact-button" onClick={() => { setAdding((current) => !current); setExpanded(true); }} type="button"><Plus size={13} /> Add</button> : null}
      </div>
      {expanded ? <div id={groupId}>
        {adding ? <div className="add-fact-form"><label className="sr-only" htmlFor={addInputId}>Add {label}</label><input autoFocus id={addInputId} onChange={(event) => setValue(event.target.value)} placeholder={`Add ${label}`} value={value} /><button className="button compact primary" disabled={saving || !value.trim()} onClick={() => void save()} type="button">Save</button><button className="button compact quiet" disabled={saving} onClick={() => { setAdding(false); setValue(""); }} type="button">Cancel</button></div> : null}
        {facts.length ? facts.map((fact) => <FactRow fact={fact} key={fact.id} onReview={onReview} onSelectedChange={onSelectedChange} selected={selected.has(fact.id)} />) : <p className="fact-empty">Nothing added yet.</p>}
      </div> : null}
    </section>
  );
}

function FactRow({ fact, selected, onReview, onSelectedChange }: {
  fact: ProfileFact;
  selected: boolean;
  onReview: (fact: ProfileFact, value: string, status: ProfileFact["review_status"]) => Promise<void>;
  onSelectedChange: (factId: number, checked: boolean) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(fact.value);
  const [saving, setSaving] = useState(false);
  const editInputId = `fact-edit-${fact.id}`;
  useEffect(() => {
    if (!editing) setValue(fact.value);
  }, [editing, fact.value]);
  async function review(status: ProfileFact["review_status"]) {
    setSaving(true);
    try {
      await onReview(fact, value, status);
      setEditing(false);
    } catch {
      // The parent displays the error; preserve the editor and its draft.
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className={`fact-row ${fact.review_status}`}>
      {fact.review_status === "pending" ? <input aria-label={`Select ${fact.value}`} checked={selected} className="fact-select" onChange={(event) => onSelectedChange(fact.id, event.target.checked)} type="checkbox" /> : <span className={`fact-state ${fact.review_status}`} aria-label={fact.review_status}>{fact.review_status === "approved" ? <Check size={13} /> : <X size={13} />}</span>}
      {editing ? <><label className="sr-only" htmlFor={editInputId}>Edit {fact.fact_type.replaceAll("_", " ")}</label><input id={editInputId} onChange={(event) => setValue(event.target.value)} value={value} /></> : <div dir="auto"><strong>{fact.value}</strong><span>{Math.round(fact.confidence * 100)}% confidence · {fact.support_count} {fact.support_count === 1 ? "source" : "sources"} · {fact.review_status}</span><p>{fact.evidence}</p></div>}
      <div className="fact-actions">
        {editing ? <><button className="button compact" disabled={saving} onClick={() => { setValue(fact.value); setEditing(false); }} type="button">Cancel</button><button className="button compact primary" disabled={saving || !value.trim()} onClick={() => void review("approved")} type="button"><Check size={13} /> Save &amp; confirm</button></> : <>{fact.review_status !== "approved" ? <button className="button compact approve" disabled={saving} onClick={() => void review("approved")} type="button"><Check size={13} /> Confirm</button> : null}{fact.review_status !== "rejected" ? <button className="button compact reject" disabled={saving} onClick={() => void review("rejected")} type="button"><X size={13} /> Reject</button> : null}<button className="button compact" disabled={saving} onClick={() => setEditing(true)} type="button"><Pencil size={13} /> Edit</button></>}
      </div>
    </div>
  );
}

function impactIndex(type: string) {
  const index = IMPACT_ORDER.indexOf(type);
  return index === -1 ? IMPACT_ORDER.length : index;
}
