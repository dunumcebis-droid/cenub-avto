-- Match the displayed Azerbaijani package name as well as canonical Tecili.
-- Existing UUID priority, statuses, projection, ACLs and authorization remain.
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
        else strpos(translate(lower(translate(concat_ws(' ',s.marka,s.model,s.paket_adi,case when s.paket_adi='Tecili' then 'Təcili' end,s.id::text,s.elan_id::text),'İ','I')),'ı','i'),
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
notify pgrst,'reload schema';
