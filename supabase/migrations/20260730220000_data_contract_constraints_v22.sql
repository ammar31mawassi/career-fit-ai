-- v22: Reject malformed or structurally incompatible durable JSON payloads and
-- constrain the workflow states consumed by the application.
--
-- These validated constraints intentionally fail deployment if historical rows
-- contain invalid JSON or an unknown workflow state. Run the documented
-- preflight first and repair/quarantine incompatible rows rather than silently
-- carrying them into the new contract.

alter table public.profile_sources
  add constraint profile_sources_metadata_json_check
  check (jsonb_typeof(metadata_json::jsonb) = 'object');

alter table public.profile_facts
  add constraint profile_facts_metadata_json_check
  check (jsonb_typeof(metadata_json::jsonb) = 'object'),
  add constraint profile_facts_source_ids_json_check
  check (jsonb_typeof(source_ids_json::jsonb) = 'array');

alter table public.profile_fact_feedback
  add constraint profile_fact_feedback_source_ids_json_check
  check (jsonb_typeof(source_ids_json::jsonb) = 'array');

alter table public.jobs
  add constraint jobs_requirements_json_check
  check (jsonb_typeof(requirements_json::jsonb) = 'object');

alter table public.job_matches
  add constraint job_matches_matched_evidence_json_check
  check (jsonb_typeof(matched_evidence_json::jsonb) = 'array'),
  add constraint job_matches_missing_blockers_json_check
  check (jsonb_typeof(missing_blockers_json::jsonb) = 'array'),
  add constraint job_matches_gaps_json_check
  check (jsonb_typeof(gaps_json::jsonb) = 'array'),
  add constraint job_matches_component_scores_json_check
  check (jsonb_typeof(component_scores_json::jsonb) = 'object'),
  add constraint job_matches_applied_caps_json_check
  check (jsonb_typeof(applied_caps_json::jsonb) = 'array'),
  add constraint job_matches_feature_snapshot_json_check
  check (jsonb_typeof(feature_snapshot_json::jsonb) = 'object');

alter table public.resume_advice
  add constraint resume_advice_projects_json_check
  check (jsonb_typeof(projects_json::jsonb) = 'array'),
  add constraint resume_advice_skill_order_json_check
  check (jsonb_typeof(skill_order_json::jsonb) = 'array'),
  add constraint resume_advice_evidence_json_check
  check (jsonb_typeof(evidence_json::jsonb) = 'array');

alter table public.agent_runs
  add constraint agent_runs_status_check
  check (status in ('running', 'completed', 'failed', 'reused'));

alter table public.agent_steps
  add constraint agent_steps_status_check
  check (status in ('running', 'completed', 'failed')),
  add constraint agent_steps_attempt_check
  check (attempt >= 1),
  add constraint agent_steps_output_json_check
  check (jsonb_typeof(output_json::jsonb) = 'object');

alter table public.shared_job_catalog
  add constraint shared_job_catalog_requirements_json_check
  check (jsonb_typeof(requirements_json::jsonb) = 'object'),
  add constraint shared_job_catalog_career_fields_json_check
  check (jsonb_typeof(career_fields_json::jsonb) = 'array');

alter table public.job_recommendations
  add constraint job_recommendations_career_fields_json_check
  check (jsonb_typeof(career_fields_json::jsonb) = 'array'),
  add constraint job_recommendations_reasons_json_check
  check (jsonb_typeof(reasons_json::jsonb) = 'array'),
  add constraint job_recommendations_match_snapshot_json_check
  check (jsonb_typeof(match_snapshot_json::jsonb) = 'object');

alter table public.job_requirement_revisions
  add constraint job_requirement_revisions_original_requirements_json_check
  check (jsonb_typeof(original_requirements_json::jsonb) = 'object'),
  add constraint job_requirement_revisions_corrected_requirements_json_check
  check (jsonb_typeof(corrected_requirements_json::jsonb) = 'object'),
  add constraint job_requirement_revisions_changed_fields_json_check
  check (jsonb_typeof(changed_fields_json::jsonb) = 'array');

alter table public.job_scans
  add constraint job_scans_payload_json_check
  check (jsonb_typeof(payload_json::jsonb) = 'object');

alter table public.extraction_metrics
  add constraint extraction_metrics_counts_json_check
  check (jsonb_typeof(counts_json::jsonb) = 'object');

alter table public.evaluation_examples
  add constraint evaluation_examples_features_json_check
  check (jsonb_typeof(features_json::jsonb) = 'object');
