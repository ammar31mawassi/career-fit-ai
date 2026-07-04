-- Upgrade an existing Career Fit AI database to deterministic fit model v2.

alter table public.profile_facts
  add column if not exists metadata_json text not null default '{}';

alter table public.job_matches
  add column if not exists model_version text not null default 'fit-v1.0.0',
  add column if not exists ontology_version text not null default 'skills-v1.0.0',
  add column if not exists component_scores_json text not null default '{}',
  add column if not exists applied_caps_json text not null default '[]',
  add column if not exists feature_snapshot_json text not null default '{}';

alter table public.job_matches drop constraint if exists job_matches_status_check;
alter table public.job_matches
  add constraint job_matches_status_check
  check (status in ('Lead', 'Applied', 'Interview', 'Rejected', 'Withdrawn', 'Offer'));

alter table public.resume_advice
  add column if not exists template_id text not null default '',
  add column if not exists evidence_json text not null default '[]';

create table if not exists public.job_status_events (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  match_id bigint not null references public.job_matches(id) on delete cascade,
  status text not null check (status in ('Lead', 'Applied', 'Interview', 'Rejected', 'Withdrawn', 'Offer')),
  created_at timestamptz not null default now()
);

create index if not exists job_status_events_user_match_created_idx
  on public.job_status_events (user_id, match_id, created_at);

alter table public.job_status_events enable row level security;

drop policy if exists job_status_events_owner_all on public.job_status_events;
create policy job_status_events_owner_all on public.job_status_events
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
