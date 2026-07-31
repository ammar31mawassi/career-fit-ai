-- Recreate the tested security and data-contract differences from database
-- contract v18.
-- The upgrade test first loads the current fresh schema, applies this fixture,
-- then executes the forward v19 through v24 migrations.

alter table public.profile_sources
  drop constraint if exists profile_sources_metadata_json_check;

alter table public.profile_facts
  drop constraint if exists profile_facts_metadata_json_check,
  drop constraint if exists profile_facts_source_ids_json_check;

alter table public.profile_fact_feedback
  drop constraint if exists profile_fact_feedback_source_ids_json_check;

alter table public.jobs
  drop constraint if exists jobs_requirements_json_check;

alter table public.job_matches
  drop constraint if exists job_matches_matched_evidence_json_check,
  drop constraint if exists job_matches_missing_blockers_json_check,
  drop constraint if exists job_matches_gaps_json_check,
  drop constraint if exists job_matches_component_scores_json_check,
  drop constraint if exists job_matches_applied_caps_json_check,
  drop constraint if exists job_matches_feature_snapshot_json_check;

alter table public.resume_advice
  drop constraint if exists resume_advice_projects_json_check,
  drop constraint if exists resume_advice_skill_order_json_check,
  drop constraint if exists resume_advice_evidence_json_check;

alter table public.job_status_events
  drop constraint if exists job_status_events_previous_status_check,
  drop constraint if exists job_status_events_source_check,
  drop constraint if exists job_status_events_note_length_check;
drop index if exists public.job_status_events_user_match_occurred_idx;
drop index if exists public.job_status_events_user_match_audit_idx;
alter table public.job_status_events
  drop column if exists previous_status,
  drop column if exists occurred_at,
  drop column if exists source,
  drop column if exists note;
create index if not exists job_status_events_user_match_created_idx
  on public.job_status_events (user_id, match_id, created_at);
create index if not exists idx_job_status_events_user_match_created
  on public.job_status_events (user_id, match_id, created_at);

alter table public.job_source_runs
  drop constraint if exists job_source_runs_status_check;
alter table public.job_source_runs
  add constraint job_source_runs_status_check
  check (status in ('running', 'completed', 'failed', 'disabled'));

alter table public.agent_runs
  drop constraint if exists agent_runs_status_check;

alter table public.agent_steps
  drop constraint if exists agent_steps_status_check,
  drop constraint if exists agent_steps_attempt_check,
  drop constraint if exists agent_steps_output_json_check;

alter table public.shared_job_catalog
  drop constraint if exists shared_job_catalog_requirements_json_check,
  drop constraint if exists shared_job_catalog_career_fields_json_check;

alter table public.job_recommendations
  drop constraint if exists job_recommendations_career_fields_json_check,
  drop constraint if exists job_recommendations_reasons_json_check,
  drop constraint if exists job_recommendations_match_snapshot_json_check;

alter table public.job_requirement_revisions
  drop constraint if exists job_requirement_revisions_original_requirements_json_check,
  drop constraint if exists job_requirement_revisions_corrected_requirements_json_check,
  drop constraint if exists job_requirement_revisions_changed_fields_json_check;

alter table public.job_scans
  drop constraint if exists job_scans_payload_json_check;

alter table public.extraction_metrics
  drop constraint if exists extraction_metrics_counts_json_check;

alter table public.evaluation_examples
  drop constraint if exists evaluation_examples_features_json_check;

drop index if exists public.job_scans_user_active_input_uq;
drop index if exists public.job_scans_recovery_idx;
alter table public.job_scans
  drop column if exists lease_token;

alter table public.profile_interests
  drop constraint if exists profile_interests_profile_owner_fkey,
  drop constraint if exists profile_interests_profile_id_fkey;
alter table public.profile_interests
  add constraint profile_interests_profile_id_fkey
  foreign key (profile_id) references public.profiles(id) on delete cascade;

alter table public.profile_sources
  drop constraint if exists profile_sources_profile_owner_fkey,
  drop constraint if exists profile_sources_profile_id_fkey;
alter table public.profile_sources
  add constraint profile_sources_profile_id_fkey
  foreign key (profile_id) references public.profiles(id) on delete cascade;

