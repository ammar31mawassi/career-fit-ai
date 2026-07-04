-- Provenance-aware profile facts and user feedback dataset.

alter table public.profile_facts
  add column if not exists source_ids_json text not null default '[]',
  add column if not exists support_count integer not null default 1 check (support_count >= 1),
  add column if not exists extraction_key text not null default '',
  add column if not exists review_status text not null default 'pending',
  add column if not exists reviewed_at timestamptz;

update public.profile_facts
set review_status = case when user_approved then 'approved' else 'pending' end
where review_status not in ('approved', 'rejected') or review_status is null;

alter table public.profile_facts drop constraint if exists profile_facts_review_status_check;
alter table public.profile_facts
  add constraint profile_facts_review_status_check
  check (review_status in ('pending', 'approved', 'rejected'));

create index if not exists profile_facts_user_profile_review_idx
  on public.profile_facts (user_id, profile_id, review_status);
create index if not exists profile_facts_profile_extraction_key_idx
  on public.profile_facts (profile_id, extraction_key);

create table if not exists public.profile_fact_feedback (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null references public.profiles(id) on delete cascade,
  fact_id bigint references public.profile_facts(id) on delete set null,
  fact_type text not null,
  extraction_key text not null default '',
  action text not null check (action in ('pending', 'approved', 'rejected', 'edited_and_approved')),
  original_value text not null default '',
  corrected_value text not null default '',
  source_ids_json text not null default '[]',
  extractor_version text not null default '',
  created_at timestamptz not null default now()
);

create index if not exists profile_fact_feedback_user_created_idx
  on public.profile_fact_feedback (user_id, created_at desc);
create index if not exists profile_fact_feedback_profile_key_idx
  on public.profile_fact_feedback (profile_id, extraction_key);

alter table public.profile_fact_feedback enable row level security;

drop policy if exists profile_fact_feedback_owner_select on public.profile_fact_feedback;
create policy profile_fact_feedback_owner_select on public.profile_fact_feedback
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists profile_fact_feedback_owner_insert on public.profile_fact_feedback;
create policy profile_fact_feedback_owner_insert on public.profile_fact_feedback
  for insert to authenticated
  with check ((select auth.uid()) = user_id);
