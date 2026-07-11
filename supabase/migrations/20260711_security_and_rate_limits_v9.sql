-- CareerFit v9: close known schema/security gaps and make public-beta limits durable.

alter table public.profiles
  drop constraint if exists profiles_status_check;

alter table public.profiles
  add constraint profiles_status_check
  check (status in ('needs_cv', 'needs_analysis', 'cv_unreadable', 'ready'));

-- Keep server-side rate-limit state unreachable through the Data API.
create table if not exists public.rate_limit_buckets (
  bucket_key text primary key,
  request_count integer not null default 0 check (request_count >= 0),
  reset_at timestamptz not null,
  updated_at timestamptz not null default now()
);

create index if not exists rate_limit_buckets_reset_idx
  on public.rate_limit_buckets (reset_at);

alter table public.rate_limit_buckets enable row level security;
revoke all on table public.rate_limit_buckets from public, anon, authenticated;

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

  insert into public.rate_limit_buckets (bucket_key, request_count, reset_at, updated_at)
  values (p_bucket_key, 1, v_now + make_interval(secs => p_window_seconds), v_now)
  on conflict (bucket_key) do update
  set request_count = case
        when public.rate_limit_buckets.reset_at <= v_now then 1
        else public.rate_limit_buckets.request_count + 1
      end,
      reset_at = case
        when public.rate_limit_buckets.reset_at <= v_now
          then v_now + make_interval(secs => p_window_seconds)
        else public.rate_limit_buckets.reset_at
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

-- A legacy event-trigger helper was accidentally left callable on the live project.
do $$
begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    execute 'revoke execute on function public.rls_auto_enable() from public, anon, authenticated';
  end if;
end;
$$;

-- Cover foreign-key maintenance and remove the duplicate v6 indexes.
drop index if exists public.idx_jobs_user_updated;
drop index if exists public.idx_job_status_events_user_match_created;

create index if not exists agent_steps_run_idx on public.agent_steps (run_id);
create index if not exists clarification_questions_profile_idx on public.clarification_questions (profile_id);
create index if not exists job_matches_job_idx on public.job_matches (job_id);
create index if not exists job_status_events_match_idx on public.job_status_events (match_id);
create index if not exists profile_fact_feedback_fact_idx on public.profile_fact_feedback (fact_id);
create index if not exists profile_facts_source_idx on public.profile_facts (source_id);
create index if not exists profile_sources_profile_idx on public.profile_sources (profile_id);
create index if not exists resume_advice_match_idx on public.resume_advice (match_id);
