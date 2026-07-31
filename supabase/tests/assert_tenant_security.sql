-- Executed against both a fresh schema and the v18 -> v24 upgrade result.

do $$
begin
  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'job_scans'
      and column_name = 'lease_token'
      and is_nullable = 'NO'
  ) then
    raise exception 'public.job_scans.lease_token is missing or nullable';
  end if;

  if not exists (
    select 1
    from pg_index
    join pg_class on pg_class.oid = pg_index.indexrelid
    join pg_namespace on pg_namespace.oid = pg_class.relnamespace
    where pg_namespace.nspname = 'public'
      and pg_class.relname = 'job_scans_user_active_input_uq'
      and pg_index.indisunique
      and pg_get_expr(pg_index.indpred, pg_index.indrelid)
        = '(status = ANY (ARRAY[''queued''::text, ''running''::text, ''cancel_requested''::text]))'
  ) then
    raise exception 'active-input partial unique index is missing or has the wrong predicate';
  end if;

  if not exists (
    select 1
    from pg_constraint
    join pg_class on pg_class.oid = pg_constraint.conrelid
    join pg_namespace on pg_namespace.oid = pg_class.relnamespace
    where pg_namespace.nspname = 'public'
      and pg_class.relname = 'job_source_runs'
      and pg_constraint.conname = 'job_source_runs_status_check'
      and pg_constraint.contype = 'c'
      and position('degraded' in pg_get_constraintdef(pg_constraint.oid)) > 0
      and position('inconclusive' in pg_get_constraintdef(pg_constraint.oid)) > 0
  ) then
    raise exception 'job source run status constraint is missing or incomplete';
  end if;

  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'job_status_events'
      and column_name in ('previous_status', 'occurred_at', 'source', 'note')
      and is_nullable = 'NO'
  ) <> 4 then
    raise exception 'application-event context columns are missing or nullable';
  end if;

  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'job_status_events'
      and column_name = 'source'
      and position('system' in coalesce(column_default, '')) > 0
  ) then
    raise exception 'application-event source default is not system';
  end if;

  if not exists (
    select 1
    from pg_class
    join pg_namespace on pg_namespace.oid = pg_class.relnamespace
    where pg_namespace.nspname = 'public'
      and pg_class.relname = 'job_status_events_user_match_occurred_idx'
      and pg_class.relkind = 'i'
  ) then
    raise exception 'application-event occurred-time index is missing';
  end if;

  if not exists (
    select 1
    from pg_class
    join pg_namespace on pg_namespace.oid = pg_class.relnamespace
    where pg_namespace.nspname = 'public'
      and pg_class.relname = 'job_status_events_user_match_audit_idx'
      and pg_class.relkind = 'i'
  ) then
    raise exception 'application-event audit-order index is missing';
  end if;

  if exists (
    select 1
    from pg_class
    join pg_namespace on pg_namespace.oid = pg_class.relnamespace
    where pg_namespace.nspname = 'public'
      and pg_class.relname in (
        'job_status_events_user_match_created_idx',
        'idx_job_status_events_user_match_created'
      )
      and pg_class.relkind = 'i'
  ) then
    raise exception 'obsolete application-event created-time index remains';
  end if;
end
$$;

do $$
declare
  privilege_name text;
  writable_policies text;
begin
  foreach privilege_name in array array[
    'SELECT',
    'INSERT',
    'UPDATE',
    'DELETE',
    'TRUNCATE',
    'REFERENCES',
    'TRIGGER'
  ] loop
    if has_table_privilege(
      'authenticated',
      'storage.objects',
      privilege_name
    ) then
      raise exception 'authenticated still has % on storage.objects', privilege_name;
    end if;
  end loop;

  select string_agg(policyname, ', ' order by policyname)
    into writable_policies
  from pg_policies
  where schemaname = 'storage'
    and tablename = 'objects'
    and 'authenticated' = any(roles);

  if writable_policies is not null then
    raise exception 'authenticated still has Storage policies: %', writable_policies;
  end if;

  if not has_table_privilege('service_role', 'storage.objects', 'SELECT')
    or not has_table_privilege('service_role', 'storage.objects', 'INSERT')
    or not has_table_privilege('service_role', 'storage.objects', 'UPDATE')
    or not has_table_privilege('service_role', 'storage.objects', 'DELETE') then
    raise exception 'service_role lost required storage.objects privileges';
  end if;
