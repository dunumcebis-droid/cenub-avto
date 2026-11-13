-- Seller-declared sale conditions. No old listing, photo or package is rewritten.
-- Apply after browse-performance.sql and marketplace-features.sql.
create or replace function public.ca_listing_sale_options(p_data jsonb)
returns text[] language plpgsql immutable parallel safe security invoker set search_path='' as $$
declare data jsonb:=p_data;options jsonb;result text[];
begin
 if jsonb_typeof(data)='string' then
  if pg_input_is_valid(data#>>'{}','jsonb') then data:=(data#>>'{}')::jsonb;else data:='{}';end if;
 end if;
 if jsonb_typeof(data) is distinct from 'object' then return array['cash']::text[];end if;
 options:=data->'saleOptions';
 if jsonb_typeof(options) is distinct from 'array' then return array['cash']::text[];end if;
 select array_agg(choice order by ord) into result
 from unnest(array['cash','credit','barter']::text[]) with ordinality as allowed(choice,ord)
 where options?choice;
 return coalesce(result,array['cash']::text[]);
end $$;
revoke all on function public.ca_listing_sale_options(jsonb) from public,anon,authenticated;
grant execute on function public.ca_listing_sale_options(jsonb) to anon,authenticated,service_role;

-- Validate only inserted/changed explicit declarations. Untouched older invalid
-- declarations can still be edited without changing unrelated information.
create or replace function ca_private.check_listing_sale_options()
returns trigger language plpgsql security invoker set search_path='' as $$
declare data jsonb:=new.ca_data;previous jsonb;options jsonb;encoded boolean:=false;
begin
 if jsonb_typeof(data)='string' then
  encoded:=true;
  if pg_input_is_valid(data#>>'{}','jsonb') then data:=(data#>>'{}')::jsonb;else return new;end if;
 end if;
 if jsonb_typeof(data) is distinct from 'object' or not(data?'saleOptions') then return new;end if;
 options:=data->'saleOptions';
 if tg_op='UPDATE' then
  previous:=old.ca_data;
  if jsonb_typeof(previous)='string' then
   if pg_input_is_valid(previous#>>'{}','jsonb') then previous:=(previous#>>'{}')::jsonb;else previous:='{}';end if;
  end if;
  if jsonb_typeof(previous)='object' and previous?'saleOptions'
   and options is not distinct from previous->'saleOptions' then return new;end if;
 end if;
 if jsonb_typeof(options) is distinct from 'array' then
  raise exception 'Nağd, Kredit və ya Barter seçimlərindən ən azı birini seç.' using errcode='23514';
 end if;
 if jsonb_array_length(options)<1 or jsonb_array_length(options)>3 then
  raise exception 'Satış şərti üçün 1–3 seçim olmalıdır.' using errcode='23514';
 end if;
 if exists(select 1 from jsonb_array_elements(options) item where jsonb_typeof(item)<>'string' or not((item#>>'{}')=any(array['cash','credit','barter']::text[]))) then
  raise exception 'Satış şərti düzgün deyil.' using errcode='23514';
 end if;
 data:=jsonb_set(data,'{saleOptions}',to_jsonb(public.ca_listing_sale_options(data)),true);
 -- Retain the old JSON-string container shape rather than changing unrelated
 -- legacy photo/submission trigger behavior during a sale-condition update.
 new.ca_data:=case when encoded then to_jsonb(data::text) else data end;
 return new;
end $$;
revoke all on function ca_private.check_listing_sale_options() from public,anon,authenticated;
do $trigger$begin
 if not exists(select 1 from pg_trigger where tgrelid='public.elanlar'::regclass and tgname='ca_sale_options_check') then
  create trigger ca_sale_options_check before insert or update of ca_data on public.elanlar
  for each row execute function ca_private.check_listing_sale_options();
 end if;
end $trigger$;

-- Avoid normalizing/copying wide listing records before filtering and paging.
-- Preserve the existing public projection and all legacy filter semantics.
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
      case when e.paket_adi in ('VIP','Premium','Standart')
 and (
   (e.paket_bitir is not null and e.paket_bitir > now())
   or (e.paket_bitir is null and e.tesdiq_tarixi <= now()
       and e.tesdiq_tarixi + make_interval(days=>case e.paket_adi when 'VIP' then 15 when 'Premium' then 5 when 'Standart' then 3 end) > now())
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
    select s.*, case s._pack when 'VIP' then 0 when 'Premium' then 1 when 'Standart' then 2 else 3 end as _rank
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
    select s.id,s._rank,s.yaradildi from ranked s cross join settings q where s._pack='VIP'
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
$function$
;

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
      case when e.paket_adi in ('VIP','Premium','Standart')
 and (
   (e.paket_bitir is not null and e.paket_bitir > now())
   or (e.paket_bitir is null and e.tesdiq_tarixi <= now()
       and e.tesdiq_tarixi + make_interval(days=>case e.paket_adi when 'VIP' then 15 when 'Premium' then 5 when 'Standart' then 3 end) > now())
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
    select s.*, case s._pack when 'VIP' then 0 when 'Premium' then 1 when 'Standart' then 2 else 3 end as _rank
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

CREATE OR REPLACE FUNCTION ca_private.clean_saved_filters(p_filters jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO ''
AS $function$
declare k text;v jsonb;result jsonb:='{}';n numeric;
begin
 if jsonb_typeof(p_filters) is distinct from 'object' or octet_length(p_filters::text)>10000 then raise exception 'Axtarış məlumatı düzgün deyil.' using errcode='22023';end if;
 for k,v in select key,value from jsonb_each(p_filters) loop
  if k=any(array['price','priceMin','priceMax','yearMin','yearMax','kmMin','kmMax','engineMin','engineMax','hpMin','hpMax']) then
   if v='null'::jsonb or v='""'::jsonb then continue;end if;
   n:=public.ca_listing_number(v);if n is null or n<0 or n>1000000000000 then raise exception 'Axtarış rəqəmi düzgün deyil.' using errcode='22023';end if;result:=result||jsonb_build_object(k,n);
  elsif k='saleType' then
   if v='null'::jsonb or v='""'::jsonb then continue;end if;
   if jsonb_typeof(v)<>'string' or (v#>>'{}') not in ('cash','credit','barter') then raise exception 'Satış şərti düzgün deyil.' using errcode='22023';end if;
   result:=result||jsonb_build_object(k,v);
  elsif k='sort' then
   if jsonb_typeof(v)<>'string' or (v#>>'{}') not in ('newest','priceAsc','priceDesc') then raise exception 'Sıralama düzgün deyil.' using errcode='22023';end if;
   if v<>'"newest"'::jsonb then result:=result||jsonb_build_object(k,v);end if;
  elsif k='equipment' then
   if jsonb_typeof(v)<>'array' or jsonb_array_length(v)>40 then raise exception 'Təchizat düzgün deyil.' using errcode='22023';end if;
   if exists(select 1 from jsonb_array_elements(v) x where jsonb_typeof(x)<>'string' or length(x#>>'{}')>100) then raise exception 'Təchizat düzgün deyil.' using errcode='22023';end if;
   if jsonb_array_length(v)>0 then result:=result||jsonb_build_object(k,(select jsonb_agg(t order by t) from(select distinct value t from jsonb_array_elements(v))q));end if;
  elsif k=any(array['make','model','city','vehicle','state','body','color','market','seats','pack']) then
   if v='null'::jsonb then continue;end if;if jsonb_typeof(v)<>'string' or length(v#>>'{}')>150 then raise exception 'Axtarış mətni düzgün deyil.' using errcode='22023';end if;
   if btrim(v#>>'{}')<>'' and not(k='pack' and v='"all"'::jsonb) then result:=result||jsonb_build_object(k,btrim(v#>>'{}'));end if;
  end if;
 end loop;
 return result;
end $function$;

revoke all on function ca_private.search_matches(uuid,jsonb),ca_private.clean_saved_filters(jsonb) from public,anon,authenticated;
notify pgrst,'reload schema';
