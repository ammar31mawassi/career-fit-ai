-- CareerFit v8: agent workflow observability.
-- Adds the agent_runs/agent_steps foundation from the research plan.
-- Safe to run more than once.

create table if not exists public.agent_runs (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  workflow_type text not null,
  subject_type text not null default '',
  subject_id bigint,
  input_hash text not null default '',
  status text not null default 'running',
  version text not null default '',
  summary text not null default '',
  error text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.agent_steps (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  run_id bigint not null references public.agent_runs(id) on delete cascade,
  step_key text not null,
  title text not null,
  status text not null default 'running',
  attempt integer not null default 1,
  progress text not null default '',
  output_json text not null default '{}',
  error text not null default '',
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists agent_runs_user_subject_created_idx
  on public.agent_runs (user_id, workflow_type, subject_type, subject_id, created_at desc);

create index if not exists agent_runs_user_status_created_idx
  on public.agent_runs (user_id, status, created_at desc);

create index if not exists agent_steps_user_run_started_idx
  on public.agent_steps (user_id, run_id, started_at);

alter table public.agent_runs enable row level security;
alter table public.agent_steps enable row level security;

drop policy if exists agent_runs_owner_all on public.agent_runs;
create policy agent_runs_owner_all on public.agent_runs
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists agent_steps_owner_all on public.agent_steps;
create policy agent_steps_owner_all on public.agent_steps
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