end
$$;

do $$
declare
  missing_constraints text;
begin
  select string_agg(expected.name, ', ' order by expected.name)
    into missing_constraints
  from unnest(array[
    'profile_interests_profile_owner_fkey',
    'profile_sources_profile_owner_fkey',
    'profile_facts_profile_owner_fkey',
    'profile_facts_source_owner_fkey',
    'profile_fact_feedback_profile_owner_fkey',
    'profile_fact_feedback_fact_owner_fkey',
    'clarification_questions_profile_owner_fkey',
    'job_matches_job_owner_fkey',
    'resume_advice_match_owner_fkey',
    'job_status_events_match_owner_fkey',
    'agent_steps_run_owner_fkey',
    'job_recommendations_materialized_job_owner_fkey',
    'recommendation_events_recommendation_owner_fkey',
    'recommendation_events_materialized_job_owner_fkey',
    'notification_deliveries_recommendation_owner_fkey',
    'job_requirement_revisions_job_owner_fkey',
    'job_scans_result_job_owner_fkey'
  ]) as expected(name)
  where not exists (
    select 1
    from pg_constraint
    where conname = expected.name
      and contype = 'f'
  );

  if missing_constraints is not null then
    raise exception 'missing tenant-owner foreign keys: %', missing_constraints;
  end if;
end
$$;

do $$
declare
  table_name text;
  role_name text;
  privilege_name text;
  writable_policies text;
begin
  foreach role_name in array array['anon', 'authenticated'] loop
    foreach table_name in array array[
      'profiles',
      'profile_interests',
      'profile_sources',
      'profile_facts',
      'profile_fact_feedback',
      'clarification_questions',
      'jobs',
      'job_matches',
      'resume_advice',
      'job_status_events',
      'agent_runs',
      'agent_steps',
      'shared_job_catalog',
      'recommendation_runs',
      'job_recommendations',
      'recommendation_events',
      'recommendation_field_calibrations',
      'job_source_runs',
      'job_discovery_beta_members',
      'job_notification_preferences',
      'notification_deliveries',
      'job_requirement_revisions',
      'job_scans',
      'extraction_metrics',
      'evaluation_examples'
    ] loop
      foreach privilege_name in array array[
        'INSERT',
        'UPDATE',
        'DELETE',
        'TRUNCATE',
        'REFERENCES',
        'TRIGGER'
      ] loop
        if has_table_privilege(
          role_name,
          format('public.%I', table_name),
          privilege_name
        ) then
          raise exception '% still has % on public.%', role_name, privilege_name, table_name;
        end if;
      end loop;
    end loop;
  end loop;

  if not has_table_privilege('authenticated', 'public.profiles', 'SELECT') then
    raise exception 'authenticated lost required SELECT access to public.profiles';
  end if;

  select string_agg(
    format('%I.%I[%s]', tablename, policyname, cmd),
    ', '
    order by tablename, policyname
  )
    into writable_policies
  from pg_policies
  where schemaname = 'public'
    and 'authenticated' = any(roles)
    and cmd <> 'SELECT'
    and tablename = any(array[
      'profiles',
      'profile_interests',
      'profile_sources',
      'profile_facts',
      'profile_fact_feedback',
      'clarification_questions',
      'jobs',
      'job_matches',
      'resume_advice',
      'job_status_events',
      'agent_runs',
      'agent_steps',
      'job_recommendations',
      'job_notification_preferences',
      'job_requirement_revisions',
      'job_scans'
    ]);

  if writable_policies is not null then
    raise exception 'authenticated still has writable RLS policies: %', writable_policies;
  end if;
end
$$;

insert into auth.users (id)
values
  ('00000000-0000-0000-0000-000000000101'),
  ('00000000-0000-0000-0000-000000000102');

insert into public.profiles (user_id, summary)
values
  ('00000000-0000-0000-0000-000000000101', 'tenant one'),
  ('00000000-0000-0000-0000-000000000102', 'tenant two');

insert into public.profile_sources (
  user_id,
  profile_id,
  source_type,
  title
)
select
  user_id,
  id,
  'cv',
  summary || '.pdf'
from public.profiles;

insert into public.profile_facts (
  user_id,
  profile_id,
  source_id,
  fact_type,
  value
)
select
  profile.user_id,
  profile.id,
  source.id,
  'skill',
  profile.summary
