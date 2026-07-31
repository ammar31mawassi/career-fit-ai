-- Keep the persisted clarification workflow aligned with the onboarding API.
-- The API intentionally retains skipped questions so analysis reruns do not
-- reopen a question the candidate already chose not to answer.

begin;

alter table public.clarification_questions
  drop constraint if exists clarification_questions_status_check;

alter table public.clarification_questions
  add constraint clarification_questions_status_check
  check (status in ('open', 'answered', 'skipped'));

commit;
