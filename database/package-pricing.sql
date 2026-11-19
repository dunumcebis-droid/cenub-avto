-- Current new-purchase terms: VIP 10 AZN / 15 days; Premium 5 AZN / 10 days.
-- Standart is legacy history only. Təcili remains 1 AZN until sold.
-- No listing, photo, request, explicit package date or historical row is updated.
CREATE OR REPLACE FUNCTION public.ca_paket_sorgusu_yarat(p_elan_id uuid, p_paket_adi text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_sorgu public.paket_sorgulari%rowtype;
  v_sorgu_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Giris teleb olunur' using errcode = '42501';
  end if;
  if p_paket_adi is null or p_paket_adi not in ('VIP', 'Premium', 'Standart', 'Tecili') then
    raise exception 'Yanlis paket' using errcode = '22023';
  end if;

  perform 1 from public.elanlar
    where id = p_elan_id
      and satici_id = (select auth.uid())
      and veziyyet = 'gozlemede' and not is_sold
    for update;
  if not found then
    raise exception 'Elan tapilmadi veya gozlemede deyil' using errcode = '42501';
  end if;

  select * into v_sorgu from public.paket_sorgulari
    where elan_id = p_elan_id and odenis_veziyyeti = 'gozlemede'
    order by yaradilib desc, id desc
    limit 1;
  if found then
    if v_sorgu.satici_id <> (select auth.uid())
       or v_sorgu.paket_adi <> p_paket_adi then
      raise exception 'Bu elan ucun ferqli paket sorgusu gozleyir'
        using errcode = '22023';
    end if;
    return v_sorgu.id;
  end if;

  -- Existing pending legacy requests remain retryable; no new Standart sale.
  if p_paket_adi = 'Standart' then
    raise exception 'Sərfəli paket artıq satılmır. Səhifəni yenilə və başqa paket seç.'
      using errcode = '22023';
  end if;

  insert into public.paket_sorgulari (elan_id, satici_id, paket_adi)
    values (p_elan_id, (select auth.uid()), p_paket_adi)
    returning id into v_sorgu_id;
  return v_sorgu_id;
end;
$function$;
create or replace function public.ca_elan_paket_sorgusu_avtomatik()
returns trigger language plpgsql security definer set search_path='' as $function$
declare v_label text;v_package text;v_legacy boolean:=false;
begin
 if new.veziyyet<>'gozlemede' or new.is_sold then return new;end if;
 v_label:=translate(upper(btrim(coalesce(new.ca_data->>'requestedPackage',''))),'Əİ','EI');
 -- Prices are exact labels, never substring matches (10 AZN is not 1 AZN).
 case
  when v_label in ('VIP','ÖNE ÇIXARILAN — 10 AZN / 15 GÜN') then v_package:='VIP';
  when v_label in ('PREMIUM','ÜSTÜN — 5 AZN / 10 GÜN') then v_package:='Premium';
  when v_label in ('ÜSTÜN — 5 AZN','ÜSTÜN — 5 AZN / 5 GÜN') then v_package:='Premium';v_legacy:=true;
  when v_label='TECILI' or v_label ~ '^TECILI[[:space:]]*[—-]?[[:space:]]*1[[:space:]]+AZN([[:space:]]*/[[:space:]]*SATILANADEK)?$' then v_package:='Tecili';
  when v_label='ÖNE ÇIXARILAN — 15 AZN / 15 GÜN' then v_package:='VIP';v_legacy:=true;
  when v_label in ('STANDART','SERFELI SEÇIM — 3 AZN','SERFELI — 3 AZN') then v_package:='Standart';v_legacy:=true;
  else return new;
 end case;
 if v_legacy then
  -- Keep genuine old payment/request history usable without another charge.
  if exists(select 1 from public.paket_sorgulari p where p.elan_id=new.id
      and p.satici_id=new.satici_id and p.paket_adi=v_package)
   or (tg_op='UPDATE' and old.paket_adi=v_package) then return new;end if;
  if v_package<>'Premium' then
   raise exception 'Paket qiymətləri yenilənib. Səhifəni yenilə və paketi yenidən seç.'
     using errcode='22023';
  end if;
 end if;
 perform public.ca_paket_sorgusu_yarat(new.id,v_package);
 return new;
end $function$;

CREATE OR REPLACE FUNCTION public.ca_admin_status(p_id uuid, p_status text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_elan public.elanlar%rowtype;
  v_paket text;
  v_odenis text;
  v_gun integer;
begin
  if auth.uid() is null or not public.cenub_admin_yoxla() then
    raise exception 'Admin icazesi yoxdur' using errcode = '42501';
  end if;
  if p_status is null or p_status not in ('gozlemede', 'aktiv', 'reddedildi') then
    raise exception 'Yanlis elan veziyyeti' using errcode = '22023';
  end if;

  select * into v_elan from public.elanlar where id = p_id for update;
  if not found or v_elan.veziyyet = 'silindi' or v_elan.is_sold then
    raise exception 'Elan tapilmadi veya silinib' using errcode = '22023';
  end if;

  if p_status = 'aktiv' and v_elan.veziyyet is distinct from 'aktiv' then
    select paket_adi, odenis_veziyyeti into v_paket, v_odenis
      from public.paket_sorgulari
      where elan_id = p_id
      order by yaradilib desc, id desc limit 1;
    if found then
      if v_odenis <> 'tesdiqlendi' then
        raise exception 'Odenis hele tesdiqlenmeyib' using errcode = '22023';
      end if;
      if v_elan.paket_adi is distinct from v_paket then
        raise exception 'Paket melumatlari uygun deyil' using errcode = '22023';
      end if;
      if v_paket = 'Tecili' then
        -- A confirmed urgent package lasts until the owner marks the car sold.
        -- Re-publication after an edit retains the original activation time.
        update public.elanlar set veziyyet='aktiv',
          paket_baslayir=coalesce(v_elan.paket_baslayir,statement_timestamp()),paket_bitir=null
          where id=p_id;
        return;
      end if;
      v_gun := case v_paket
        when 'VIP' then 15 when 'Premium' then 10 when 'Standart' then 3
        else null
      end;
      if v_gun is null then
        raise exception 'Yanlis paket' using errcode = '22023';
      end if;

      if v_elan.paket_baslayir is null and v_elan.paket_bitir is null then
        update public.elanlar
          set veziyyet = 'aktiv', paket_baslayir = statement_timestamp(),
            paket_bitir = statement_timestamp() + make_interval(days => v_gun)
          where id = p_id;
      elsif v_elan.paket_baslayir is null or v_elan.paket_bitir is null then
        raise exception 'Paket muddeti tam deyil' using errcode = '22023';
      else
        update public.elanlar set veziyyet = 'aktiv' where id = p_id;
      end if;
      return;
    end if;
    if v_elan.paket_adi in ('VIP', 'Premium', 'Standart', 'Tecili') then
      raise exception 'Tesdiqlenmis odenis tapilmadi' using errcode = '22023';
    end if;
  end if;

  update public.elanlar set veziyyet = p_status where id = p_id;
end;
$function$;
CREATE OR REPLACE FUNCTION public.ca_admin_browse_listings(p_status text DEFAULT 'all'::text, p_query text DEFAULT ''::text, p_page integer DEFAULT 1, p_page_size integer DEFAULT 24)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
AS $function$
declare v_size integer:=least(48,greatest(1,coalesce(p_page_size,24))); v_result jsonb;
begin
  if auth.uid() is null or not public.cenub_admin_yoxla() then
    raise exception 'Admin icazesi yoxdur' using errcode='42501';
  end if;
  if coalesce(p_status,'all') not in ('all','gozlemede','aktiv','reddedildi','satilib') then
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
        case when e.paket_adi in ('VIP','Premium','Standart','Tecili') then e.paket_adi end,
        'Pulsuz') as requested_package,
      case when r.id is not null then case r.odenis_veziyyeti
        when 'gozlemede' then 'pending'
        when 'tesdiqlendi' then 'confirmed'
        when 'reddedildi' then 'rejected'
        else 'legacy_unrequested' end
      when l.requested is not null or e.paket_adi in ('VIP','Premium','Standart','Tecili')
        then 'legacy_unrequested'
      else 'free' end as package_status,
      r.id as package_request_id,
      case when e.paket_adi in ('VIP','Premium','Standart','Tecili')
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
        when translate(upper(btrim(d.data->>'requestedPackage')),'Əİ','EI') in ('VIP','ÖNE ÇIXARILAN — 10 AZN / 15 GÜN','ÖNE ÇIXARILAN — 15 AZN / 15 GÜN') then 'VIP'
        when translate(upper(btrim(d.data->>'requestedPackage')),'Əİ','EI') in ('PREMIUM','ÜSTÜN — 5 AZN / 10 GÜN','ÜSTÜN — 5 AZN','ÜSTÜN — 5 AZN / 5 GÜN') then 'Premium'
        when translate(upper(btrim(d.data->>'requestedPackage')),'Əİ','EI') in ('STANDART','SERFELI SEÇIM — 3 AZN','SERFELI — 3 AZN') then 'Standart'
        when translate(upper(btrim(d.data->>'requestedPackage')),'Əİ','EI')='TECILI' or translate(upper(btrim(d.data->>'requestedPackage')),'Əİ','EI') ~ '^TECILI[[:space:]]*[—-]?[[:space:]]*1[[:space:]]+AZN([[:space:]]*/[[:space:]]*SATILANADEK)?$' then 'Tecili'
        else null end as requested
    ) l
  )
  select jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(p) order by p.yaradildi desc,p.id desc) from enriched p),'[]'::jsonb),
    'total',n,'pending_total',(select count(*) from source where veziyyet='gozlemede'),
    'page',page,'page_size',v_size,'total_pages',(n+v_size-1)/v_size)
    into v_result from paging;
  return v_result;
