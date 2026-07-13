-- Cover foreign keys introduced by product intelligence v14 so account deletion,
-- ownership filtering, and job cleanup do not require full table scans.

create index if not exists job_requirement_revisions_user_idx
  on public.job_requirement_revisions (user_id);
create index if not exists job_scans_result_job_idx
  on public.job_scans (result_job_id) where result_job_id is not null;
create index if not exists extraction_metrics_user_idx
  on public.extraction_metrics (user_id);
create index if not exists evaluation_examples_user_idx
  on public.evaluation_examples (user_id);
