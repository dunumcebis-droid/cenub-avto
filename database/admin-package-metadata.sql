-- Admin-only package feedback. Read metadata without approving any listing or
-- payment, modifying packages/dates/photos, or changing the public browse API.
-- Existing role checks, RLS, RPC signatures and private-table grants remain.
create or replace function public.ca_admin_browse_listings(
  p_status text default 'all',p_query text default '',
  p_page integer default 1,p_page_size integer default 24)
returns jsonb language plpgsql stable security invoker set search_path = ''
as $fn$
declare v_size integer:=least(48,greatest(1,coalesce(p_page_size,24))); v_result jsonb;
begin
  if auth.uid() is null or not public.cenub_admin_yoxla() then
    raise exception 'Admin icazesi yoxdur' using errcode='42501';
  end if;
  if coalesce(p_status,'all') not in ('all','gozlemede','aktiv','reddedildi') then
    raise exception 'Yanlis status' using errcode='22023';
  end if;
  with source as materialized (select * from public.ca_admin_list()),
  matched as materialized (
    select s.* from source s
    where (coalesce(p_status,'all')='all' or s.veziyyet=p_status)
      and strpos(translate(lower(translate(concat_ws(' ',s.marka,s.model,s.seher),'İ','I')),'ı','i'),
        translate(lower(translate(btrim(coalesce(p_query,'')),'İ','I')),'ı','i'))>0
  ), totals as (select count(*) n from matched),
  paging as (select n,greatest(1,least(greatest(1,coalesce(p_page,1)),greatest(1,(n+v_size-1)/v_size))) page from totals),
  paged as (select m.* from matched m order by m.yaradildi desc,m.id desc
    limit v_size offset (select (page-1)*v_size from paging)),
  requests as materialized (
    -- Choose the latest request across every payment status, matching the
    -- activation RPC. An older pending request must not replace newer history.
    select distinct on (r.elan_id)
      r.elan_id,r.id,r.paket_adi,r.odenis_veziyyeti
    from public.ca_admin_paket_sorgulari() r join paged p on p.id=r.elan_id
    order by r.elan_id,r.yaradilib desc,r.id desc
  ), enriched as (
    select p.*,
      coalesce(r.paket_adi,l.requested,
        case when e.paket_adi in ('VIP','Premium','Standart') then e.paket_adi end,
        'Pulsuz') as requested_package,
      case when r.id is not null then case r.odenis_veziyyeti
        when 'gozlemede' then 'pending'
        when 'tesdiqlendi' then 'confirmed'
        when 'reddedildi' then 'rejected'
        else 'legacy_unrequested' end
      when l.requested is not null or e.paket_adi in ('VIP','Premium','Standart')
        then 'legacy_unrequested'
      else 'free' end as package_status,
      r.id as package_request_id,
      case when e.paket_adi in ('VIP','Premium','Standart')
        then e.paket_adi else 'Pulsuz' end as approved_package
    from paged p join public.elanlar e on e.id=p.id
    left join requests r on r.elan_id=p.id
    cross join lateral (
      select case
        when jsonb_typeof(e.ca_data)='object' then e.ca_data
        when jsonb_typeof(e.ca_data)='string'
          and pg_input_is_valid(e.ca_data#>>'{}','jsonb') then
          case when jsonb_typeof((e.ca_data#>>'{}')::jsonb)='object'
            then (e.ca_data#>>'{}')::jsonb else '{}'::jsonb end
        else '{}'::jsonb end as data
    ) d
    cross join lateral (
      -- A seller's old label is intent only. It never signifies a payment or
      -- changes the authoritative package, and ca_data.pack is never trusted.
      select case
        when d.data->>'requestedPackage' like '%15 AZN%'
          or upper(btrim(d.data->>'requestedPackage'))='VIP' then 'VIP'
        when d.data->>'requestedPackage' like '%5 AZN%'
          or upper(btrim(d.data->>'requestedPackage'))='PREMIUM' then 'Premium'
        when d.data->>'requestedPackage' like '%3 AZN%'
          or upper(btrim(d.data->>'requestedPackage'))='STANDART' then 'Standart'
        else null end as requested
    ) l
  )
  select jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(p) order by p.yaradildi desc,p.id desc) from enriched p),'[]'::jsonb),
    'total',n,'pending_total',(select count(*) from source where veziyyet='gozlemede'),
    'page',page,'page_size',v_size,'total_pages',(n+v_size-1)/v_size)
    into v_result from paging;
  return v_result;
end;
$fn$;
revoke all on function public.ca_admin_browse_listings(text,text,integer,integer) from public,anon;
grant execute on function public.ca_admin_browse_listings(text,text,integer,integer) to authenticated;

-- Search also accepts the exact request/listing UUID for a card-to-payment
-- jump, without adding an overloaded signature or exposing private tables.
create or replace function public.ca_admin_browse_payments(
  p_status text default 'all',p_query text default '',
  p_page integer default 1,p_page_size integer default 24)
returns jsonb language plpgsql stable security invoker set search_path = ''
as $fn$
declare v_size integer:=least(48,greatest(1,coalesce(p_page_size,24))); v_result jsonb;
begin
  if auth.uid() is null or not public.cenub_admin_yoxla() then
    raise exception 'Admin icazesi yoxdur' using errcode='42501';
  end if;
  if coalesce(p_status,'all') not in ('all','gozlemede','tesdiqlendi','reddedildi') then
    raise exception 'Yanlis status' using errcode='22023';
  end if;
  with source as materialized (select * from public.ca_admin_paket_sorgulari()),
  search as (
    select lower(btrim(coalesce(p_query,''))) as uuid_query,
      exists(select 1 from source r where r.id::text=lower(btrim(coalesce(p_query,'')))) as exact_request,
      exists(select 1 from source r where r.elan_id::text=lower(btrim(coalesce(p_query,'')))) as exact_listing
  ),
  matched as materialized (
    select s.* from source s cross join search q
    where (coalesce(p_status,'all')='all' or s.odenis_veziyyeti=p_status)
      -- A full request UUID takes priority over an equal UUID used by another
      -- listing, keeping a card jump pinned to its one linked request.
      and case when q.exact_request then s.id::text=q.uuid_query
        when q.exact_listing then s.elan_id::text=q.uuid_query
        else strpos(translate(lower(translate(concat_ws(' ',s.marka,s.model,s.paket_adi,s.id::text,s.elan_id::text),'İ','I')),'ı','i'),
          translate(lower(translate(btrim(coalesce(p_query,'')),'İ','I')),'ı','i'))>0 end
  ), totals as (select count(*) n from matched),
  paging as (select n,greatest(1,least(greatest(1,coalesce(p_page,1)),greatest(1,(n+v_size-1)/v_size))) page from totals),
  paged as (select m.* from matched m order by m.yaradilib desc,m.id desc
    limit v_size offset (select (page-1)*v_size from paging))
  select jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(p) order by p.yaradilib desc,p.id desc) from paged p),'[]'::jsonb),
    'total',n,'pending_total',(select count(*) from source where odenis_veziyyeti='gozlemede'),
    'page',page,'page_size',v_size,'total_pages',(n+v_size-1)/v_size)
    into v_result from paging;
  return v_result;
end;
$fn$;
revoke all on function public.ca_admin_browse_payments(text,text,integer,integer) from public,anon;
grant execute on function public.ca_admin_browse_payments(text,text,integer,integer) to authenticated;

notify pgrst,'reload schema';
