-- Career Fit AI Supabase schema
-- Run in the Supabase SQL editor.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists public.profiles (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  summary text not null default '',
  status text not null default 'needs_cv' check (status in ('needs_cv', 'needs_analysis', 'cv_unreadable', 'ready')),
  github_url text not null default '',
  linkedin_text text not null default '',
  manual_info text not null default '',
  years_experience numeric not null default 0,
  onboarding_completed boolean not null default false,
  last_analyzed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_user_id_unique unique (user_id)
);

create table if not exists public.profile_interests (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null references public.profiles(id) on delete cascade,
  interest text not null,
  created_at timestamptz not null default now(),
  constraint profile_interests_profile_interest_unique unique (profile_id, interest)
);

create table if not exists public.profile_sources (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null references public.profiles(id) on delete cascade,
  source_type text not null,
  title text not null default '',
  storage_path text not null default '',
  content_text text not null default '',
  metadata_json text not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.profile_facts (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null references public.profiles(id) on delete cascade,
  source_id bigint references public.profile_sources(id) on delete set null,
  fact_type text not null,
  value text not null,
  evidence text not null default '',
  metadata_json text not null default '{}',
  source_ids_json text not null default '[]',
  support_count integer not null default 1 check (support_count >= 1),
  extraction_key text not null default '',
  confidence numeric not null default 0 check (confidence >= 0 and confidence <= 1),
  user_approved boolean not null default false,
  review_status text not null default 'pending' check (review_status in ('pending', 'approved', 'rejected')),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.profile_fact_feedback (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null references public.profiles(id) on delete cascade,
  fact_id bigint references public.profile_facts(id) on delete set null,
  fact_type text not null,
  extraction_key text not null default '',
  action text not null check (action in ('pending', 'approved', 'rejected', 'edited_and_approved', 'manually_added')),
  original_value text not null default '',
  corrected_value text not null default '',
  source_ids_json text not null default '[]',
  extractor_version text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.clarification_questions (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null references public.profiles(id) on delete cascade,
  field_key text not null,
  question text not null,
  answer text not null default '',
  status text not null default 'open' check (status in ('open', 'answered')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.jobs (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  content_hash text not null,
  source_url text not null default '',
  company text not null default 'Unknown Company',
  role text not null default 'Unknown Role',
  location text not null default '',
  description_text text not null default '',
  source_title text not null default '',
  source_confidence numeric not null default 0,
  application_link text not null default '',
  requirements_json text not null default '{}',
  status text not null default 'analyzed',
  error text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint jobs_user_content_hash_unique unique (user_id, content_hash)
);

create table if not exists public.job_matches (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id bigint not null references public.jobs(id) on delete cascade,
  score numeric not null default 0 check (score >= 0 and score <= 100),
  fit_level text not null default 'Weak' check (fit_level in ('Strong', 'Medium', 'Weak')),
  confidence numeric not null default 0 check (confidence >= 0 and confidence <= 1),
  status text not null default 'Lead' check (status in ('Lead', 'Applied', 'Interview', 'Rejected', 'Withdrawn', 'Offer')),
  matched_evidence_json text not null default '[]',
  missing_blockers_json text not null default '[]',
  gaps_json text not null default '[]',
  model_version text not null default 'fit-v1.0.0',
  ontology_version text not null default 'skills-v1.0.0',
  component_scores_json text not null default '{}',
  applied_caps_json text not null default '[]',
  feature_snapshot_json text not null default '{}',
  analyzed_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint job_matches_user_job_unique unique (user_id, job_id)
);

create table if not exists public.resume_advice (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  match_id bigint not null references public.job_matches(id) on delete cascade,
  projects_json text not null default '[]',
  skill_order_json text not null default '[]',
  about_text text not null default '',
  template_id text not null default '',
  evidence_json text not null default '[]',
  generated_at timestamptz not null default now(),
  constraint resume_advice_user_match_unique unique (user_id, match_id)
);

create table if not exists public.job_status_events (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  match_id bigint not null references public.job_matches(id) on delete cascade,
  status text not null check (status in ('Lead', 'Applied', 'Interview', 'Rejected', 'Withdrawn', 'Offer')),
  created_at timestamptz not null default now()
);

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

create table if not exists private.rate_limit_buckets (
  bucket_key text primary key,
  request_count integer not null default 0 check (request_count >= 0),
  reset_at timestamptz not null,
  updated_at timestamptz not null default now()
);

create index if not exists profile_sources_user_profile_idx on public.profile_sources (user_id, profile_id);
create index if not exists profiles_user_onboarding_idx on public.profiles (user_id, onboarding_completed);
create index if not exists profile_interests_user_interest_idx on public.profile_interests (user_id, interest);
create index if not exists profile_facts_user_profile_type_idx on public.profile_facts (user_id, profile_id, fact_type);
create index if not exists profile_facts_user_profile_review_idx on public.profile_facts (user_id, profile_id, review_status);
create index if not exists profile_facts_profile_extraction_key_idx on public.profile_facts (profile_id, extraction_key);
create index if not exists profile_fact_feedback_user_created_idx on public.profile_fact_feedback (user_id, created_at desc);
create index if not exists profile_fact_feedback_profile_key_idx on public.profile_fact_feedback (profile_id, extraction_key);
create index if not exists clarification_questions_user_profile_status_idx on public.clarification_questions (user_id, profile_id, status);
create index if not exists jobs_user_updated_idx on public.jobs (user_id, updated_at desc);
create index if not exists jobs_user_company_role_idx on public.jobs (user_id, company, role);
create index if not exists job_matches_user_job_idx on public.job_matches (user_id, job_id);
create index if not exists job_matches_user_status_idx on public.job_matches (user_id, status, updated_at desc);
create index if not exists resume_advice_user_match_idx on public.resume_advice (user_id, match_id);
create index if not exists job_status_events_user_match_created_idx on public.job_status_events (user_id, match_id, created_at);
create index if not exists agent_runs_user_subject_created_idx on public.agent_runs (user_id, workflow_type, subject_type, subject_id, created_at desc);
create index if not exists agent_runs_user_status_created_idx on public.agent_runs (user_id, status, created_at desc);
create index if not exists agent_steps_user_run_started_idx on public.agent_steps (user_id, run_id, started_at);
create index if not exists rate_limit_buckets_reset_idx on private.rate_limit_buckets (reset_at);
create index if not exists agent_steps_run_idx on public.agent_steps (run_id);
create index if not exists clarification_questions_profile_idx on public.clarification_questions (profile_id);
create index if not exists job_matches_job_idx on public.job_matches (job_id);
create index if not exists job_status_events_match_idx on public.job_status_events (match_id);
create index if not exists profile_fact_feedback_fact_idx on public.profile_fact_feedback (fact_id);
create index if not exists profile_facts_source_idx on public.profile_facts (source_id);
create index if not exists profile_sources_profile_idx on public.profile_sources (profile_id);
create index if not exists resume_advice_match_idx on public.resume_advice (match_id);

alter table public.profiles enable row level security;
alter table public.profile_interests enable row level security;
alter table public.profile_sources enable row level security;
alter table public.profile_facts enable row level security;
alter table public.profile_fact_feedback enable row level security;
alter table public.clarification_questions enable row level security;
alter table public.jobs enable row level security;
alter table public.job_matches enable row level security;
alter table public.resume_advice enable row level security;
alter table public.job_status_events enable row level security;
alter table public.agent_runs enable row level security;
alter table public.agent_steps enable row level security;
alter table private.rate_limit_buckets enable row level security;

revoke all on table private.rate_limit_buckets from public, anon, authenticated;

create or replace function public.consume_rate_limit(
  p_bucket_key text,
  p_limit integer,
  p_window_seconds integer
)
returns table (allowed boolean, remaining integer, retry_after integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_count integer;
  v_reset_at timestamptz;
  v_now timestamptz := clock_timestamp();
begin
  if p_bucket_key is null or length(p_bucket_key) < 8 or p_limit < 1 or p_window_seconds < 1 then
    raise exception 'invalid rate-limit arguments';
  end if;

  insert into private.rate_limit_buckets (bucket_key, request_count, reset_at, updated_at)
  values (p_bucket_key, 1, v_now + make_interval(secs => p_window_seconds), v_now)
  on conflict (bucket_key) do update
  set request_count = case
        when private.rate_limit_buckets.reset_at <= v_now then 1
        else private.rate_limit_buckets.request_count + 1
      end,
      reset_at = case
        when private.rate_limit_buckets.reset_at <= v_now
          then v_now + make_interval(secs => p_window_seconds)
        else private.rate_limit_buckets.reset_at
      end,
      updated_at = v_now
  returning request_count, reset_at into v_count, v_reset_at;

  allowed := v_count <= p_limit;
  remaining := greatest(0, p_limit - v_count);
  retry_after := case when allowed then 0 else greatest(1, ceil(extract(epoch from (v_reset_at - v_now)))::integer) end;
  return next;
end;
$$;

revoke execute on function public.consume_rate_limit(text, integer, integer) from public, anon, authenticated;
grant execute on function public.consume_rate_limit(text, integer, integer) to service_role;

create policy profiles_owner_all on public.profiles
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy profile_interests_owner_all on public.profile_interests
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy profile_sources_owner_all on public.profile_sources
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy profile_facts_owner_all on public.profile_facts
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy profile_fact_feedback_owner_select on public.profile_fact_feedback
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy profile_fact_feedback_owner_insert on public.profile_fact_feedback
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy clarification_questions_owner_all on public.clarification_questions
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy jobs_owner_all on public.jobs
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy job_matches_owner_all on public.job_matches
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy resume_advice_owner_all on public.resume_advice
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy job_status_events_owner_all on public.job_status_events
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy agent_runs_owner_all on public.agent_runs
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy agent_steps_owner_all on public.agent_steps
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

-- Storage policy for private profile documents.
-- Create the bucket in Storage as private before running this section if needed.
insert into storage.buckets (id, name, public)
values ('profile-documents', 'profile-documents', false)
on conflict (id) do nothing;

create policy profile_documents_owner_select on storage.objects
  for select to authenticated
  using (
    bucket_id = 'profile-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy profile_documents_owner_insert on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'profile-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy profile_documents_owner_update on storage.objects
  for update to authenticated
  using (
    bucket_id = 'profile-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  )
  with check (
    bucket_id = 'profile-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy profile_documents_owner_delete on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'profile-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
