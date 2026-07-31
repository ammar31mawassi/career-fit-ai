-- Minimal Supabase-owned objects required to execute the application schema in
-- a stock PostgreSQL container. These are test doubles, not deployment SQL.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin bypassrls;
  end if;
end
$$;

create schema auth;
create table auth.users (
  id uuid primary key
);

create function auth.uid()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;

grant usage on schema auth to authenticated, service_role;
grant execute on function auth.uid() to authenticated, service_role;

create schema storage;
create table storage.buckets (
  id text primary key,
  name text not null,
  public boolean not null default false
);
create table storage.objects (
  id bigint generated always as identity primary key,
  bucket_id text not null references storage.buckets(id) on delete cascade,
  name text not null
);
alter table storage.objects enable row level security;

create function storage.foldername(object_name text)
returns text[]
language sql
immutable
as $$
  select string_to_array(trim(both '/' from object_name), '/')
$$;

grant usage on schema storage to authenticated, service_role;
grant select, insert, update, delete on storage.objects to authenticated, service_role;

-- The application schema only needs queue discovery and creation during
-- bootstrap. A stock postgres image does not ship Supabase's pgmq extension.
create schema pgmq;
create table pgmq.test_queues (
  queue_name text primary key
);

create function pgmq.list_queues()
returns table (queue_name text)
language sql
stable
as $$
  select test_queues.queue_name from pgmq.test_queues
$$;

create function pgmq.create(requested_queue text)
returns void
language sql
as $$
  insert into pgmq.test_queues (queue_name)
  values (requested_queue)
  on conflict (queue_name) do nothing
$$;

grant usage on schema public to anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  grant select, insert, update, delete, truncate, references, trigger
  on tables to anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  grant usage, select, update on sequences to anon, authenticated, service_role;
