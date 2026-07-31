from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "supabase" / "schema.sql"
MIGRATIONS_PATH = REPOSITORY_ROOT / "supabase" / "migrations"


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def _table_definition(schema: str, table_name: str) -> str:
    match = re.search(
        rf"create table if not exists public\.{re.escape(table_name)}\s*\((.*?)\n\);",
        schema,
        re.DOTALL,
    )
    assert match is not None, f"canonical schema is missing public.{table_name}"
    return match.group(1)


def test_clarification_status_contract_supports_onboarding_skip() -> None:
    schema = _sql(SCHEMA_PATH)
    clarification_questions = _table_definition(schema, "clarification_questions")
    status_constraint = re.search(
        r"clarification_questions_status_check\s+check\s*"
        r"\(\s*status\s+in\s*\((.*?)\)\s*\)",
        clarification_questions,
        re.DOTALL,
    )

    assert status_constraint is not None
    assert set(re.findall(r"'([^']+)'", status_constraint.group(1))) == {
        "open",
        "answered",
        "skipped",
    }

    migration = _sql(
        MIGRATIONS_PATH / "20260730153000_clarification_question_status_v18.sql"
    )
    assert "drop constraint if exists clarification_questions_status_check" in migration
    assert "check (status in ('open', 'answered', 'skipped'))" in migration


def test_fresh_schema_contains_recommendation_feedback_contract() -> None:
    schema = _sql(SCHEMA_PATH)
    job_recommendations = _table_definition(schema, "job_recommendations")
    recommendation_events = _table_definition(schema, "recommendation_events")
    field_calibrations = _table_definition(
        schema, "recommendation_field_calibrations"
    )

    assert re.search(r"(?m)^\s*materialized_job_id\s+bigint\s*,", job_recommendations)
    assert re.search(
        r"job_recommendations_materialized_job_owner_fkey\s+"
        r"foreign key\s*\(materialized_job_id,\s*user_id\)\s+"
        r"references public\.jobs\(id,\s*user_id\)\s+"
        r"on delete set null\s*\(materialized_job_id\)",
        job_recommendations,
    )
    for column in (
        "user_id",
        "recommendation_id",
        "catalog_job_id",
        "materialized_job_id",
        "event_type",
        "dismiss_reason",
        "score_band",
        "career_field",
        "source_name",
        "model_version",
    ):
        assert re.search(rf"(?m)^\s*{column}\s+", recommendation_events)

    for column in (
        "career_field",
        "minimum_score",
        "sample_size",
        "positive_count",
        "negative_count",
        "possible_sample_size",
        "possible_positive_count",
        "medium_sample_size",
        "medium_positive_count",
        "window_days",
    ):
        assert re.search(rf"(?m)^\s*{column}\s+", field_calibrations)

    assert (
        "alter table public.recommendation_events enable row level security" in schema
    )
    assert (
        "alter table public.recommendation_field_calibrations "
        "enable row level security" in schema
    )


def test_tenant_integrity_and_browser_write_contract_is_pinned() -> None:
    schema = _sql(SCHEMA_PATH)
    migration = _sql(
        MIGRATIONS_PATH
        / "20260730170000_tenant_integrity_and_browser_privileges_v19.sql"
    )
    owner_foreign_keys = {
        "profile_interests_profile_owner_fkey",
        "profile_sources_profile_owner_fkey",
        "profile_facts_profile_owner_fkey",
        "profile_facts_source_owner_fkey",
        "profile_fact_feedback_profile_owner_fkey",
        "profile_fact_feedback_fact_owner_fkey",
        "clarification_questions_profile_owner_fkey",
        "job_matches_job_owner_fkey",
        "resume_advice_match_owner_fkey",
        "job_status_events_match_owner_fkey",
        "agent_steps_run_owner_fkey",
        "job_recommendations_materialized_job_owner_fkey",
        "recommendation_events_recommendation_owner_fkey",
        "recommendation_events_materialized_job_owner_fkey",
        "notification_deliveries_recommendation_owner_fkey",
        "job_requirement_revisions_job_owner_fkey",
        "job_scans_result_job_owner_fkey",
    }

    for constraint_name in owner_foreign_keys:
        assert f"constraint {constraint_name}" in schema
        assert f"constraint {constraint_name}" in migration

    browser_write_revoke = (
        "revoke insert, update, delete, truncate, references, trigger "
        "on all tables in schema public from anon, authenticated"
    )
    assert re.sub(r"\s+", " ", browser_write_revoke) in re.sub(r"\s+", " ", schema)
    assert re.sub(r"\s+", " ", browser_write_revoke) in re.sub(
        r"\s+", " ", migration
    )

    for dangerous_policy in (
        "profiles_owner_all",
        "profile_facts_owner_all",
        "clarification_questions_owner_all",
        "jobs_owner_all",
        "job_matches_owner_all",
        "job_recommendations_owner_update",
        "job_notification_preferences_owner_update",
        "job_requirement_revisions_owner_all",
        "job_scans_owner_all",
    ):
        assert f"create policy {dangerous_policy}" not in schema


