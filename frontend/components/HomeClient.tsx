"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { FileText, RefreshCw, Search, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAppData } from "@/components/AppDataProvider";
import { JobLibrarySkeleton } from "@/components/home/JobLibrarySkeleton";
import { JobScanner } from "@/components/home/JobScanner";
import { JobSummaryCard } from "@/components/home/JobSummaryCard";
import { OpportunityInspector } from "@/components/home/OpportunityInspector";
import { createKeyedRequestPool, summaryInvalidatesDetail } from "@/lib/ui-concurrency.mjs";
import {
  cancelJobScan,
  createJobScan,
  getActiveJobScan,
  getJob,
  getJobScan,
  getJobSummaries,
  processJobScan,
  toJobSummary,
  type JobCreate,
  type JobScan,
  type TrackedJob,
  type TrackedJobSummary
} from "@/lib/api";

const emptyJob: JobCreate = {
  source_url: "",
  company: "",
  role: "",
  description_text: "",
  contribute_public_posting: false
};

type DetailLoadState = {
  loading: boolean;
  error: string;
};

function updatedAtMillis(value: string) {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

export function HomeClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    profile,
    jobs,
    profileLoading,
    jobsLoading,
    jobsNextCursor,
    dataError,
    setJobs,
    refreshAll,
    loadMoreJobs,
    reportDataError
  } = useAppData();
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(emptyJob);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [scanStartedAt, setScanStartedAt] = useState(0);
  const [scan, setScan] = useState<JobScan | null>(null);
  const [failedScan, setFailedScan] = useState<JobCreate | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [jobDetailsById, setJobDetailsById] = useState<Record<number, TrackedJob>>({});
  const [detailStateById, setDetailStateById] = useState<Record<number, DetailLoadState>>({});
  const [searchResults, setSearchResults] = useState<TrackedJobSummary[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const inspectorRef = useRef<HTMLDivElement>(null);
  const jobDetailsRef = useRef<Record<number, TrackedJob>>({});
  const activeScanId = useRef<number | null>(null);
  const activeScanResumeChecked = useRef(false);
  const detailRequestPool = useRef(
    createKeyedRequestPool(async (jobId: number): Promise<TrackedJob> => {
      const job = await getJob(jobId);
      const summary = toJobSummary(job);
      jobDetailsRef.current[job.id] = job;
      setJobDetailsById((current) => ({ ...current, [job.id]: job }));
      setJobs((current) => current.some((item) => item.id === job.id)
        ? current.map((item) => (
            item.id === job.id && updatedAtMillis(summary.updated_at) >= updatedAtMillis(item.updated_at)
              ? summary
              : item
          ))
        : [summary, ...current]);
      setSearchResults((current) => current?.map((item) => (
        item.id === job.id && updatedAtMillis(summary.updated_at) >= updatedAtMillis(item.updated_at)
          ? summary
          : item
      )) ?? current);
      return job;
    })
  ).current;

  const profileReady = Boolean(profile && profile.status === "ready");
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
  const selectedJob = selectedJobId ? jobDetailsById[selectedJobId] ?? null : null;
  const selectedSummary = selectedJobId
    ? visibleJobs.find((job) => job.id === selectedJobId) ?? (selectedJob ? toJobSummary(selectedJob) : null)
    : null;
  const selectedDetailState = selectedJobId ? detailStateById[selectedJobId] : undefined;
  const detailsLoading = Boolean(selectedJobId && !selectedJob && selectedDetailState?.loading);
  const detailError = selectedJobId && !selectedJob ? selectedDetailState?.error ?? "" : "";
  const stats = useMemo(() => ({
    scanned: jobs.length,
    applied: jobs.filter((job) => job.match && ["Applied", "Interview", "Offer"].includes(job.match.status)).length,
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
    const controller = new AbortController();
    let cancelled = false;
    setSearchLoading(true);
    setSearchError("");
    setSearchResults(null);
    const timer = window.setTimeout(() => {
      void getJobSummaries(normalized, controller.signal)
        .then((results) => { if (!cancelled) setSearchResults(results); })
        .catch((caught) => {
          if (!cancelled && !controller.signal.aborted) {
            setSearchResults(null);
            setSearchError(caught instanceof Error ? caught.message : "Could not search saved jobs.");
          }
        })
        .finally(() => { if (!cancelled) setSearchLoading(false); });
    }, 260);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [deferredQuery]);

  useEffect(() => {
    const newestSummaryById = new Map<number, TrackedJobSummary>();
    for (const summary of [...jobs, ...(searchResults ?? [])]) {
      const current = newestSummaryById.get(summary.id);
      if (!current || updatedAtMillis(summary.updated_at) > updatedAtMillis(current.updated_at)) {
        newestSummaryById.set(summary.id, summary);
      }
    }
    const staleIds = Object.values(jobDetailsById)
      .filter((job) => summaryInvalidatesDetail(job, newestSummaryById.get(job.id)))
      .map((job) => job.id);
    if (!staleIds.length) return;
    for (const jobId of staleIds) delete jobDetailsRef.current[jobId];
    setJobDetailsById((current) => {
      const next = { ...current };
      for (const jobId of staleIds) delete next[jobId];
      return next;
    });
  }, [jobDetailsById, jobs, searchResults]);

  const fetchJobDetail = useCallback((jobId: number): Promise<TrackedJob> => {
    const cached = jobDetailsRef.current[jobId];
    if (cached) return Promise.resolve(cached);
    return detailRequestPool.load(jobId);
  }, [detailRequestPool]);

  const loadInspectorDetail = useCallback(async (jobId: number) => {
    setDetailStateById((current) => ({
      ...current,
      [jobId]: { loading: true, error: "" }
    }));
    try {
      await fetchJobDetail(jobId);
      setDetailStateById((current) => ({
        ...current,
        [jobId]: { loading: false, error: "" }
      }));
    } catch (caught) {
      setDetailStateById((current) => ({
        ...current,
        [jobId]: {
          loading: false,
          error: caught instanceof Error ? caught.message : "Could not load job details."
        }
      }));
    }
  }, [fetchJobDetail]);

  useEffect(() => {
    const requested = Number(searchParams.get("job"));
    if (Number.isSafeInteger(requested) && requested > 0 && requested !== selectedJobId) {
      setSelectedJobId(requested);
    }
  }, [searchParams, selectedJobId]);

  useEffect(() => {
    const requested = Number(searchParams.get("job"));
    if (!visibleJobs.length) {
      if (!Number.isSafeInteger(requested) || requested <= 0) setSelectedJobId(null);
      return;
    }
    if (Number.isSafeInteger(requested) && requested > 0) return;
    if (!selectedJobId || !visibleJobs.some((job) => job.id === selectedJobId)) setSelectedJobId(visibleJobs[0].id);
  }, [searchParams, selectedJobId, visibleJobs]);

  useEffect(() => {
    if (!selectedJobId) return;
    if (selectedJob) {
      setDetailStateById((current) => {
        const state = current[selectedJobId];
        if (!state?.loading && !state?.error) return current;
        return { ...current, [selectedJobId]: { loading: false, error: "" } };
      });
      return;
    }
    void loadInspectorDetail(selectedJobId);
  }, [loadInspectorDetail, selectedJob, selectedJobId]);

  useEffect(() => {
    if (profileLoading || !profileReady || activeScanResumeChecked.current) return;
    activeScanResumeChecked.current = true;
    let disposed = false;
    void getActiveJobScan()
      .then((active) => {
        if (disposed || !active) return;
        activeScanId.current = active.id;
        setScan(active);
        setSubmitting(true);
        const createdAt = Date.parse(active.created_at);
        setScanStartedAt(Number.isNaN(createdAt) ? Date.now() : createdAt);
        if (active.status === "queued") {
          void processJobScan(active.id).catch(() => undefined);
        }
        void monitorScan(active, null).finally(() => {
          if (disposed) return;
          if (activeScanId.current === active.id) activeScanId.current = null;
          setSubmitting(false);
          setScanStartedAt(0);
        });
      })
      .catch((caught) => {
        if (!disposed) {
          setError(caught instanceof Error ? caught.message : "Could not check for an active saved scan.");
        }
      });
    return () => {
      disposed = true;
      activeScanId.current = null;
      activeScanResumeChecked.current = false;
    };
  }, [profileLoading, profileReady]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runScan(form);
  }

  async function runScan(payload: JobCreate) {
    setSubmitting(true);
    setScanStartedAt(Date.now());
    setError("");
    setMessage("");
    setFailedScan(null);
    try {
      const queued = await createJobScan(payload);
      activeScanId.current = queued.id;
      setScan(queued);
      void processJobScan(queued.id).catch(() => undefined);
      await monitorScan(queued, payload);
    } catch (caught) {
      setFailedScan(payload);
      setError(caught instanceof Error ? caught.message : "Could not queue this job scan.");
    } finally {
      activeScanId.current = null;
      setSubmitting(false);
      setScanStartedAt(0);
    }
  }

  async function monitorScan(initial: JobScan, retryPayload: JobCreate | null) {
      let current = initial;
      let consecutiveReadFailures = 0;
      let delayMs = 1000;
      const deadline = Date.now() + 6 * 60 * 1000;
      while (
        activeScanId.current === initial.id
        && !["succeeded", "failed", "cancelled"].includes(current.status)
        && Date.now() < deadline
      ) {
        const visibilityDelay = typeof document !== "undefined" && document.hidden ? 10_000 : delayMs;
        await new Promise((resolve) => window.setTimeout(resolve, visibilityDelay));
        if (activeScanId.current !== initial.id) return;
        try {
          current = await getJobScan(initial.id);
          consecutiveReadFailures = 0;
          delayMs = Math.min(8000, Math.round(delayMs * 1.45));
          setError("");
          setScan(current);
        } catch {
          consecutiveReadFailures += 1;
          delayMs = Math.min(10_000, Math.round(delayMs * 1.7));
          setError("Connection interrupted while checking this saved scan. CareerFit is resuming automatically.");
          if (consecutiveReadFailures >= 8) {
            setMessage("The scan is still saved on the server. Reload this page later to resume its status.");
            return;
          }
        }
      }
      if (activeScanId.current !== initial.id) return;
      if (current.status === "cancelled") {
        setMessage("Scan cancelled. Its saved input can be submitted again when you are ready.");
        return;
      }
      if (current.status !== "succeeded" || !current.result_job) {
        if (["queued", "running", "cancel_requested"].includes(current.status)) {
          setMessage("The scan is still saved and processing in the background. Reload this page later to resume its status.");
          return;
        }
        setFailedScan(retryPayload);
        setError(current.error_message || `The durable scan failed${current.error_code ? ` (${current.error_code})` : ""}.`);
        return;
      }
      const job = current.result_job;
      const summary = toJobSummary(job);
      if (job.status === "failed") {
        setError(job.error || "The role was saved, but analysis did not finish.");
      } else {
        setMessage(`${job.company} — ${job.role} analyzed and saved.`);
      }
      setJobs((current) => [summary, ...current.filter((item) => item.id !== job.id)]);
      setSearchResults((current) => current ? [summary, ...current.filter((item) => item.id !== job.id)] : current);
      jobDetailsRef.current[job.id] = job;
      setJobDetailsById((current) => ({ ...current, [job.id]: job }));
      selectJob(job.id);
      setForm(emptyJob);
      setQuery("");
  }

  async function cancelActiveScan() {
    const scanId = activeScanId.current;
    if (!scanId) return;
    activeScanId.current = null;
    try {
      const cancelled = await cancelJobScan(scanId);
      setScan(cancelled);
      setMessage(cancelled.status === "cancelled" ? "Scan cancelled." : "Cancellation requested. The current safe step will finish first.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not cancel the scan.");
    } finally {
      setSubmitting(false);
    }
  }

  function selectJob(jobId: number) {
    setSelectedJobId(jobId);
    const parameters = new URLSearchParams(searchParams.toString());
    parameters.set("job", String(jobId));
    router.replace(`/?${parameters.toString()}`, { scroll: false });
    if (window.matchMedia("(max-width: 760px)").matches) {
      window.setTimeout(() => {
        inspectorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        inspectorRef.current?.focus({ preventScroll: true });
      }, 0);
    }
  }

  function updateCachedJob(updated: TrackedJob) {
    const summary = toJobSummary(updated);
    setJobs((current) => current.map((job) => job.id === updated.id ? summary : job));
    setSearchResults((current) => current?.map((job) => job.id === updated.id ? summary : job) ?? current);
    jobDetailsRef.current[updated.id] = updated;
    setJobDetailsById((current) => ({ ...current, [updated.id]: updated }));
  }

  return (
    <>
      <section className="workbench-intro">
        <header className="page-heading home-hero">
          <div>
            <span className="eyebrow"><Sparkles size={14} /> Your career signal, clarified</span>
            <h1>Know why a role fits.<br /><em>Know what to improve.</em></h1>
            <p>Paste a job URL, compare it against your verified profile, and focus on the roles that are the best fit.</p>
          </div>
          <button aria-label="Refresh workspace" className="button quiet hero-refresh" onClick={() => { void refreshAll().catch(() => undefined); }} title="Refresh workspace" type="button"><RefreshCw size={16} /> Refresh</button>
        </header>

        <JobScanner
          form={form}
          onCancel={() => void cancelActiveScan()}
          onSubmit={submit}
          profileReady={profileReady}
          scanProgress={scan ? { status: scan.status, currentStep: scan.current_step, progress: scan.progress, traceId: scan.trace_id } : null}
          scanStartedAt={scanStartedAt}
          setForm={setForm}
          submitting={submitting}
        />
      </section>
      {error || dataError || searchError ? <div className="notice error action-notice"><span>{error || dataError || searchError}</span>{failedScan ? <button className="button compact" onClick={() => void runScan(failedScan)} type="button">Retry safely</button> : null}</div> : null}
      {message ? <div className="notice success">{message}</div> : null}
      {profileConfirmedIncomplete ? <section className="panel warning-panel"><FileText size={22} aria-hidden /><div><h2>Profile is not ready</h2><p>Upload one CV and run profile analysis before job matching. GitHub and LinkedIn are optional.</p></div><a className="button primary" href="/profile">Complete profile</a></section> : null}

      <section className="opportunity-workbench">
        <div className="panel flush opportunity-library">
          <div className="list-header">
            <div><h2>Saved opportunities</h2><p>{jobs.length} roles · {stats.strong} strong signals</p></div>
            <form className="search-box" onSubmit={(event) => event.preventDefault()}><Search size={15} aria-hidden /><input aria-label="Search saved opportunities" onChange={(event) => setQuery(event.target.value)} placeholder="Search roles" value={query} />{searchLoading ? <span className="search-spinner" aria-label="Searching saved jobs" /> : null}</form>
          </div>
          {jobsLoading && !jobs.length ? <JobLibrarySkeleton /> : visibleJobs.length ? (
            <div className="job-list compact-list">{visibleJobs.map((job) => <JobSummaryCard active={job.id === selectedJobId} job={job} key={job.id} onPreview={() => { void fetchJobDetail(job.id).catch(() => undefined); }} onSelect={() => selectJob(job.id)} />)}</div>
          ) : <div className="empty">{jobs.length ? "No roles match that search." : "Your first opportunity will appear here."}</div>}
          {jobsNextCursor && !query.trim() ? <div className="load-more-row"><button className="button quiet" disabled={jobsLoading} onClick={() => {
            void loadMoreJobs().catch((caught) => {
              reportDataError(caught instanceof Error ? caught.message : "Could not load more saved jobs.");
            });
          }} type="button">{jobsLoading ? "Loading…" : "Load more roles"}</button></div> : null}
        </div>
        <div id="opportunity-inspector" ref={inspectorRef} tabIndex={-1}>
          <OpportunityInspector detailError={detailError} job={selectedJob} loading={detailsLoading} onJobChanged={updateCachedJob} onRetry={selectedJobId ? () => { void loadInspectorDetail(selectedJobId); } : undefined} profileUpdatedAt={profile?.updated_at ?? null} summary={selectedSummary} />
        </div>
      </section>

      <section className="stats signal-stats" aria-label="Job search overview">
        <div><span>Loaded opportunities</span><strong>{stats.scanned}</strong><small>Roles loaded in this workspace view</small></div>
        <div><span>Loaded strong signals</span><strong>{stats.strong}</strong><small>Strong matches in the loaded roles</small></div>
        <div><span>In motion</span><strong>{stats.applied}</strong><small>Applications beyond lead stage</small></div>
      </section>
    </>
  );
}
