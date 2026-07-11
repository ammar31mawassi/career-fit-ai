-- CareerFit v10: keep rate-limit state outside the exposed public schema.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

alter table public.rate_limit_buckets set schema private;
revoke all on table private.rate_limit_buckets from public, anon, authenticated;

create or replace function public.consume_rate_limit(
  p_bucket_key text,
  p_limit integer,
  p_window_seconds integer
)
returns table (allowed boolean, remaining integer, retry_after integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_count integer;
  v_reset_at timestamptz;
  v_now timestamptz := clock_timestamp();
begin
  if p_bucket_key is null or length(p_bucket_key) < 8 or p_limit < 1 or p_window_seconds < 1 then
    raise exception 'invalid rate-limit arguments';
  end if;

  insert into private.rate_limit_buckets (bucket_key, request_count, reset_at, updated_at)
  values (p_bucket_key, 1, v_now + make_interval(secs => p_window_seconds), v_now)
  on conflict (bucket_key) do update
  set request_count = case
        when private.rate_limit_buckets.reset_at <= v_now then 1
        else private.rate_limit_buckets.request_count + 1
      end,
      reset_at = case
        when private.rate_limit_buckets.reset_at <= v_now
          then v_now + make_interval(secs => p_window_seconds)
        else private.rate_limit_buckets.reset_at
      end,
      updated_at = v_now
  returning request_count, reset_at into v_count, v_reset_at;

  allowed := v_count <= p_limit;
  remaining := greatest(0, p_limit - v_count);
  retry_after := case when allowed then 0 else greatest(1, ceil(extract(epoch from (v_reset_at - v_now)))::integer) end;
  return next;
end;
$$;

revoke execute on function public.consume_rate_limit(text, integer, integer) from public, anon, authenticated;
grant execute on function public.consume_rate_limit(text, integer, integer) to service_role;
