-- CareerFit v6: indexes for the authenticated library's actual access patterns.
-- Safe to run more than once.

create index if not exists idx_jobs_user_updated
  on public.jobs (user_id, updated_at desc);

create index if not exists idx_job_status_events_user_match_created
  on public.job_status_events (user_id, match_id, created_at);