alter table public.profile_facts
  drop constraint if exists profile_facts_profile_owner_fkey,
  drop constraint if exists profile_facts_source_owner_fkey,
  drop constraint if exists profile_facts_profile_id_fkey,
  drop constraint if exists profile_facts_source_id_fkey;
alter table public.profile_facts
  add constraint profile_facts_profile_id_fkey
    foreign key (profile_id) references public.profiles(id) on delete cascade,
  add constraint profile_facts_source_id_fkey
    foreign key (source_id) references public.profile_sources(id) on delete set null;

alter table public.profile_fact_feedback
  drop constraint if exists profile_fact_feedback_profile_owner_fkey,
  drop constraint if exists profile_fact_feedback_fact_owner_fkey,
  drop constraint if exists profile_fact_feedback_profile_id_fkey,
  drop constraint if exists profile_fact_feedback_fact_id_fkey;
alter table public.profile_fact_feedback
  add constraint profile_fact_feedback_profile_id_fkey
    foreign key (profile_id) references public.profiles(id) on delete cascade,
  add constraint profile_fact_feedback_fact_id_fkey
    foreign key (fact_id) references public.profile_facts(id) on delete set null;

alter table public.clarification_questions
  drop constraint if exists clarification_questions_profile_owner_fkey,
  drop constraint if exists clarification_questions_profile_id_fkey;
alter table public.clarification_questions
  add constraint clarification_questions_profile_id_fkey
  foreign key (profile_id) references public.profiles(id) on delete cascade;

alter table public.job_matches
  drop constraint if exists job_matches_job_owner_fkey,
  drop constraint if exists job_matches_job_id_fkey;
alter table public.job_matches
  add constraint job_matches_job_id_fkey
  foreign key (job_id) references public.jobs(id) on delete cascade;

alter table public.resume_advice
  drop constraint if exists resume_advice_match_owner_fkey,
  drop constraint if exists resume_advice_match_id_fkey;
alter table public.resume_advice
  add constraint resume_advice_match_id_fkey
  foreign key (match_id) references public.job_matches(id) on delete cascade;

alter table public.job_status_events
  drop constraint if exists job_status_events_match_owner_fkey,
  drop constraint if exists job_status_events_match_id_fkey;
alter table public.job_status_events
  add constraint job_status_events_match_id_fkey
  foreign key (match_id) references public.job_matches(id) on delete cascade;

alter table public.agent_steps
  drop constraint if exists agent_steps_run_owner_fkey,
  drop constraint if exists agent_steps_run_id_fkey;
alter table public.agent_steps
  add constraint agent_steps_run_id_fkey
  foreign key (run_id) references public.agent_runs(id) on delete cascade;

alter table public.job_recommendations
  drop constraint if exists job_recommendations_materialized_job_owner_fkey,
  drop constraint if exists job_recommendations_materialized_job_id_fkey;
alter table public.job_recommendations
  add constraint job_recommendations_materialized_job_id_fkey
  foreign key (materialized_job_id) references public.jobs(id) on delete set null;

alter table public.recommendation_events
  drop constraint if exists recommendation_events_recommendation_owner_fkey,
  drop constraint if exists recommendation_events_materialized_job_owner_fkey,
  drop constraint if exists recommendation_events_recommendation_id_fkey,
  drop constraint if exists recommendation_events_materialized_job_id_fkey;
alter table public.recommendation_events
  add constraint recommendation_events_recommendation_id_fkey
    foreign key (recommendation_id)
    references public.job_recommendations(id) on delete cascade,
  add constraint recommendation_events_materialized_job_id_fkey
    foreign key (materialized_job_id)
    references public.jobs(id) on delete set null;

alter table public.notification_deliveries
  drop constraint if exists notification_deliveries_recommendation_owner_fkey,
  drop constraint if exists notification_deliveries_recommendation_id_fkey;
alter table public.notification_deliveries
  add constraint notification_deliveries_recommendation_id_fkey
  foreign key (recommendation_id)
  references public.job_recommendations(id) on delete cascade;

alter table public.job_requirement_revisions
  drop constraint if exists job_requirement_revisions_job_owner_fkey,
  drop constraint if exists job_requirement_revisions_job_id_fkey;
