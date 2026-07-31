# Database migration order

`supabase/schema.sql` is the current fresh-install snapshot. It includes the
database contract through v22 and must not be rerun over an existing database.

The historical migrations predate the current timestamp naming convention.
Several have the same date prefix, so lexicographic filename order is **not**
release order. Do not rename a migration after it has been applied; migration
identity must remain stable for deployed environments.

For a legacy database, apply only migrations that its deployment log has not
already recorded, in this release order:

1. `20260702_no_openai_fit_v2.sql`
2. `20260702_profile_fact_reconciliation_v3.sql`
3. `20260702_manual_profile_facts_v4.sql`
4. `20260704_onboarding_interests_v5.sql`
5. `20260705_performance_v6.sql`
6. `20260709_job_summary_performance_v7.sql`
7. `20260709_agent_workflows_v8.sql`
8. `20260711_security_and_rate_limits_v9.sql`
9. `20260711_private_rate_limits_v10.sql`
10. `20260712_shadow_recommendations_v11.sql`
11. `20260712_recommendation_run_source_index_v12.sql`
12. `20260712_shadow_observation_status_v13.sql`
13. `20260713_product_intelligence_v14.sql`
14. `20260713_product_intelligence_indexes_v15.sql`
15. `20260721_goozali_discovery_v16.sql`
16. `20260725160309_recommendation_feedback_v17.sql`
17. `20260730153000_clarification_question_status_v18.sql`
18. `20260730170000_tenant_integrity_and_browser_privileges_v19.sql`
19. `20260730190000_job_scan_claims_v20.sql`
20. `20260730210000_backend_mediated_storage_v21.sql`
21. `20260730220000_data_contract_constraints_v22.sql`

All new migrations use a unique 14-digit UTC timestamp, are forward-only, and
must update `supabase/schema.sql` in the same change. Production deployment
automation should record each applied filename instead of deriving state from
the directory listing.
