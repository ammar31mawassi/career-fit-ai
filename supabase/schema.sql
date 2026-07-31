-- Career Fit AI fresh-install Supabase schema through database contract v24.
-- Run once in a new Supabase project. Existing databases must use the
-- forward-only files and recorded release order in supabase/migrations/.

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
  recommendations_enabled boolean not null default false,
  last_analyzed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_user_id_unique unique (user_id),
  constraint profiles_owner_key unique (id, user_id)
);

create table if not exists public.profile_interests (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null,
  interest text not null,
  created_at timestamptz not null default now(),
  constraint profile_interests_profile_interest_unique unique (profile_id, interest),
  constraint profile_interests_profile_owner_fkey
    foreign key (profile_id, user_id)
    references public.profiles(id, user_id) on delete cascade
);

create table if not exists public.profile_sources (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null,
  source_type text not null,
  title text not null default '',
  storage_path text not null default '',
  content_text text not null default '',
  metadata_json text not null default '{}'
    constraint profile_sources_metadata_json_check
    check (jsonb_typeof(metadata_json::jsonb) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profile_sources_owner_key unique (id, profile_id, user_id),
  constraint profile_sources_profile_owner_fkey
    foreign key (profile_id, user_id)
    references public.profiles(id, user_id) on delete cascade
);

create table if not exists public.profile_facts (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null,
  source_id bigint,
  fact_type text not null,
  value text not null,
  evidence text not null default '',
  metadata_json text not null default '{}'
    constraint profile_facts_metadata_json_check
    check (jsonb_typeof(metadata_json::jsonb) = 'object'),
  source_ids_json text not null default '[]'
    constraint profile_facts_source_ids_json_check
    check (jsonb_typeof(source_ids_json::jsonb) = 'array'),
  support_count integer not null default 1 check (support_count >= 1),
  extraction_key text not null default '',
  confidence numeric not null default 0 check (confidence >= 0 and confidence <= 1),
  user_approved boolean not null default false,
  review_status text not null default 'pending' check (review_status in ('pending', 'approved', 'rejected')),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profile_facts_owner_key unique (id, profile_id, user_id),
  constraint profile_facts_profile_owner_fkey
    foreign key (profile_id, user_id)
    references public.profiles(id, user_id) on delete cascade,
  constraint profile_facts_source_owner_fkey
    foreign key (source_id, profile_id, user_id)
    references public.profile_sources(id, profile_id, user_id)
    on delete set null (source_id)
);

create table if not exists public.profile_fact_feedback (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null,
  fact_id bigint,
  fact_type text not null,
  extraction_key text not null default '',
  action text not null check (action in ('pending', 'approved', 'rejected', 'edited_and_approved', 'manually_added')),
  original_value text not null default '',
  corrected_value text not null default '',
  source_ids_json text not null default '[]'
    constraint profile_fact_feedback_source_ids_json_check
    check (jsonb_typeof(source_ids_json::jsonb) = 'array'),
  extractor_version text not null default '',
  created_at timestamptz not null default now(),
  constraint profile_fact_feedback_profile_owner_fkey
    foreign key (profile_id, user_id)
    references public.profiles(id, user_id) on delete cascade,
  constraint profile_fact_feedback_fact_owner_fkey
    foreign key (fact_id, profile_id, user_id)
    references public.profile_facts(id, profile_id, user_id)
    on delete set null (fact_id)
);

create table if not exists public.clarification_questions (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null,
  field_key text not null,
  question text not null,
  answer text not null default '',
  status text not null default 'open',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint clarification_questions_status_check
    check (status in ('open', 'answered', 'skipped')),
  constraint clarification_questions_profile_owner_fkey
    foreign key (profile_id, user_id)
    references public.profiles(id, user_id) on delete cascade
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
  requirements_json text not null default '{}'
    constraint jobs_requirements_json_check
    check (jsonb_typeof(requirements_json::jsonb) = 'object'),
  status text not null default 'analyzed',
  error text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint jobs_user_content_hash_unique unique (user_id, content_hash),
  constraint jobs_owner_key unique (id, user_id)
);

create table if not exists public.job_matches (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id bigint not null,
  score numeric not null default 0 check (score >= 0 and score <= 100),
  fit_level text not null default 'Weak' check (fit_level in ('Strong', 'Medium', 'Weak')),
  confidence numeric not null default 0 check (confidence >= 0 and confidence <= 1),
  status text not null default 'Lead' check (status in ('Lead', 'Applied', 'Interview', 'Rejected', 'Withdrawn', 'Offer')),
  matched_evidence_json text not null default '[]'
    constraint job_matches_matched_evidence_json_check
    check (jsonb_typeof(matched_evidence_json::jsonb) = 'array'),
  missing_blockers_json text not null default '[]'
    constraint job_matches_missing_blockers_json_check
    check (jsonb_typeof(missing_blockers_json::jsonb) = 'array'),
  gaps_json text not null default '[]'
    constraint job_matches_gaps_json_check
    check (jsonb_typeof(gaps_json::jsonb) = 'array'),
  model_version text not null default 'fit-v1.0.0',
  ontology_version text not null default 'skills-v1.0.0',
  component_scores_json text not null default '{}'
    constraint job_matches_component_scores_json_check
    check (jsonb_typeof(component_scores_json::jsonb) = 'object'),
  applied_caps_json text not null default '[]'
    constraint job_matches_applied_caps_json_check
    check (jsonb_typeof(applied_caps_json::jsonb) = 'array'),
  feature_snapshot_json text not null default '{}'
    constraint job_matches_feature_snapshot_json_check
    check (jsonb_typeof(feature_snapshot_json::jsonb) = 'object'),
  analyzed_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint job_matches_user_job_unique unique (user_id, job_id),
  constraint job_matches_owner_key unique (id, user_id),
  constraint job_matches_job_owner_fkey
    foreign key (job_id, user_id)
    references public.jobs(id, user_id) on delete cascade
);

create table if not exists public.resume_advice (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  match_id bigint not null,
  projects_json text not null default '[]'
    constraint resume_advice_projects_json_check
    check (jsonb_typeof(projects_json::jsonb) = 'array'),
  skill_order_json text not null default '[]'
    constraint resume_advice_skill_order_json_check
    check (jsonb_typeof(skill_order_json::jsonb) = 'array'),
  about_text text not null default '',
  template_id text not null default '',
  evidence_json text not null default '[]'
    constraint resume_advice_evidence_json_check
    check (jsonb_typeof(evidence_json::jsonb) = 'array'),
  generated_at timestamptz not null default now(),
  constraint resume_advice_user_match_unique unique (user_id, match_id),
  constraint resume_advice_match_owner_fkey
    foreign key (match_id, user_id)
    references public.job_matches(id, user_id) on delete cascade
);

create table if not exists public.job_status_events (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  match_id bigint not null,
  previous_status text not null default '',
  status text not null check (status in ('Lead', 'Applied', 'Interview', 'Rejected', 'Withdrawn', 'Offer')),
  occurred_at timestamptz not null default now(),
  source text not null default 'system',
  note text not null default '',
  created_at timestamptz not null default now(),
  constraint job_status_events_previous_status_check
    check (previous_status in ('', 'Lead', 'Applied', 'Interview', 'Rejected', 'Withdrawn', 'Offer')),
  constraint job_status_events_source_check
    check (source in ('system', 'user', 'correction', 'backfill', 'legacy')),
  constraint job_status_events_note_length_check
    check (char_length(note) <= 500),
  constraint job_status_events_match_owner_fkey
    foreign key (match_id, user_id)
    references public.job_matches(id, user_id) on delete cascade
);

create table if not exists public.agent_runs (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  workflow_type text not null,
  subject_type text not null default '',
  subject_id bigint,
  input_hash text not null default '',
  status text not null default 'running'
    constraint agent_runs_status_check
    check (status in ('running', 'completed', 'failed', 'reused')),
  version text not null default '',
  summary text not null default '',
  error text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint agent_runs_owner_key unique (id, user_id)
);

create table if not exists public.agent_steps (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  run_id bigint not null,
  step_key text not null,
  title text not null,
  status text not null default 'running'
    constraint agent_steps_status_check
    check (status in ('running', 'completed', 'failed')),
  attempt integer not null default 1
    constraint agent_steps_attempt_check
    check (attempt >= 1),
  progress text not null default '',
  output_json text not null default '{}'
    constraint agent_steps_output_json_check
    check (jsonb_typeof(output_json::jsonb) = 'object'),
  error text not null default '',
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint agent_steps_run_owner_fkey
    foreign key (run_id, user_id)
    references public.agent_runs(id, user_id) on delete cascade
);

create extension if not exists pgmq;

do $$
begin
  if not exists (select 1 from pgmq.list_queues() where queue_name = 'careerfit_job_scans') then
    perform pgmq.create('careerfit_job_scans');
  end if;
  if not exists (select 1 from pgmq.list_queues() where queue_name = 'careerfit_job_recommendations') then
    perform pgmq.create('careerfit_job_recommendations');
  end if;
  if not exists (select 1 from pgmq.list_queues() where queue_name = 'careerfit_email_notifications') then
    perform pgmq.create('careerfit_email_notifications');
  end if;
end
$$;

create table if not exists public.shared_job_catalog (
  id bigint generated by default as identity primary key,
  content_hash text not null unique,
  source_url text not null default '',
  application_link text not null default '',
  company text not null default 'Unknown Company',
  role text not null default 'Unknown Role',
  location text not null default '',
  description_text text not null default '',
  requirements_json text not null default '{}'
    constraint shared_job_catalog_requirements_json_check
    check (jsonb_typeof(requirements_json::jsonb) = 'object'),
  domain text not null default '',
  career_fields_json text not null default '[]'
    constraint shared_job_catalog_career_fields_json_check
    check (jsonb_typeof(career_fields_json::jsonb) = 'array'),
  source_confidence double precision not null default 0,
  first_seen_by uuid references auth.users(id) on delete set null,
  source_name text not null default 'community',
  external_id text not null default '',
  source_published_at timestamptz,
  last_seen_at timestamptz,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.recommendation_runs (
  id bigint generated by default as identity primary key,
  catalog_job_id bigint not null references public.shared_job_catalog(id) on delete cascade,
  source_user_id uuid references auth.users(id) on delete set null,
  status text not null default 'running',
  candidate_count integer not null default 0,
  scored_count integer not null default 0,
  strong_count integer not null default 0,
  error text not null default '',
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.job_recommendations (
  id bigint generated by default as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  catalog_job_id bigint not null references public.shared_job_catalog(id) on delete cascade,
  materialized_job_id bigint,
  score double precision not null default 0,
  fit_level text not null default 'Weak',
  confidence double precision not null default 0,
  career_fields_json text not null default '[]'
    constraint job_recommendations_career_fields_json_check
    check (jsonb_typeof(career_fields_json::jsonb) = 'array'),
  reasons_json text not null default '[]'
    constraint job_recommendations_reasons_json_check
    check (jsonb_typeof(reasons_json::jsonb) = 'array'),
  match_snapshot_json text not null default '{}'
    constraint job_recommendations_match_snapshot_json_check
    check (jsonb_typeof(match_snapshot_json::jsonb) = 'object'),
  model_version text not null default '',
  status text not null default 'shadow_observation',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_job_recommendation_version unique (user_id, catalog_job_id, model_version),
  constraint job_recommendations_owner_key unique (id, user_id),
  constraint job_recommendations_materialized_job_owner_fkey
    foreign key (materialized_job_id, user_id)
    references public.jobs(id, user_id) on delete set null (materialized_job_id)
);

create table if not exists public.recommendation_events (
  id bigint generated by default as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  recommendation_id bigint not null,
  catalog_job_id bigint not null references public.shared_job_catalog(id) on delete cascade,
  materialized_job_id bigint,
  event_type text not null,
  dismiss_reason text not null default '',
  score double precision not null default 0,
  score_band text not null,
  career_field text not null default 'unknown',
  source_name text not null default 'community',
  model_version text not null default '',
  created_at timestamptz not null default now(),
  constraint uq_recommendation_event_type
    unique (user_id, recommendation_id, event_type),
  constraint recommendation_events_type_check
    check (event_type in ('viewed', 'saved', 'applied', 'dismissed')),
  constraint recommendation_events_band_check
    check (score_band in ('possible', 'medium', 'strong')),
  constraint recommendation_events_reason_check
    check (
      (
        event_type = 'dismissed'
        and dismiss_reason in (
          'too_senior',
          'wrong_field',
          'wrong_location',
          'missing_skills',
          'employment_type',
          'not_interested',
          'other'
        )
      )
      or (event_type <> 'dismissed' and dismiss_reason = '')
    ),
  constraint recommendation_events_recommendation_owner_fkey
    foreign key (recommendation_id, user_id)
    references public.job_recommendations(id, user_id) on delete cascade,
  constraint recommendation_events_materialized_job_owner_fkey
    foreign key (materialized_job_id, user_id)
    references public.jobs(id, user_id) on delete set null (materialized_job_id)
);

create table if not exists public.recommendation_field_calibrations (
  career_field text primary key,
  minimum_score double precision not null default 40,
  sample_size integer not null default 0,
  positive_count integer not null default 0,
  negative_count integer not null default 0,
  possible_sample_size integer not null default 0,
  possible_positive_count integer not null default 0,
  medium_sample_size integer not null default 0,
  medium_positive_count integer not null default 0,
  window_days integer not null default 90,
  updated_at timestamptz not null default now(),
  constraint recommendation_field_threshold_check
    check (minimum_score in (40, 50, 65)),
  constraint recommendation_field_counts_check
    check (
      sample_size >= 0
      and positive_count >= 0
      and negative_count >= 0
      and positive_count + negative_count = sample_size
      and possible_sample_size >= 0
      and possible_positive_count between 0 and possible_sample_size
      and medium_sample_size >= 0
      and medium_positive_count between 0 and medium_sample_size
    )
);

create table if not exists public.job_source_runs (
  id bigint generated by default as identity primary key,
  source_name text not null,
  status text not null default 'running',
  records_seen integer not null default 0,
  records_valid integer not null default 0,
  created_count integer not null default 0,
  updated_count integer not null default 0,
  ignored_count integer not null default 0,
  deactivated_count integer not null default 0,
  error_code text not null default '',
  error text not null default '',
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint job_source_runs_status_check
    check (status in ('running', 'completed', 'failed', 'disabled', 'degraded', 'inconclusive'))
);

create table if not exists public.job_discovery_beta_members (
  user_id uuid primary key references auth.users(id) on delete cascade,
  market_code text not null default 'IL',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.job_notification_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email_enabled boolean not null default false,
  unsubscribed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.notification_deliveries (
  id bigint generated by default as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  recommendation_id bigint not null,
  channel text not null default 'email',
  status text not null default 'queued',
  attempts integer not null default 0,
  provider_message_id text not null default '',
  error_code text not null default '',
  error text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  sent_at timestamptz,
  constraint uq_notification_delivery_channel unique (recommendation_id, channel),
  constraint notification_deliveries_recommendation_owner_fkey
    foreign key (recommendation_id, user_id)
    references public.job_recommendations(id, user_id) on delete cascade
);

create table if not exists public.job_requirement_revisions (
  id bigint generated by default as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id bigint not null,
  original_requirements_json text not null default '{}'
    constraint job_requirement_revisions_original_requirements_json_check
    check (jsonb_typeof(original_requirements_json::jsonb) = 'object'),
  corrected_requirements_json text not null default '{}'
    constraint job_requirement_revisions_corrected_requirements_json_check
    check (jsonb_typeof(corrected_requirements_json::jsonb) = 'object'),
  changed_fields_json text not null default '[]'
    constraint job_requirement_revisions_changed_fields_json_check
    check (jsonb_typeof(changed_fields_json::jsonb) = 'array'),
  matcher_version text not null default '',
  created_at timestamptz not null default now(),
  constraint job_requirement_revisions_job_owner_fkey
    foreign key (job_id, user_id)
    references public.jobs(id, user_id) on delete cascade
);

create table if not exists public.job_scans (
  id bigint generated by default as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  input_hash text not null default '',
  payload_json text not null default '{}'
    constraint job_scans_payload_json_check
    check (jsonb_typeof(payload_json::jsonb) = 'object'),
  status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled')),
  current_step text not null default 'queued',
  progress integer not null default 0 check (progress between 0 and 100),
  result_job_id bigint,
  trace_id text not null default '',
  attempts integer not null default 0,
  lease_token text not null default '',
  error_code text not null default '',
  error_message text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  constraint job_scans_result_job_owner_fkey
    foreign key (result_job_id, user_id)
    references public.jobs(id, user_id) on delete set null (result_job_id)
);

create table if not exists public.extraction_metrics (
  id bigint generated by default as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  workflow_type text not null,
  subject_type text not null default '',
  subject_id bigint,
  strategy text not null default '',
  status text not null default 'succeeded',
  duration_ms integer not null default 0,
  input_length integer not null default 0,
  output_length integer not null default 0,
  fallback_reason text not null default '',
  counts_json text not null default '{}'
    constraint extraction_metrics_counts_json_check
    check (jsonb_typeof(counts_json::jsonb) = 'object'),
  error_code text not null default '',
  trace_id text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.evaluation_examples (
  id bigint generated by default as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  example_type text not null,
  subject_id bigint,
  split text not null default 'train' check (split in ('train', 'validation', 'test')),
  label text not null,
  features_json text not null default '{}'
    constraint evaluation_examples_features_json_check
    check (jsonb_typeof(features_json::jsonb) = 'object'),
  model_version text not null default '',
  trace_id text not null default '',
  created_at timestamptz not null default now()
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
create index if not exists profile_interests_interest_profile_idx on public.profile_interests (interest, profile_id);
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
create index if not exists job_status_events_user_match_occurred_idx on public.job_status_events (user_id, match_id, occurred_at, created_at, id);
create index if not exists job_status_events_user_match_audit_idx on public.job_status_events (user_id, match_id, id);
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
create index if not exists shared_job_catalog_domain_updated_idx on public.shared_job_catalog (domain, updated_at desc) where active = true;
create index if not exists shared_job_catalog_first_seen_idx on public.shared_job_catalog (first_seen_by, created_at desc);
create unique index if not exists shared_job_catalog_source_external_uq on public.shared_job_catalog (source_name, external_id) where external_id <> '';
create index if not exists shared_job_catalog_source_seen_idx on public.shared_job_catalog (source_name, last_seen_at desc);
create index if not exists recommendation_runs_status_created_idx on public.recommendation_runs (status, created_at);
create index if not exists recommendation_runs_catalog_idx on public.recommendation_runs (catalog_job_id, created_at desc);
create index if not exists recommendation_runs_source_user_idx on public.recommendation_runs (source_user_id, created_at desc);
create index if not exists job_recommendations_user_status_score_idx on public.job_recommendations (user_id, status, score desc);
create index if not exists job_recommendations_catalog_idx on public.job_recommendations (catalog_job_id);
create index if not exists job_recommendations_materialized_job_idx on public.job_recommendations (materialized_job_id) where materialized_job_id is not null;
create index if not exists recommendation_events_recommendation_idx on public.recommendation_events (recommendation_id);
create index if not exists recommendation_events_catalog_idx on public.recommendation_events (catalog_job_id);
create index if not exists recommendation_events_materialized_job_idx on public.recommendation_events (materialized_job_id) where materialized_job_id is not null;
create index if not exists recommendation_events_user_created_idx on public.recommendation_events (user_id, created_at desc);
create index if not exists recommendation_events_field_type_created_idx on public.recommendation_events (career_field, event_type, created_at desc);
create index if not exists recommendation_events_band_type_idx on public.recommendation_events (score_band, event_type);
create index if not exists job_source_runs_source_created_idx on public.job_source_runs (source_name, created_at desc);
create index if not exists job_discovery_beta_market_active_idx on public.job_discovery_beta_members (market_code, active);
create index if not exists job_notification_preferences_email_idx on public.job_notification_preferences (email_enabled, updated_at desc) where email_enabled = true;
create index if not exists notification_deliveries_queue_idx on public.notification_deliveries (status, created_at) where status in ('queued', 'failed');
create index if not exists notification_deliveries_user_created_idx on public.notification_deliveries (user_id, created_at desc);
create index if not exists profiles_recommendations_ready_idx on public.profiles (recommendations_enabled, status, updated_at desc) where recommendations_enabled = true and onboarding_completed = true;
create index if not exists job_requirement_revisions_job_created_idx on public.job_requirement_revisions (job_id, created_at desc);
create index if not exists job_requirement_revisions_user_idx on public.job_requirement_revisions (user_id);
create index if not exists job_scans_user_created_idx on public.job_scans (user_id, created_at desc);
create index if not exists job_scans_queue_idx on public.job_scans (status, created_at) where status in ('queued', 'cancel_requested');
create index if not exists job_scans_result_job_idx on public.job_scans (result_job_id) where result_job_id is not null;
create unique index if not exists job_scans_user_active_input_uq on public.job_scans (user_id, input_hash) where status in ('queued', 'running', 'cancel_requested');
create index if not exists job_scans_recovery_idx on public.job_scans (status, updated_at, created_at) where status in ('queued', 'running', 'cancel_requested');
create index if not exists extraction_metrics_workflow_created_idx on public.extraction_metrics (workflow_type, status, created_at desc);
create index if not exists extraction_metrics_trace_idx on public.extraction_metrics (trace_id) where trace_id <> '';
create index if not exists extraction_metrics_user_idx on public.extraction_metrics (user_id);
create index if not exists evaluation_examples_type_split_idx on public.evaluation_examples (example_type, split, created_at desc);
create index if not exists evaluation_examples_user_idx on public.evaluation_examples (user_id);

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
alter table public.shared_job_catalog enable row level security;
alter table public.recommendation_runs enable row level security;
alter table public.job_recommendations enable row level security;
alter table public.recommendation_events enable row level security;
alter table public.recommendation_field_calibrations enable row level security;
alter table public.job_source_runs enable row level security;
alter table public.job_discovery_beta_members enable row level security;
alter table public.job_notification_preferences enable row level security;
alter table public.notification_deliveries enable row level security;
alter table public.job_requirement_revisions enable row level security;
alter table public.job_scans enable row level security;
alter table public.extraction_metrics enable row level security;
alter table public.evaluation_examples enable row level security;
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

-- Browser clients authenticate with Supabase, but all application mutations
-- pass through the backend. Keep owner reads available to server-rendered auth
-- checks while preventing forged derived data through PostgREST.
revoke insert, update, delete, truncate, references, trigger
  on all tables in schema public from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke insert, update, delete, truncate, references, trigger
  on tables from anon, authenticated;

create policy profiles_owner_select on public.profiles
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy profile_interests_owner_select on public.profile_interests
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy profile_sources_owner_select on public.profile_sources
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy profile_facts_owner_select on public.profile_facts
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy profile_fact_feedback_owner_select on public.profile_fact_feedback
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy clarification_questions_owner_select on public.clarification_questions
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy jobs_owner_select on public.jobs
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy job_matches_owner_select on public.job_matches
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy resume_advice_owner_select on public.resume_advice
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy job_status_events_owner_select on public.job_status_events
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy agent_runs_owner_select on public.agent_runs
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy agent_steps_owner_select on public.agent_steps
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy shared_job_catalog_client_deny on public.shared_job_catalog
  for all to anon, authenticated using (false) with check (false);

create policy recommendation_runs_client_deny on public.recommendation_runs
  for all to anon, authenticated using (false) with check (false);

create policy job_recommendations_owner_select on public.job_recommendations
  for select to authenticated using ((select auth.uid()) = user_id);

create policy recommendation_events_owner_select on public.recommendation_events
  for select to authenticated using ((select auth.uid()) = user_id);

create policy recommendation_field_calibrations_client_deny on public.recommendation_field_calibrations
  for all to anon, authenticated using (false) with check (false);

create policy job_source_runs_client_deny on public.job_source_runs
  for all to anon, authenticated using (false) with check (false);

create policy job_discovery_beta_owner_select on public.job_discovery_beta_members
  for select to authenticated using ((select auth.uid()) = user_id);

create policy job_notification_preferences_owner_select on public.job_notification_preferences
  for select to authenticated using ((select auth.uid()) = user_id);

create policy notification_deliveries_client_deny on public.notification_deliveries
  for all to anon, authenticated using (false) with check (false);

create policy job_requirement_revisions_owner_select on public.job_requirement_revisions
  for select to authenticated using ((select auth.uid()) = user_id);

create policy job_scans_owner_select on public.job_scans
  for select to authenticated using ((select auth.uid()) = user_id);

-- These rows contain only privacy-safe features, but remain backend-only so
-- product telemetry cannot become a second user-facing profile store.
create policy extraction_metrics_client_deny on public.extraction_metrics
  for all to anon, authenticated using (false) with check (false);

create policy evaluation_examples_client_deny on public.evaluation_examples
  for all to anon, authenticated using (false) with check (false);

-- Storage policy for private profile documents.
-- Create the bucket in Storage as private before running this section if needed.
insert into storage.buckets (id, name, public)
values ('profile-documents', 'profile-documents', false)
on conflict (id) do nothing;

-- The API uses a Supabase secret/service credential and is the only supported
-- document boundary. Browser sessions may not bypass its validation or
-- lifecycle controls with direct Storage calls.
revoke select, insert, update, delete, truncate, references, trigger
  on storage.objects from anon, authenticated;
