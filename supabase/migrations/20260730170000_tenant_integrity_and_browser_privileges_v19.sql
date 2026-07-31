-- Enforce tenant ownership at the relational boundary and make application
-- tables read-only to browser roles. All mutations flow through the backend.

begin;

alter table public.profiles
  add constraint profiles_owner_key unique (id, user_id);
alter table public.profile_sources
  add constraint profile_sources_owner_key unique (id, profile_id, user_id);
alter table public.profile_facts
  add constraint profile_facts_owner_key unique (id, profile_id, user_id);
alter table public.jobs
  add constraint jobs_owner_key unique (id, user_id);
alter table public.job_matches
  add constraint job_matches_owner_key unique (id, user_id);
alter table public.agent_runs
  add constraint agent_runs_owner_key unique (id, user_id);
alter table public.job_recommendations
  add constraint job_recommendations_owner_key unique (id, user_id);

alter table public.profile_interests
  drop constraint if exists profile_interests_profile_id_fkey;
alter table public.profile_interests
  add constraint profile_interests_profile_owner_fkey
  foreign key (profile_id, user_id)
  references public.profiles(id, user_id) on delete cascade;

alter table public.profile_sources
  drop constraint if exists profile_sources_profile_id_fkey;
alter table public.profile_sources
  add constraint profile_sources_profile_owner_fkey
  foreign key (profile_id, user_id)
  references public.profiles(id, user_id) on delete cascade;

alter table public.profile_facts
  drop constraint if exists profile_facts_profile_id_fkey,
  drop constraint if exists profile_facts_source_id_fkey;
alter table public.profile_facts
  add constraint profile_facts_profile_owner_fkey
    foreign key (profile_id, user_id)
    references public.profiles(id, user_id) on delete cascade,
  add constraint profile_facts_source_owner_fkey
    foreign key (source_id, profile_id, user_id)
    references public.profile_sources(id, profile_id, user_id)
    on delete set null (source_id);

alter table public.profile_fact_feedback
  drop constraint if exists profile_fact_feedback_profile_id_fkey,
  drop constraint if exists profile_fact_feedback_fact_id_fkey;
alter table public.profile_fact_feedback
  add constraint profile_fact_feedback_profile_owner_fkey
    foreign key (profile_id, user_id)
    references public.profiles(id, user_id) on delete cascade,
  add constraint profile_fact_feedback_fact_owner_fkey
    foreign key (fact_id, profile_id, user_id)
    references public.profile_facts(id, profile_id, user_id)
    on delete set null (fact_id);

alter table public.clarification_questions
  drop constraint if exists clarification_questions_profile_id_fkey;
alter table public.clarification_questions
  add constraint clarification_questions_profile_owner_fkey
  foreign key (profile_id, user_id)
  references public.profiles(id, user_id) on delete cascade;

alter table public.job_matches
  drop constraint if exists job_matches_job_id_fkey;
alter table public.job_matches
  add constraint job_matches_job_owner_fkey
  foreign key (job_id, user_id)
  references public.jobs(id, user_id) on delete cascade;

alter table public.resume_advice
  drop constraint if exists resume_advice_match_id_fkey;
alter table public.resume_advice
  add constraint resume_advice_match_owner_fkey
  foreign key (match_id, user_id)
  references public.job_matches(id, user_id) on delete cascade;

alter table public.job_status_events
  drop constraint if exists job_status_events_match_id_fkey;
alter table public.job_status_events
  add constraint job_status_events_match_owner_fkey
  foreign key (match_id, user_id)
  references public.job_matches(id, user_id) on delete cascade;

alter table public.agent_steps
  drop constraint if exists agent_steps_run_id_fkey;
alter table public.agent_steps
  add constraint agent_steps_run_owner_fkey
  foreign key (run_id, user_id)
  references public.agent_runs(id, user_id) on delete cascade;

alter table public.job_recommendations
  drop constraint if exists job_recommendations_materialized_job_id_fkey;
alter table public.job_recommendations
  add constraint job_recommendations_materialized_job_owner_fkey
  foreign key (materialized_job_id, user_id)
  references public.jobs(id, user_id) on delete set null (materialized_job_id);

alter table public.recommendation_events
  drop constraint if exists recommendation_events_recommendation_id_fkey,
  drop constraint if exists recommendation_events_materialized_job_id_fkey;
