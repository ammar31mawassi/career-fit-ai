-- v24: Preserve source-health observations without violating the durable run
-- status contract introduced with the discovery beta.

alter table public.job_source_runs
  drop constraint if exists job_source_runs_status_check,
  add constraint job_source_runs_status_check
  check (status in (
    'running',
    'completed',
    'failed',
    'disabled',
    'degraded',
    'inconclusive'
  ));
