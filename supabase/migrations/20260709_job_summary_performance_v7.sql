-- CareerFit v7: fast Home library summaries and match lookup.
-- Safe to run more than once.

create index if not exists idx_job_matches_user_job_summary
  on public.job_matches (user_id, job_id)
  include (
    id,
    score,
    fit_level,
    confidence,
    status,
    missing_blockers_json,
    gaps_json,
    analyzed_at
  );