from public.profiles as profile
join public.profile_sources as source
  on source.profile_id = profile.id;

insert into public.jobs (user_id, content_hash)
values
  ('00000000-0000-0000-0000-000000000101', 'tenant-one-job'),
  ('00000000-0000-0000-0000-000000000102', 'tenant-two-job');

insert into public.job_matches (user_id, job_id)
select user_id, id from public.jobs;

insert into public.agent_runs (user_id, workflow_type)
values
  ('00000000-0000-0000-0000-000000000101', 'tenant-one-run'),
  ('00000000-0000-0000-0000-000000000102', 'tenant-two-run');

insert into public.shared_job_catalog (content_hash)
values ('shared-catalog-job');

insert into public.job_recommendations (
  user_id,
  catalog_job_id,
  model_version
)
select
  users.id,
  catalog.id,
  'security-test'
from auth.users as users
cross join public.shared_job_catalog as catalog;

create or replace function pg_temp.expect_foreign_key_violation(command text)
returns void
language plpgsql
as $$
begin
  begin
    execute command;
  exception
    when foreign_key_violation then
      return;
  end;
  raise exception 'expected foreign_key_violation for: %', command;
end
$$;

create or replace function pg_temp.expect_unique_violation(command text)
returns void
language plpgsql
as $$
begin
  begin
    execute command;
  exception
    when unique_violation then
      return;
  end;
  raise exception 'expected unique_violation for: %', command;
end
$$;

create or replace function pg_temp.expect_data_contract_rejection(command text)
returns void
language plpgsql
as $$
begin
  begin
    execute command;
  exception
    when others then
      if sqlstate in ('22P02', '23514') then
        return;
      end if;
      raise;
  end;
  raise exception 'expected data-contract rejection for: %', command;
end
$$;

select pg_temp.expect_data_contract_rejection($command$
  insert into public.profile_sources (
    user_id,
    profile_id,
    source_type,
    title,
    metadata_json
  )
  select
    user_id,
    id,
    'manual',
    'invalid-json-shape',
    '[]'
  from public.profiles
  where user_id = '00000000-0000-0000-0000-000000000101'
$command$);

select pg_temp.expect_data_contract_rejection($command$
  insert into public.agent_runs (user_id, workflow_type, status)
  values (
    '00000000-0000-0000-0000-000000000101',
    'invalid-status-test',
    'typo'
  )
$command$);

