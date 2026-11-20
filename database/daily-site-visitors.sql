-- Public, approximate daily unique-browser statistics. No existing user/listing
-- table is read or changed. A random browser UUID is hashed with its Baku date;
-- the raw UUID, IP address, user agent and account identity are never stored.
-- Old receipt hashes are deleted in batches on subsequent record requests;
-- this is activity-driven cleanup, not a promise of wall-clock expiry.
create schema if not exists ca_private;
grant usage on schema ca_private to anon,authenticated;

create table if not exists ca_private.site_visit_totals(
 day date primary key,
 visitors bigint not null default 0 check(visitors between 0 and 9007199254740991)
);
create table if not exists ca_private.site_visit_receipts(
 day date not null,
 visitor_hash text not null check(visitor_hash ~ '^[0-9a-f]{64}$'),
 primary key(day,visitor_hash)
);
alter table ca_private.site_visit_totals enable row level security;
alter table ca_private.site_visit_receipts enable row level security;
revoke all on ca_private.site_visit_totals,ca_private.site_visit_receipts from public,anon,authenticated;

-- Calendar conversion is an internal helper, not a caller-selectable API date.
create or replace function ca_private.site_visit_day(p_now timestamptz)
returns date language sql immutable strict security invoker set search_path='' as $$
 select (p_now at time zone 'Asia/Baku')::date;
$$;
revoke all on function ca_private.site_visit_day(timestamptz) from public,anon,authenticated;

-- The private write proxy is intentionally anonymous: its only authority is
-- adding one receipt/count for today's browser identity. Direct table access,
-- historical reads, arbitrary count values and reset operations are not APIs.
create or replace function ca_private.api_record_site_visit(p_visitor uuid)
returns jsonb language plpgsql volatile security definer set search_path='' as $$
declare
 d date:=ca_private.site_visit_day(statement_timestamp());
 h text;
 changed integer;
 total bigint;
begin
 if p_visitor is null or p_visitor='00000000-0000-0000-0000-000000000000'::uuid then
  raise exception 'Ziyarətçi identifikatoru düzgün deyil.' using errcode='22023';
 end if;
 h:=encode(sha256(convert_to('avtounvan-site-v1:'||d::text||':'||p_visitor::text,'UTF8')),'hex');
 -- The primary key gates concurrent retries, including calls across login.
 insert into ca_private.site_visit_receipts(day,visitor_hash)
 values(d,h) on conflict do nothing;
 get diagnostics changed=row_count;
 if changed=1 then
  insert into ca_private.site_visit_totals(day,visitors) values(d,1)
  on conflict(day) do update set visitors=ca_private.site_visit_totals.visitors+1
  returning visitors into total;
 else
  select s.visitors into total from ca_private.site_visit_totals s where s.day=d;
 end if;
 -- PK(day,hash) also indexes this bounded cleanup. Keep today and the previous
 -- two Baku calendar dates; with no traffic, old hashes may remain longer.
 delete from ca_private.site_visit_receipts r where r.ctid in(
  select old.ctid from ca_private.site_visit_receipts old
  where old.day<d-2 order by old.day,old.visitor_hash limit 100 for update skip locked
 );
 return jsonb_build_object('day',d,'timezone','Asia/Baku',
  'visitors',coalesce(total,0),'counted',changed=1);
end $$;

create or replace function ca_private.api_daily_site_visitors()
returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('day',d.day,'timezone','Asia/Baku',
  'visitors',coalesce((select s.visitors from ca_private.site_visit_totals s where s.day=d.day),0))
 from (select ca_private.site_visit_day(statement_timestamp()) as day) d;
$$;
revoke all on function ca_private.api_record_site_visit(uuid),ca_private.api_daily_site_visitors() from public,anon,authenticated;
grant execute on function ca_private.api_record_site_visit(uuid),ca_private.api_daily_site_visitors() to anon,authenticated;

create or replace function public.ca_record_site_visit(p_visitor uuid)
returns jsonb language sql volatile security invoker set search_path='' as $$
 select ca_private.api_record_site_visit(p_visitor);
$$;
create or replace function public.ca_daily_site_visitors()
returns jsonb language sql stable security invoker set search_path='' as $$
 select ca_private.api_daily_site_visitors();
$$;
revoke all on function public.ca_record_site_visit(uuid),public.ca_daily_site_visitors() from public,anon,authenticated;
grant execute on function public.ca_record_site_visit(uuid),public.ca_daily_site_visitors() to anon,authenticated;
notify pgrst,'reload schema';
