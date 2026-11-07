-- Admin metadata paging. Existing authorization and RLS are preserved.
-- No listing, uploaded photo, payment, or package row is modified.
create or replace function public.ca_admin_list()
returns table(id uuid, marka text, model text, il integer, qiymet numeric,
  seher text, tesvir text, veziyyet text, yaradildi timestamptz)
language plpgsql stable security invoker set search_path = ''
as $fn$
begin
  if auth.uid() is null or not public.cenub_admin_yoxla() then
    raise exception 'Admin icazesi yoxdur' using errcode='42501';
  end if;
  return query select e.id,e.marka,e.model,e.il,e.qiymet,e.seher,e.tesvir,e.veziyyet,e.yaradildi
    from public.elanlar e where e.veziyyet <> 'silindi'
    order by e.yaradildi desc,e.id desc;
end;
$fn$;
revoke all on function public.ca_admin_list() from public,anon;
grant execute on function public.ca_admin_list() to authenticated;

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
    limit v_size offset (select (page-1)*v_size from paging))
  select jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(p) order by p.yaradildi desc,p.id desc) from paged p),'[]'::jsonb),
    'total',n,'pending_total',(select count(*) from source where veziyyet='gozlemede'),
    'page',page,'page_size',v_size,'total_pages',(n+v_size-1)/v_size)
    into v_result from paging;
  return v_result;
end;
$fn$;
revoke all on function public.ca_admin_browse_listings(text,text,integer,integer) from public,anon;
grant execute on function public.ca_admin_browse_listings(text,text,integer,integer) to authenticated;

-- The existing payment RPC already checks admin membership and returns all
-- rows inside PostgreSQL. Aggregate there, before the REST row-count limit.
-- This wrapper gains no table privileges and adds no SECURITY DEFINER code.
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
  matched as materialized (
    select s.* from source s
    where (coalesce(p_status,'all')='all' or s.odenis_veziyyeti=p_status)
      and strpos(translate(lower(translate(concat_ws(' ',s.marka,s.model,s.paket_adi),'İ','I')),'ı','i'),
        translate(lower(translate(btrim(coalesce(p_query,'')),'İ','I')),'ı','i'))>0
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
