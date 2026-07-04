-- First-use onboarding and normalized career interests.

alter table public.profiles
  add column if not exists onboarding_completed boolean not null default false;

-- Existing beta profiles have already completed the equivalent setup flow.
update public.profiles
set onboarding_completed = true
where onboarding_completed = false;

create index if not exists profiles_user_onboarding_idx
  on public.profiles (user_id, onboarding_completed);

create table if not exists public.profile_interests (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  profile_id bigint not null references public.profiles(id) on delete cascade,
  interest text not null,
  created_at timestamptz not null default now(),
  constraint profile_interests_profile_interest_unique unique (profile_id, interest)
);

create index if not exists profile_interests_user_interest_idx
  on public.profile_interests (user_id, interest);

alter table public.profile_interests enable row level security;

drop policy if exists profile_interests_owner_all on public.profile_interests;
create policy profile_interests_owner_all on public.profile_interests
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
