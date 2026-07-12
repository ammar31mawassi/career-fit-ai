create index if not exists recommendation_runs_source_user_idx
  on public.recommendation_runs (source_user_id, created_at desc);