end;
$function$;

CREATE OR REPLACE FUNCTION public.ca_browse_listings(p_filters jsonb DEFAULT '{}'::jsonb, p_page integer DEFAULT 1, p_page_size integer DEFAULT 24)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
AS $function$
declare
  v_filters jsonb := coalesce(p_filters,'{}'::jsonb);
  v_page integer := greatest(1,coalesce(p_page,1));
  v_size integer := least(48,greatest(1,coalesce(p_page_size,24)));
  v_result jsonb;
begin
  if jsonb_typeof(v_filters) <> 'object' then
    raise exception 'Filters must be an object' using errcode='22023';
  end if;
  if v_filters?'saleType' and v_filters->'saleType'<>'null'::jsonb
   and (jsonb_typeof(v_filters->'saleType')<>'string' or coalesce(v_filters->>'saleType','') not in ('','cash','credit','barter')) then
    raise exception 'Satış şərti düzgün deyil.' using errcode='22023';
  end if;
  if v_filters?'urgent' and v_filters->'urgent'<>'null'::jsonb
   and jsonb_typeof(v_filters->'urgent')<>'boolean' then
    raise exception 'Təcili filtri düzgün deyil.' using errcode='22023';
  end if;
  with settings as (
    select coalesce(v_filters->>'make','') as make,
      coalesce(v_filters->>'model','') as model,
      coalesce(v_filters->>'city','') as city,
      coalesce(v_filters->>'vehicle','') as vehicle,
      coalesce(v_filters->>'state','') as state,
      coalesce(v_filters->>'body','') as body,
      coalesce(v_filters->>'color','') as color,
      coalesce(v_filters->>'market','') as market,
      coalesce(v_filters->>'seats','') as seats,
      coalesce(v_filters->>'pack','') as pack,
      coalesce(v_filters->>'sort','') as sort,
      coalesce(v_filters->>'saleType','') as sale_type,
      coalesce((v_filters->>'urgent')::boolean,false) as urgent,
      public.ca_listing_number(v_filters->'price') as price,
      public.ca_listing_number(v_filters->'priceMin') as pricemin,
      public.ca_listing_number(v_filters->'priceMax') as pricemax,
      public.ca_listing_number(v_filters->'yearMin') as yearmin,
      public.ca_listing_number(v_filters->'yearMax') as yearmax,
      public.ca_listing_number(v_filters->'kmMin') as kmmin,
      public.ca_listing_number(v_filters->'kmMax') as kmmax,
      public.ca_listing_number(v_filters->'engineMin') as enginemin,
      public.ca_listing_number(v_filters->'engineMax') as enginemax,
      public.ca_listing_number(v_filters->'hpMin') as hpmin,
      public.ca_listing_number(v_filters->'hpMax') as hpmax,
      array(select jsonb_array_elements_text(case when jsonb_typeof(v_filters->'equipment')='array' then v_filters->'equipment' else '[]'::jsonb end)) as equipment
  ), source as not materialized (
    select e.id, e.satici_id, e.marka, e.model, e.il, e.qiymet, e.yurus, e.seher, e.tesvir, e.veziyyet, e.yaradildi, e.neqliyyat_novu, e.nesil, e.ban_novu, e.yanacaq, e.suretler_qutusu, e.muherrik_hecmi, e.at_gucu, e.reng, e.bazar_ucun, e.oturacaq_sayi, e.techizat, e.sekiller, e.telefon, e.ca_data, e.paket_adi, e.paket_baslayir, e.paket_bitir, e.tesdiq_tarixi,
      coalesce(public.ca_listing_value(e.marka,d.data->>'make',d.data->>'marka',d.data->>'brand'),'') as _make,
      coalesce(public.ca_listing_value(e.model,d.data->>'model',d.data->>'modelName'),'') as _model,
      coalesce(public.ca_listing_value(e.seher,d.data->>'city',d.data->>'seher'),'') as _city,
      coalesce(public.ca_listing_value(e.neqliyyat_novu,d.data->>'vehicleType',d.data->>'vehicle',d.data->>'neqliyyat_novu'),'') as _vehicle,
      coalesce(d.data->>'vehicleState','') as _state,
      coalesce(public.ca_listing_value(e.ban_novu,d.data->>'body',d.data->>'bodyType',d.data->>'ban_novu'),'') as _body,
      coalesce(public.ca_listing_value(e.reng,d.data->>'color',d.data->>'reng'),'') as _color,
      coalesce(public.ca_listing_value(e.bazar_ucun,d.data->>'market',d.data->>'bazar_ucun'),'') as _market,
      coalesce(public.ca_listing_value(e.oturacaq_sayi::text,d.data->>'seats',d.data->>'oturacaq_sayi'),'') as _seats,
      case when e.yurus is not null then public.ca_listing_number(to_jsonb(e.yurus))
        else public.ca_listing_number(d.data->'mileage',d.data->'km',d.data->'yurus') end as _mileage,
      case when e.muherrik_hecmi is not null then public.ca_listing_number(to_jsonb(e.muherrik_hecmi))
        else public.ca_listing_number(d.data->'engine',d.data->'muherrik_hecmi') end as _engine,
      case when e.at_gucu is not null then public.ca_listing_number(to_jsonb(e.at_gucu))
        else public.ca_listing_number(d.data->'horsepower',d.data->'hp',d.data->'at_gucu') end as _horsepower,
      coalesce(e.techizat,array(select jsonb_array_elements_text(case when jsonb_typeof(d.data->'equipment')='array' then d.data->'equipment' when jsonb_typeof(d.data->'techizat')='array' then d.data->'techizat' else '[]'::jsonb end))) as _equipment,
      case when e.paket_adi='Tecili' then 'Tecili' when e.paket_adi in ('VIP','Premium','Standart')
 and (
   (e.paket_bitir is not null and e.paket_bitir > now())
   or (e.paket_bitir is null and e.tesdiq_tarixi <= now()
       and e.tesdiq_tarixi + make_interval(days=>case e.paket_adi when 'VIP' then 15 when 'Premium' then 10 when 'Standart' then 3 end) > now())
 ) then e.paket_adi else 'Pulsuz' end as _pack
    from public.elanlar e
    cross join lateral (
      select case
        when jsonb_typeof(e.ca_data)='object' then e.ca_data
        when jsonb_typeof(e.ca_data)='string'
          and pg_input_is_valid(e.ca_data#>>'{}','jsonb') then
            case when jsonb_typeof((e.ca_data#>>'{}')::jsonb)='object'
              then (e.ca_data#>>'{}')::jsonb else '{}'::jsonb end
        else '{}'::jsonb
      end as data
    ) d
    where e.veziyyet='aktiv' and not e.is_sold
  ), ranked as not materialized (
    select s.*, case s._pack when 'VIP' then 0 when 'Premium' then 1 when 'Standart' then 2 when 'Tecili' then 3 else 4 end as _rank
    from source s
  ), matched as materialized (
    select s.id,s._rank,s.qiymet,s.yaradildi from ranked s cross join settings q
    where (q.make='' or strpos(translate(lower(translate(coalesce(s._make,''),'İ','I')),'ı','i'),translate(lower(translate(coalesce(q.make,''),'İ','I')),'ı','i'))>0) and
      (q.model='' or strpos(translate(lower(translate(coalesce(s._model,''),'İ','I')),'ı','i'),translate(lower(translate(coalesce(q.model,''),'İ','I')),'ı','i'))>0) and
      (q.city='' or strpos(translate(lower(translate(coalesce(s._city,''),'İ','I')),'ı','i'),translate(lower(translate(coalesce(q.city,''),'İ','I')),'ı','i'))>0) and
      (q.color='' or strpos(translate(lower(translate(coalesce(s._color,''),'İ','I')),'ı','i'),translate(lower(translate(coalesce(q.color,''),'İ','I')),'ı','i'))>0) and
      (q.vehicle='' or s._vehicle=q.vehicle) and
      (q.state='' or s._state=q.state) and
      (q.body='' or s._body=q.body) and
      (q.market='' or s._market=q.market) and
      (q.seats='' or s._seats=q.seats) and
      (q.sale_type='' or q.sale_type=any(public.ca_listing_sale_options(s.ca_data))) and
      (q.pack in ('','all') or s._pack=q.pack) and
      (not q.urgent or s._pack='Tecili') and
      (q.price is null or s.qiymet <= q.price) and
      (q.pricemin is null or s.qiymet >= q.pricemin) and
      (q.pricemax is null or s.qiymet <= q.pricemax) and
      (q.yearmin is null or s.il >= q.yearmin) and
      (q.yearmax is null or s.il <= q.yearmax) and
      (q.kmmin is null or s._mileage >= q.kmmin) and
      (q.kmmax is null or s._mileage <= q.kmmax) and
      (q.enginemin is null or s._engine >= q.enginemin) and
      (q.enginemax is null or s._engine <= q.enginemax) and
      (q.hpmin is null or s._horsepower >= q.hpmin) and
      (q.hpmax is null or s._horsepower <= q.hpmax) and
      (cardinality(q.equipment)=0 or s._equipment @> q.equipment)
  ), paged as (
    select m.* from matched m cross join settings q
    order by m._rank,
      case when q.sort='priceAsc' then m.qiymet end asc nulls last,
      case when q.sort='priceDesc' then m.qiymet end desc nulls last,
      m.yaradildi desc, m.id desc
    limit v_size offset ((v_page::bigint-1)*v_size)
  ), promoted as (
    select s.id,s._rank,s.yaradildi from ranked s cross join settings q where s._pack='VIP' and not q.urgent
      and (q.sale_type='' or q.sale_type=any(public.ca_listing_sale_options(s.ca_data)))
    order by s.yaradildi desc,s.id desc limit 6
  ), totals as (
    select count(id) as n from matched
  ), public_rows as not materialized (
    select e.id, e.satici_id, e.marka, e.model, e.il, e.qiymet, e.yurus, e.seher, e.tesvir, e.veziyyet, e.yaradildi, e.neqliyyat_novu, e.nesil, e.ban_novu, e.yanacaq, e.suretler_qutusu, e.muherrik_hecmi, e.at_gucu, e.reng, e.bazar_ucun, e.oturacaq_sayi, e.techizat, e.sekiller, e.telefon, e.ca_data, e.paket_adi, e.paket_baslayir, e.paket_bitir, e.tesdiq_tarixi from public.elanlar e
  )
  select jsonb_build_object(
    'items',coalesce((select jsonb_agg(to_jsonb(l)
      order by p._rank,
        case when v_filters->>'sort'='priceAsc' then p.qiymet end asc nulls last,
        case when v_filters->>'sort'='priceDesc' then p.qiymet end desc nulls last,
        p.yaradildi desc,p.id desc) from paged p join public_rows l on l.id=p.id),'[]'::jsonb),
    'total',t.n,'page',v_page,'page_size',v_size,
    'total_pages',(t.n+v_size-1)/v_size,
    'vip_items',coalesce((select jsonb_agg(to_jsonb(l)
      order by p.yaradildi desc,p.id desc) from promoted p join public_rows l on l.id=p.id),'[]'::jsonb),
    'today_approved',(select count(id) from source
      where tesdiq_tarixi is not null
        and (tesdiq_tarixi at time zone 'Asia/Baku')::date=(now() at time zone 'Asia/Baku')::date)
  ) into v_result from totals t;
  return v_result;
end;
$function$;

CREATE OR REPLACE FUNCTION ca_private.search_matches(p_id uuid, p_filters jsonb)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
AS $function$
declare v_filters jsonb:=p_filters;result boolean;
begin
  if v_filters?'saleType' and v_filters->'saleType'<>'null'::jsonb
   and (jsonb_typeof(v_filters->'saleType')<>'string' or coalesce(v_filters->>'saleType','') not in ('','cash','credit','barter')) then
    raise exception 'Satış şərti düzgün deyil.' using errcode='22023';
  end if;
  if v_filters?'urgent' and v_filters->'urgent'<>'null'::jsonb
   and jsonb_typeof(v_filters->'urgent')<>'boolean' then
    raise exception 'Təcili filtri düzgün deyil.' using errcode='22023';
  end if;
  with settings as (
    select coalesce(v_filters->>'make','') as make,
      coalesce(v_filters->>'model','') as model,
      coalesce(v_filters->>'city','') as city,
      coalesce(v_filters->>'vehicle','') as vehicle,
      coalesce(v_filters->>'state','') as state,
      coalesce(v_filters->>'body','') as body,
      coalesce(v_filters->>'color','') as color,
      coalesce(v_filters->>'market','') as market,
      coalesce(v_filters->>'seats','') as seats,
      coalesce(v_filters->>'pack','') as pack,
      coalesce(v_filters->>'sort','') as sort,
      coalesce(v_filters->>'saleType','') as sale_type,
      coalesce((v_filters->>'urgent')::boolean,false) as urgent,
      public.ca_listing_number(v_filters->'price') as price,
      public.ca_listing_number(v_filters->'priceMin') as pricemin,
      public.ca_listing_number(v_filters->'priceMax') as pricemax,
      public.ca_listing_number(v_filters->'yearMin') as yearmin,
      public.ca_listing_number(v_filters->'yearMax') as yearmax,
      public.ca_listing_number(v_filters->'kmMin') as kmmin,
      public.ca_listing_number(v_filters->'kmMax') as kmmax,
      public.ca_listing_number(v_filters->'engineMin') as enginemin,
      public.ca_listing_number(v_filters->'engineMax') as enginemax,
      public.ca_listing_number(v_filters->'hpMin') as hpmin,
      public.ca_listing_number(v_filters->'hpMax') as hpmax,
      array(select jsonb_array_elements_text(case when jsonb_typeof(v_filters->'equipment')='array' then v_filters->'equipment' else '[]'::jsonb end)) as equipment
  ), source as materialized (
    select e.id, e.satici_id, e.marka, e.model, e.il, e.qiymet, e.yurus, e.seher, e.tesvir, e.veziyyet, e.yaradildi, e.neqliyyat_novu, e.nesil, e.ban_novu, e.yanacaq, e.suretler_qutusu, e.muherrik_hecmi, e.at_gucu, e.reng, e.bazar_ucun, e.oturacaq_sayi, e.techizat, e.sekiller, e.telefon, e.ca_data, e.paket_adi, e.paket_baslayir, e.paket_bitir, e.tesdiq_tarixi,
      coalesce(public.ca_listing_value(e.marka,d.data->>'make',d.data->>'marka',d.data->>'brand'),'') as _make,
      coalesce(public.ca_listing_value(e.model,d.data->>'model',d.data->>'modelName'),'') as _model,
      coalesce(public.ca_listing_value(e.seher,d.data->>'city',d.data->>'seher'),'') as _city,
      coalesce(public.ca_listing_value(e.neqliyyat_novu,d.data->>'vehicleType',d.data->>'vehicle',d.data->>'neqliyyat_novu'),'') as _vehicle,
      coalesce(d.data->>'vehicleState','') as _state,
      coalesce(public.ca_listing_value(e.ban_novu,d.data->>'body',d.data->>'bodyType',d.data->>'ban_novu'),'') as _body,
      coalesce(public.ca_listing_value(e.reng,d.data->>'color',d.data->>'reng'),'') as _color,
      coalesce(public.ca_listing_value(e.bazar_ucun,d.data->>'market',d.data->>'bazar_ucun'),'') as _market,
      coalesce(public.ca_listing_value(e.oturacaq_sayi::text,d.data->>'seats',d.data->>'oturacaq_sayi'),'') as _seats,
      case when e.yurus is not null then public.ca_listing_number(to_jsonb(e.yurus))
        else public.ca_listing_number(d.data->'mileage',d.data->'km',d.data->'yurus') end as _mileage,
      case when e.muherrik_hecmi is not null then public.ca_listing_number(to_jsonb(e.muherrik_hecmi))
        else public.ca_listing_number(d.data->'engine',d.data->'muherrik_hecmi') end as _engine,
      case when e.at_gucu is not null then public.ca_listing_number(to_jsonb(e.at_gucu))
        else public.ca_listing_number(d.data->'horsepower',d.data->'hp',d.data->'at_gucu') end as _horsepower,
      coalesce(e.techizat,array(select jsonb_array_elements_text(case when jsonb_typeof(d.data->'equipment')='array' then d.data->'equipment' when jsonb_typeof(d.data->'techizat')='array' then d.data->'techizat' else '[]'::jsonb end))) as _equipment,
      case when e.paket_adi='Tecili' then 'Tecili' when e.paket_adi in ('VIP','Premium','Standart')
 and (
   (e.paket_bitir is not null and e.paket_bitir > now())
   or (e.paket_bitir is null and e.tesdiq_tarixi <= now()
       and e.tesdiq_tarixi + make_interval(days=>case e.paket_adi when 'VIP' then 15 when 'Premium' then 10 when 'Standart' then 3 end) > now())
 ) then e.paket_adi else 'Pulsuz' end as _pack
    from public.elanlar e
    cross join lateral (
      select case
        when jsonb_typeof(e.ca_data)='object' then e.ca_data
        when jsonb_typeof(e.ca_data)='string'
          and pg_input_is_valid(e.ca_data#>>'{}','jsonb') then
            case when jsonb_typeof((e.ca_data#>>'{}')::jsonb)='object'
              then (e.ca_data#>>'{}')::jsonb else '{}'::jsonb end
        else '{}'::jsonb
      end as data
    ) d
    where e.id=p_id and e.veziyyet='aktiv' and not e.is_sold
  ), ranked as materialized (
    select s.*, case s._pack when 'VIP' then 0 when 'Premium' then 1 when 'Standart' then 2 when 'Tecili' then 3 else 4 end as _rank
    from source s
  ), matched as materialized (
    select s.* from ranked s cross join settings q
    where (q.make='' or strpos(translate(lower(translate(coalesce(s._make,''),'İ','I')),'ı','i'),translate(lower(translate(coalesce(q.make,''),'İ','I')),'ı','i'))>0) and
      (q.model='' or strpos(translate(lower(translate(coalesce(s._model,''),'İ','I')),'ı','i'),translate(lower(translate(coalesce(q.model,''),'İ','I')),'ı','i'))>0) and
      (q.city='' or strpos(translate(lower(translate(coalesce(s._city,''),'İ','I')),'ı','i'),translate(lower(translate(coalesce(q.city,''),'İ','I')),'ı','i'))>0) and
      (q.color='' or strpos(translate(lower(translate(coalesce(s._color,''),'İ','I')),'ı','i'),translate(lower(translate(coalesce(q.color,''),'İ','I')),'ı','i'))>0) and
      (q.vehicle='' or s._vehicle=q.vehicle) and
      (q.state='' or s._state=q.state) and
      (q.body='' or s._body=q.body) and
      (q.market='' or s._market=q.market) and
      (q.seats='' or s._seats=q.seats) and
      (q.sale_type='' or q.sale_type=any(public.ca_listing_sale_options(s.ca_data))) and
      (q.pack in ('','all') or s._pack=q.pack) and
      (not q.urgent or s._pack='Tecili') and
      (q.price is null or s.qiymet <= q.price) and
      (q.pricemin is null or s.qiymet >= q.pricemin) and
      (q.pricemax is null or s.qiymet <= q.pricemax) and
      (q.yearmin is null or s.il >= q.yearmin) and
      (q.yearmax is null or s.il <= q.yearmax) and
      (q.kmmin is null or s._mileage >= q.kmmin) and
      (q.kmmax is null or s._mileage <= q.kmmax) and
      (q.enginemin is null or s._engine >= q.enginemin) and
      (q.enginemax is null or s._engine <= q.enginemax) and
      (q.hpmin is null or s._horsepower >= q.hpmin) and
      (q.hpmax is null or s._horsepower <= q.hpmax) and
      s._equipment @> q.equipment
  )
select exists(select 1 from matched) into result;return result;
end $function$;

revoke all on function ca_private.search_matches(uuid,jsonb) from public,anon,authenticated;
notify pgrst,'reload schema';