alter table public.job_requirement_revisions
  add constraint job_requirement_revisions_job_id_fkey
  foreign key (job_id) references public.jobs(id) on delete cascade;

alter table public.job_scans
  drop constraint if exists job_scans_result_job_owner_fkey,
  drop constraint if exists job_scans_result_job_id_fkey;
alter table public.job_scans
  add constraint job_scans_result_job_id_fkey
  foreign key (result_job_id) references public.jobs(id) on delete set null;

alter table public.profiles
  drop constraint if exists profiles_owner_key;
alter table public.profile_sources
  drop constraint if exists profile_sources_owner_key;
alter table public.profile_facts
  drop constraint if exists profile_facts_owner_key;
alter table public.jobs
  drop constraint if exists jobs_owner_key;
alter table public.job_matches
  drop constraint if exists job_matches_owner_key;
alter table public.agent_runs
  drop constraint if exists agent_runs_owner_key;
alter table public.job_recommendations
  drop constraint if exists job_recommendations_owner_key;

drop policy if exists profiles_owner_select on public.profiles;
drop policy if exists profiles_owner_all on public.profiles;
create policy profiles_owner_all on public.profiles
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists profile_interests_owner_select
  on public.profile_interests;
drop policy if exists profile_interests_owner_all
  on public.profile_interests;
create policy profile_interests_owner_all on public.profile_interests
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists profile_sources_owner_select on public.profile_sources;
drop policy if exists profile_sources_owner_all on public.profile_sources;
create policy profile_sources_owner_all on public.profile_sources
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists profile_facts_owner_select on public.profile_facts;
drop policy if exists profile_facts_owner_all on public.profile_facts;
create policy profile_facts_owner_all on public.profile_facts
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists profile_fact_feedback_owner_insert
  on public.profile_fact_feedback;
create policy profile_fact_feedback_owner_insert on public.profile_fact_feedback
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists clarification_questions_owner_select
  on public.clarification_questions;
drop policy if exists clarification_questions_owner_all
  on public.clarification_questions;
create policy clarification_questions_owner_all on public.clarification_questions
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists jobs_owner_select on public.jobs;
drop policy if exists jobs_owner_all on public.jobs;
create policy jobs_owner_all on public.jobs
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists job_matches_owner_select on public.job_matches;
drop policy if exists job_matches_owner_all on public.job_matches;
create policy job_matches_owner_all on public.job_matches
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists resume_advice_owner_select on public.resume_advice;
drop policy if exists resume_advice_owner_all on public.resume_advice;
create policy resume_advice_owner_all on public.resume_advice
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists job_status_events_owner_select
  on public.job_status_events;
drop policy if exists job_status_events_owner_all
  on public.job_status_events;
create policy job_status_events_owner_all on public.job_status_events
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists agent_runs_owner_select on public.agent_runs;
drop policy if exists agent_runs_owner_all on public.agent_runs;
create policy agent_runs_owner_all on public.agent_runs
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists agent_steps_owner_select on public.agent_steps;
drop policy if exists agent_steps_owner_all on public.agent_steps;
create policy agent_steps_owner_all on public.agent_steps
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists job_recommendations_owner_update
  on public.job_recommendations;
create policy job_recommendations_owner_update on public.job_recommendations
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists job_notification_preferences_owner_update
  on public.job_notification_preferences;
create policy job_notification_preferences_owner_update
  on public.job_notification_preferences
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists job_requirement_revisions_owner_select
  on public.job_requirement_revisions;
drop policy if exists job_requirement_revisions_owner_all
  on public.job_requirement_revisions;
create policy job_requirement_revisions_owner_all
  on public.job_requirement_revisions
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists job_scans_owner_select on public.job_scans;
drop policy if exists job_scans_owner_all on public.job_scans;
create policy job_scans_owner_all on public.job_scans
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

grant insert, update, delete, truncate, references, trigger
  on all tables in schema public to anon, authenticated;

alter default privileges for role postgres in schema public
  grant insert, update, delete, truncate, references, trigger
  on tables to anon, authenticated;

-- Recreate the pre-v21 direct-browser Storage contract so the upgrade harness
-- proves that the backend-mediated migration removes it.
grant select, insert, update, delete on storage.objects to authenticated;

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
