"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { FileText, RefreshCw, Search, Sparkles } from "lucide-react";
import { useAppData } from "@/components/AppDataProvider";
import { JobLibrarySkeleton } from "@/components/home/JobLibrarySkeleton";
import { JobScanner } from "@/components/home/JobScanner";
import { JobSummaryCard } from "@/components/home/JobSummaryCard";
import { OpportunityInspector } from "@/components/home/OpportunityInspector";
import {
  createJob,
  getJob,
  getJobSummaries,
  kickRecommendationWorker,
  toJobSummary,
  type JobCreate,
  type TrackedJob,
  type TrackedJobSummary
} from "@/lib/api";

const emptyJob: JobCreate = { source_url: "", company: "", role: "", description_text: "" };

export function HomeClient() {
  const { profile, jobs, profileLoading, jobsLoading, dataError, setJobs, refreshAll } = useAppData();
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(emptyJob);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [scanStartedAt, setScanStartedAt] = useState(0);
  const [failedScan, setFailedScan] = useState<JobCreate | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [jobDetailsById, setJobDetailsById] = useState<Record<number, TrackedJob>>({});
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [searchResults, setSearchResults] = useState<TrackedJobSummary[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const pendingDetailIds = useRef(new Set<number>());
  const scanAbort = useRef<AbortController | null>(null);

  const profileReady = profile ? profile.status === "ready" : true;
  const profileConfirmedIncomplete = !profileLoading && profile !== null && profile.status !== "ready";
  const deferredQuery = useDeferredValue(query);
  const searchableJobs = useMemo(
    () => jobs.map((job) => ({
      job,
      searchText: [job.company, job.role, job.location, job.source_url, job.requirement_summary, job.primary_signal, ...job.top_skills].join(" ").toLowerCase()
    })),
    [jobs]
  );
  const visibleJobs = useMemo(() => {
    const normalized = deferredQuery.trim().toLowerCase();
    if (searchResults) return searchResults;
    if (!normalized) return jobs;
    return searchableJobs.filter(({ searchText }) => searchText.includes(normalized)).map(({ job }) => job);
  }, [deferredQuery, jobs, searchableJobs, searchResults]);
  const selectedSummary = selectedJobId ? visibleJobs.find((job) => job.id === selectedJobId) ?? null : null;
  const selectedJob = selectedJobId ? jobDetailsById[selectedJobId] ?? null : null;
  const stats = useMemo(() => ({
    scanned: jobs.length,
    applied: jobs.filter((job) => job.match && !["Lead", "Withdrawn"].includes(job.match.status)).length,
    strong: jobs.filter((job) => job.match?.fit_level === "Strong").length
  }), [jobs]);

  useEffect(() => {
    const normalized = deferredQuery.trim();
    if (normalized.length < 2) {
      setSearchResults(null);
      setSearchLoading(false);
      setSearchError("");
      return;
    }
    let cancelled = false;
    setSearchLoading(true);
    setSearchError("");
    const timer = window.setTimeout(() => {
      void getJobSummaries(normalized)
        .then((results) => { if (!cancelled) setSearchResults(results); })
        .catch((caught) => {
          if (!cancelled) {
            setSearchResults(null);
            setSearchError(caught instanceof Error ? caught.message : "Could not search saved jobs.");
          }
        })
        .finally(() => { if (!cancelled) setSearchLoading(false); });
    }, 260);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [deferredQuery]);

  const fetchJobDetail = useCallback(async (jobId: number, showLoading = false) => {
    if (jobDetailsById[jobId] || pendingDetailIds.current.has(jobId)) return;
    pendingDetailIds.current.add(jobId);
    if (showLoading) { setDetailsLoading(true); setDetailError(""); }
    try {
      const job = await getJob(jobId);
      setJobDetailsById((current) => ({ ...current, [job.id]: job }));
    } catch (caught) {
      if (showLoading) setDetailError(caught instanceof Error ? caught.message : "Could not load job details.");
    } finally {
      pendingDetailIds.current.delete(jobId);
      if (showLoading) setDetailsLoading(false);
    }
  }, [jobDetailsById]);

  useEffect(() => {
    if (!visibleJobs.length) { setSelectedJobId(null); return; }
    if (!selectedJobId || !visibleJobs.some((job) => job.id === selectedJobId)) setSelectedJobId(visibleJobs[0].id);
  }, [selectedJobId, visibleJobs]);

  useEffect(() => {
    if (!selectedJobId || jobDetailsById[selectedJobId]) { setDetailsLoading(false); setDetailError(""); return; }
    void fetchJobDetail(selectedJobId, true);
  }, [fetchJobDetail, jobDetailsById, selectedJobId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runScan(form);
  }

  async function runScan(payload: JobCreate) {
    const controller = new AbortController();
    scanAbort.current?.abort();
    scanAbort.current = controller;
    setSubmitting(true);
    setScanStartedAt(Date.now());
    setError("");
    setMessage("");
    setFailedScan(null);
    try {
      const job = await createJob(payload, controller.signal);
      const summary = toJobSummary(job);
      setMessage(job.status === "failed" ? job.error : `${job.company} — ${job.role} analyzed and saved.`);
      setJobs((current) => [summary, ...current.filter((item) => item.id !== job.id)]);
      setSearchResults((current) => current ? [summary, ...current.filter((item) => item.id !== job.id)] : current);
      setJobDetailsById((current) => ({ ...current, [job.id]: job }));
      setSelectedJobId(job.id);
      if (job.status === "analyzed") void kickRecommendationWorker().catch(() => undefined);
      setForm(emptyJob);
      setQuery("");
    } catch (caught) {
      if (controller.signal.aborted) {
        setMessage("Stopped waiting. The server may still finish this scan; use Refresh in a moment before retrying.");
      } else {
        setFailedScan(payload);
        setError(caught instanceof Error ? caught.message : "Could not analyze this job.");
      }
    } finally {
      if (scanAbort.current === controller) scanAbort.current = null;
      setSubmitting(false);
      setScanStartedAt(0);
    }
  }

  function updateCachedJob(updated: TrackedJob) {
    const summary = toJobSummary(updated);
    setJobs((current) => current.map((job) => job.id === updated.id ? summary : job));
    setSearchResults((current) => current?.map((job) => job.id === updated.id ? summary : job) ?? current);
    setJobDetailsById((current) => ({ ...current, [updated.id]: updated }));
  }

  return (
    <>
      <header className="page-heading home-hero">
        <div><span className="eyebrow"><Sparkles size={14} /> Career signal radar</span><h1>Scan the role.<br /><em>Trust the evidence.</em></h1><p>CareerFit reads an opportunity, compares it to your verified profile, and shows the exact resume changes that improve your fit.</p></div>
        <button className="button quiet" onClick={() => void refreshAll()} type="button"><RefreshCw size={16} /> Refresh</button>
      </header>
      {error || dataError || searchError ? <div className="notice error action-notice"><span>{error || dataError || searchError}</span>{failedScan ? <button className="button compact" onClick={() => void runScan(failedScan)} type="button">Retry safely</button> : null}</div> : null}
      {message ? <div className="notice success">{message}</div> : null}
      {profileConfirmedIncomplete ? <section className="panel warning-panel"><FileText size={22} aria-hidden /><div><h2>Profile is not ready</h2><p>Upload one CV and run profile analysis before job matching. GitHub and LinkedIn are optional.</p></div><a className="button primary" href="/profile">Complete profile</a></section> : null}

      <JobScanner form={form} onCancel={() => scanAbort.current?.abort()} onSubmit={submit} profileReady={profileReady} scanStartedAt={scanStartedAt} setForm={setForm} submitting={submitting} />

      <section className="stats signal-stats" aria-label="Job search overview">
        <div><span>Opportunities mapped</span><strong>{stats.scanned}</strong><small>Cached summaries for quick switching</small></div>
        <div><span>Strong signals</span><strong>{stats.strong}</strong><small>Roles worth prioritizing</small></div>
        <div><span>In motion</span><strong>{stats.applied}</strong><small>Applications beyond lead stage</small></div>
      </section>

      <section className="opportunity-workbench">
        <div className="panel flush opportunity-library">
          <div className="list-header">
            <div><span className="section-kicker">Opportunity radar</span><h2>Your saved roles</h2><p>Search summaries instantly; longer searches query your saved database so old roles are still findable.</p></div>
            <form className="search-box" onSubmit={(event) => event.preventDefault()}><Search size={16} aria-hidden /><input onChange={(event) => setQuery(event.target.value)} placeholder="Search company, role, skill..." value={query} />{searchLoading ? <span className="search-spinner" aria-label="Searching saved jobs" /> : null}</form>
          </div>
          {jobsLoading && !jobs.length ? <JobLibrarySkeleton /> : visibleJobs.length ? (
            <div className="job-list compact-list">{visibleJobs.map((job) => <JobSummaryCard active={job.id === selectedJobId} job={job} key={job.id} onPreview={() => void fetchJobDetail(job.id)} onSelect={() => setSelectedJobId(job.id)} />)}</div>
          ) : <div className="empty">{jobs.length ? "No roles match that search." : "Your first opportunity will appear here."}</div>}
        </div>
        <OpportunityInspector detailError={detailError} job={selectedJob} loading={detailsLoading} onStatusChanged={updateCachedJob} summary={selectedSummary} />
      </section>
    </>
  );
}
