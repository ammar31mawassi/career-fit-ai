-- v23: Preserve immutable application-stage context and distinguish the
-- observed business time from the database audit time.

alter table public.job_status_events
  add column if not exists previous_status text not null default '',
  add column if not exists occurred_at timestamptz,
  add column if not exists source text not null default 'legacy',
  add column if not exists note text not null default '';

with ordered as (
  select
    id,
    coalesce(
      lag(status) over (partition by user_id, match_id order by id),
      ''
    ) as previous_status
  from public.job_status_events
)
update public.job_status_events as event
set
  previous_status = ordered.previous_status,
  occurred_at = coalesce(event.occurred_at, event.created_at),
  source = case when event.source = '' then 'legacy' else event.source end
from ordered
where event.id = ordered.id;

alter table public.job_status_events
  alter column occurred_at set default now(),
  alter column occurred_at set not null,
  alter column source set default 'system',
  add constraint job_status_events_previous_status_check
    check (previous_status in ('', 'Lead', 'Applied', 'Interview', 'Rejected', 'Withdrawn', 'Offer')),
  add constraint job_status_events_source_check
    check (source in ('system', 'user', 'correction', 'backfill', 'legacy')),
  add constraint job_status_events_note_length_check
    check (char_length(note) <= 500);

drop index if exists public.job_status_events_user_match_created_idx;
drop index if exists public.idx_job_status_events_user_match_created;
drop index if exists public.job_status_events_user_match_occurred_idx;
drop index if exists public.job_status_events_user_match_audit_idx;
create index job_status_events_user_match_occurred_idx
  on public.job_status_events (user_id, match_id, occurred_at, created_at, id);
create index job_status_events_user_match_audit_idx
  on public.job_status_events (user_id, match_id, id);