def test_job_scan_claim_and_active_input_contract_is_pinned() -> None:
    schema = _sql(SCHEMA_PATH)
    migration = _sql(
        MIGRATIONS_PATH / "20260730190000_job_scan_claims_v20.sql"
    )
    job_scans = _table_definition(schema, "job_scans")
    active_predicate = (
        "where status in ('queued', 'running', 'cancel_requested')"
    )

    assert re.search(
        r"(?m)^\s*lease_token\s+text\s+not null\s+default\s+''",
        job_scans,
    )
    assert (
        "create unique index if not exists job_scans_user_active_input_uq "
        "on public.job_scans (user_id, input_hash) "
        f"{active_predicate}"
    ) in re.sub(r"\s+", " ", schema)
    assert "add column if not exists lease_token text not null default ''" in re.sub(
        r"\s+", " ", migration
    )
    assert (
        "create unique index job_scans_user_active_input_uq "
        "on public.job_scans (user_id, input_hash) "
        f"{active_predicate}"
    ) in re.sub(r"\s+", " ", migration)


def test_profile_document_storage_is_backend_mediated() -> None:
    schema = _sql(SCHEMA_PATH)
    migration = _sql(
        MIGRATIONS_PATH / "20260730210000_backend_mediated_storage_v21.sql"
    )
    revoke = (
        "revoke select, insert, update, delete, truncate, references, trigger "
        "on storage.objects from anon, authenticated"
    )

    for sql in (schema, migration):
        normalized = re.sub(r"\s+", " ", sql)
        assert revoke in normalized
        for policy_name in (
            "profile_documents_owner_select",
            "profile_documents_owner_insert",
            "profile_documents_owner_update",
            "profile_documents_owner_delete",
        ):
            assert f"create policy {policy_name}" not in sql


def test_durable_json_shapes_and_workflow_states_are_constrained() -> None:
    schema = _sql(SCHEMA_PATH)
    migration = _sql(
        MIGRATIONS_PATH / "20260730220000_data_contract_constraints_v22.sql"
    )
    json_constraints = {
        "profile_sources_metadata_json_check": "object",
        "profile_facts_metadata_json_check": "object",
        "profile_facts_source_ids_json_check": "array",
        "profile_fact_feedback_source_ids_json_check": "array",
        "jobs_requirements_json_check": "object",
        "job_matches_matched_evidence_json_check": "array",
        "job_matches_missing_blockers_json_check": "array",
        "job_matches_gaps_json_check": "array",
        "job_matches_component_scores_json_check": "object",
        "job_matches_applied_caps_json_check": "array",
        "job_matches_feature_snapshot_json_check": "object",
        "resume_advice_projects_json_check": "array",
        "resume_advice_skill_order_json_check": "array",
        "resume_advice_evidence_json_check": "array",
        "agent_steps_output_json_check": "object",
        "shared_job_catalog_requirements_json_check": "object",
        "shared_job_catalog_career_fields_json_check": "array",
        "job_recommendations_career_fields_json_check": "array",
        "job_recommendations_reasons_json_check": "array",
        "job_recommendations_match_snapshot_json_check": "object",
        "job_requirement_revisions_original_requirements_json_check": "object",
        "job_requirement_revisions_corrected_requirements_json_check": "object",
        "job_requirement_revisions_changed_fields_json_check": "array",
        "job_scans_payload_json_check": "object",
        "extraction_metrics_counts_json_check": "object",
        "evaluation_examples_features_json_check": "object",
    }

    for constraint_name, expected_shape in json_constraints.items():
        for sql in (schema, migration):
            assert f"constraint {constraint_name}" in sql
            assert (
                f"= '{expected_shape}'" in sql[
                    sql.index(f"constraint {constraint_name}") :
                    sql.index(f"constraint {constraint_name}") + 250
                ]
            )

    for sql in (schema, migration):
        normalized = re.sub(r"\s+", " ", sql)
        assert (
            "constraint agent_runs_status_check "
            "check (status in ('running', 'completed', 'failed', 'reused'))"
            in normalized
        )
        assert (
            "constraint agent_steps_status_check "
            "check (status in ('running', 'completed', 'failed'))"
            in normalized
        )
        assert "constraint agent_steps_attempt_check check (attempt >= 1)" in normalized
