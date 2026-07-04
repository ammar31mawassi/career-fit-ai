-- Record user-created profile facts in the feedback dataset.
alter table public.profile_fact_feedback
  drop constraint if exists profile_fact_feedback_action_check;

alter table public.profile_fact_feedback
  add constraint profile_fact_feedback_action_check
  check (action in ('pending', 'approved', 'rejected', 'edited_and_approved', 'manually_added'));
