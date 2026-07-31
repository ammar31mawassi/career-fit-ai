-- Make scan submission idempotent under concurrent requests and give each
-- worker attempt an ownership token for compare-and-set heartbeats/finalizers.

begin;

alter table public.job_scans
  add column if not exists lease_token text not null default '';

create unique index job_scans_user_active_input_uq
  on public.job_scans (user_id, input_hash)
  where status in ('queued', 'running', 'cancel_requested');

create index job_scans_recovery_idx
  on public.job_scans (status, updated_at, created_at)
  where status in ('queued', 'running', 'cancel_requested');

commit;