alter table public.recommendation_events
  add constraint recommendation_events_recommendation_owner_fkey
    foreign key (recommendation_id, user_id)
    references public.job_recommendations(id, user_id) on delete cascade,
  add constraint recommendation_events_materialized_job_owner_fkey
    foreign key (materialized_job_id, user_id)
    references public.jobs(id, user_id) on delete set null (materialized_job_id);

alter table public.notification_deliveries
  drop constraint if exists notification_deliveries_recommendation_id_fkey;
alter table public.notification_deliveries
  add constraint notification_deliveries_recommendation_owner_fkey
  foreign key (recommendation_id, user_id)
  references public.job_recommendations(id, user_id) on delete cascade;

alter table public.job_requirement_revisions
  drop constraint if exists job_requirement_revisions_job_id_fkey;
alter table public.job_requirement_revisions
  add constraint job_requirement_revisions_job_owner_fkey
  foreign key (job_id, user_id)
  references public.jobs(id, user_id) on delete cascade;

alter table public.job_scans
  drop constraint if exists job_scans_result_job_id_fkey;
alter table public.job_scans
  add constraint job_scans_result_job_owner_fkey
  foreign key (result_job_id, user_id)
  references public.jobs(id, user_id) on delete set null (result_job_id);

revoke insert, update, delete, truncate, references, trigger
  on all tables in schema public from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke insert, update, delete, truncate, references, trigger
  on tables from anon, authenticated;

drop policy if exists profiles_owner_all on public.profiles;
drop policy if exists profiles_owner_select on public.profiles;
create policy profiles_owner_select on public.profiles
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists profile_interests_owner_all on public.profile_interests;
drop policy if exists profile_interests_owner_select on public.profile_interests;
create policy profile_interests_owner_select on public.profile_interests
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists profile_sources_owner_all on public.profile_sources;
drop policy if exists profile_sources_owner_select on public.profile_sources;
create policy profile_sources_owner_select on public.profile_sources
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists profile_facts_owner_all on public.profile_facts;
drop policy if exists profile_facts_owner_select on public.profile_facts;
create policy profile_facts_owner_select on public.profile_facts
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists profile_fact_feedback_owner_insert
  on public.profile_fact_feedback;
drop policy if exists profile_fact_feedback_owner_select
  on public.profile_fact_feedback;
create policy profile_fact_feedback_owner_select on public.profile_fact_feedback
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists clarification_questions_owner_all
  on public.clarification_questions;
drop policy if exists clarification_questions_owner_select
  on public.clarification_questions;
create policy clarification_questions_owner_select on public.clarification_questions
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists jobs_owner_all on public.jobs;
drop policy if exists jobs_owner_select on public.jobs;
create policy jobs_owner_select on public.jobs
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists job_matches_owner_all on public.job_matches;
drop policy if exists job_matches_owner_select on public.job_matches;
create policy job_matches_owner_select on public.job_matches
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists resume_advice_owner_all on public.resume_advice;
drop policy if exists resume_advice_owner_select on public.resume_advice;
create policy resume_advice_owner_select on public.resume_advice
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists job_status_events_owner_all on public.job_status_events;
drop policy if exists job_status_events_owner_select on public.job_status_events;
create policy job_status_events_owner_select on public.job_status_events
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists agent_runs_owner_all on public.agent_runs;
drop policy if exists agent_runs_owner_select on public.agent_runs;
create policy agent_runs_owner_select on public.agent_runs
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists agent_steps_owner_all on public.agent_steps;
drop policy if exists agent_steps_owner_select on public.agent_steps;
create policy agent_steps_owner_select on public.agent_steps
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists job_recommendations_owner_update
  on public.job_recommendations;

drop policy if exists job_notification_preferences_owner_update
  on public.job_notification_preferences;

drop policy if exists job_requirement_revisions_owner_all
  on public.job_requirement_revisions;
drop policy if exists job_requirement_revisions_owner_select
  on public.job_requirement_revisions;
create policy job_requirement_revisions_owner_select
  on public.job_requirement_revisions
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists job_scans_owner_all on public.job_scans;
drop policy if exists job_scans_owner_select on public.job_scans;
create policy job_scans_owner_select on public.job_scans
  for select to authenticated
  using ((select auth.uid()) = user_id);

commit;