select pg_temp.expect_data_contract_rejection($command$
  insert into public.agent_steps (
    user_id,
    run_id,
    step_key,
    title,
    status
  )
  select
    user_id,
    id,
    'invalid-status-test',
    'Invalid status test',
    'typo'
  from public.agent_runs
  where user_id = '00000000-0000-0000-0000-000000000101'
  limit 1
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.profile_interests (user_id, profile_id, interest)
  select
    '00000000-0000-0000-0000-000000000101',
    id,
    'cross-tenant-interest'
  from public.profiles
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.profile_sources (
    user_id,
    profile_id,
    source_type,
    title
  )
  select
    '00000000-0000-0000-0000-000000000101',
    id,
    'cv',
    'cross-tenant.pdf'
  from public.profiles
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.profile_facts (
    user_id,
    profile_id,
    fact_type,
    value
  )
  select
    '00000000-0000-0000-0000-000000000101',
    id,
    'skill',
    'cross-tenant-fact'
  from public.profiles
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.profile_facts (
    user_id,
    profile_id,
    source_id,
    fact_type,
    value
  )
  select
    '00000000-0000-0000-0000-000000000101',
    own_profile.id,
    foreign_source.id,
    'skill',
    'cross-tenant-source'
  from public.profiles as own_profile
  cross join public.profile_sources as foreign_source
  where own_profile.user_id = '00000000-0000-0000-0000-000000000101'
    and foreign_source.user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.profile_fact_feedback (
    user_id,
    profile_id,
    fact_id,
    fact_type,
    action
  )
  select
    '00000000-0000-0000-0000-000000000101',
    own_profile.id,
    foreign_fact.id,
    'skill',
    'rejected'
  from public.profiles as own_profile
  cross join public.profile_facts as foreign_fact
  where own_profile.user_id = '00000000-0000-0000-0000-000000000101'
    and foreign_fact.user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.profile_fact_feedback (
    user_id,
    profile_id,
    fact_type,
    action
  )
  select
    '00000000-0000-0000-0000-000000000101',
    id,
    'skill',
    'rejected'
  from public.profiles
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.clarification_questions (
    user_id,
    profile_id,
    field_key,
    question
  )
  select
    '00000000-0000-0000-0000-000000000101',
    id,
    'cross_tenant',
    'Should this be rejected?'
  from public.profiles
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.job_matches (user_id, job_id)
  select
    '00000000-0000-0000-0000-000000000101',
    id
  from public.jobs
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.resume_advice (user_id, match_id)
  select
    '00000000-0000-0000-0000-000000000101',
    id
  from public.job_matches
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.job_status_events (user_id, match_id, status)
  select
    '00000000-0000-0000-0000-000000000101',
    id,
    'Lead'
  from public.job_matches
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.agent_steps (
    user_id,
    run_id,
    step_key,
    title
  )
  select
    '00000000-0000-0000-0000-000000000101',
    id,
    'cross-tenant',
    'Cross-tenant step'
  from public.agent_runs
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.job_recommendations (
    user_id,
    catalog_job_id,
    materialized_job_id,
    model_version
  )
  select
    '00000000-0000-0000-0000-000000000101',
    catalog.id,
    foreign_job.id,
    'cross-tenant-materialized-job'
  from public.shared_job_catalog as catalog
  cross join public.jobs as foreign_job
  where foreign_job.user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.recommendation_events (
    user_id,
    recommendation_id,
    catalog_job_id,
    event_type,
    score_band
  )
  select
    '00000000-0000-0000-0000-000000000101',
    recommendation.id,
    recommendation.catalog_job_id,
    'viewed',
    'possible'
  from public.job_recommendations as recommendation
  where recommendation.user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.recommendation_events (
    user_id,
    recommendation_id,
    catalog_job_id,
    materialized_job_id,
    event_type,
    score_band
  )
  select
    recommendation.user_id,
    recommendation.id,
    recommendation.catalog_job_id,
    foreign_job.id,
    'saved',
    'possible'
  from public.job_recommendations as recommendation
  cross join public.jobs as foreign_job
  where recommendation.user_id = '00000000-0000-0000-0000-000000000101'
    and foreign_job.user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.notification_deliveries (
    user_id,
    recommendation_id
  )
  select
    '00000000-0000-0000-0000-000000000101',
    id
  from public.job_recommendations
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.job_requirement_revisions (user_id, job_id)
  select
    '00000000-0000-0000-0000-000000000101',
    id
  from public.jobs
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

select pg_temp.expect_foreign_key_violation($command$
  insert into public.job_scans (user_id, result_job_id)
  select
    '00000000-0000-0000-0000-000000000101',
    id
  from public.jobs
  where user_id = '00000000-0000-0000-0000-000000000102'
$command$);

insert into public.job_scans (user_id, input_hash, payload_json)
values (
  '00000000-0000-0000-0000-000000000101',
  'active-input-invariant',
  '{}'
);

select pg_temp.expect_unique_violation($command$
  insert into public.job_scans (user_id, input_hash, status)
  values (
    '00000000-0000-0000-0000-000000000101',
    'active-input-invariant',
    'running'
  )
$command$);

update public.job_scans
set status = 'cancel_requested'
where user_id = '00000000-0000-0000-0000-000000000101'
  and input_hash = 'active-input-invariant';

select pg_temp.expect_unique_violation($command$
  insert into public.job_scans (user_id, input_hash, status)
  values (
    '00000000-0000-0000-0000-000000000101',
    'active-input-invariant',
    'queued'
  )
$command$);

update public.job_scans
set status = 'cancelled'
where user_id = '00000000-0000-0000-0000-000000000101'
  and input_hash = 'active-input-invariant';

insert into public.job_scans (user_id, input_hash, status)
values (
  '00000000-0000-0000-0000-000000000101',
  'active-input-invariant',
  'queued'
);

set role authenticated;
select set_config(
  'request.jwt.claim.sub',
  '00000000-0000-0000-0000-000000000101',
  false
);

do $$
declare
  visible_count integer;
  visible_summary text;
begin
  select count(*), min(summary)
    into visible_count, visible_summary
  from public.profiles;

  if visible_count <> 1 or visible_summary <> 'tenant one' then
    raise exception
      'tenant-one profile isolation failed: count=%, summary=%',
      visible_count,
      visible_summary;
  end if;
end
$$;

reset role;
