-- Profile documents are accepted, parsed, and deleted only through the backend.
-- Browser roles must not bypass the application's size, type, quota, lifecycle,
-- and account-deletion controls by calling Supabase Storage directly.

begin;

drop policy if exists profile_documents_owner_select on storage.objects;
drop policy if exists profile_documents_owner_insert on storage.objects;
drop policy if exists profile_documents_owner_update on storage.objects;
drop policy if exists profile_documents_owner_delete on storage.objects;

revoke select, insert, update, delete, truncate, references, trigger
  on storage.objects from anon, authenticated;

commit;
