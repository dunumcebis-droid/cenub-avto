-- SQL reference for the already applied remote migration:
-- 20261107060719_fix_listing_management_and_paginated_browse
-- Restored from the reviewed payload; not a new CLI-generated migration.
-- The existing project schema/functions are prerequisites.

alter table public.elanlar enable row level security;

-- Record only genuine future approvals. Historical approval times are unknown.
alter table public.elanlar
  add column if not exists tesdiq_tarixi timestamptz;

-- Archive seller-deleted listings so foreign-key payment evidence and uploaded
-- photographs remain intact. The previous three states retain their meaning.
alter table public.elanlar drop constraint if exists elanlar_veziyyet_check;
alter table public.elanlar add constraint elanlar_veziyyet_check
  check (veziyyet in ('gozlemede', 'aktiv', 'reddedildi', 'silindi'));

-- RLS does not protect TRUNCATE. Browser roles never need these DDL-like grants.
revoke truncate, references, trigger on public.elanlar
  from anon, authenticated;

-- Table-level grants override per-column restrictions. Restrict BOTH INSERT
-- and UPDATE: otherwise a seller could prefill paid package fields at creation.
revoke insert, update on public.elanlar from authenticated;
-- Clear any old column-level write grants before setting the exact allowlist.
revoke insert (
  id, satici_id, marka, model, il, qiymet, yurus, seher, tesvir, veziyyet,
  yaradildi, neqliyyat_novu, nesil, ban_novu, yanacaq, suretler_qutusu,
  muherrik_hecmi, at_gucu, reng, bazar_ucun, oturacaq_sayi, techizat,
  sekiller, telefon, ca_data, paket_adi, paket_baslayir, paket_bitir,
  paket_tesdiq_qeydi, tesdiq_tarixi
) on public.elanlar from authenticated;
revoke update (
  id, satici_id, marka, model, il, qiymet, yurus, seher, tesvir, veziyyet,
  yaradildi, neqliyyat_novu, nesil, ban_novu, yanacaq, suretler_qutusu,
  muherrik_hecmi, at_gucu, reng, bazar_ucun, oturacaq_sayi, techizat,
  sekiller, telefon, ca_data, paket_adi, paket_baslayir, paket_bitir,
  paket_tesdiq_qeydi, tesdiq_tarixi
) on public.elanlar from authenticated;
grant insert (
  satici_id, marka, model, il, qiymet, yurus, seher, tesvir, veziyyet,
  neqliyyat_novu, nesil, ban_novu, yanacaq, suretler_qutusu,
  muherrik_hecmi, at_gucu, reng, bazar_ucun, oturacaq_sayi, techizat,
  sekiller, telefon, ca_data
) on public.elanlar to authenticated;
grant update (
  satici_id, marka, model, il, qiymet, yurus, seher, tesvir, veziyyet,
  neqliyyat_novu, nesil, ban_novu, yanacaq, suretler_qutusu,
  muherrik_hecmi, at_gucu, reng, bazar_ucun, oturacaq_sayi, techizat,
  sekiller, telefon, ca_data
) on public.elanlar to authenticated;

-- Existing owner INSERT policy already requires auth.uid() = satici_id and
-- veziyyet = 'gozlemede'; preserve it. Existing owner SELECT stays in place
-- so a successful archive PATCH may return its own updated row for verification.
-- Archived rows must be filtered from the seller cabinet in the frontend.
drop policy if exists "Satici oz elanini redakte edir" on public.elanlar;
create policy "Satici oz elanini redakte edir"
  on public.elanlar for update to authenticated
  using (
    satici_id = (select auth.uid())
    and veziyyet <> 'silindi'
  )
  with check (
    satici_id = (select auth.uid())
    and veziyyet in ('gozlemede', 'silindi')
  );

-- No hard DELETE policy is added. Existing browser DELETE privilege cannot
-- delete a row through RLS; the UI will use the archive PATCH instead.

-- Authenticated public reads should not expose internal approval notes either.
-- Existing anon column-level public read grants remain in place.
revoke select on public.elanlar from authenticated;
revoke select (paket_tesdiq_qeydi) on public.elanlar from authenticated;
grant select (
  id, satici_id, marka, model, il, qiymet, yurus, seher, tesvir, veziyyet,
  yaradildi, neqliyyat_novu, nesil, ban_novu, yanacaq, suretler_qutusu,
  muherrik_hecmi, at_gucu, reng, bazar_ucun, oturacaq_sayi, techizat,
  sekiller, telefon, ca_data, paket_adi, paket_baslayir, paket_bitir,
  tesdiq_tarixi
) on public.elanlar to authenticated;
grant select (tesdiq_tarixi) on public.elanlar to anon;

-- SECURITY INVOKER: the trigger gains no extra privileges. Column grants keep
-- clients from writing tesdiq_tarixi; only a real transition to active stamps it.
create or replace function public.ca_elan_tesdiq_tarixini_qeyd_et()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  if tg_op = 'INSERT' then
    new.tesdiq_tarixi := case
      when new.veziyyet = 'aktiv' then statement_timestamp()
      else null
    end;
  elsif new.veziyyet = 'aktiv' and old.veziyyet is distinct from 'aktiv' then
    new.tesdiq_tarixi := statement_timestamp();
  else
    new.tesdiq_tarixi := old.tesdiq_tarixi;
  end if;
  return new;
end;
$function$;
revoke all on function public.ca_elan_tesdiq_tarixini_qeyd_et()
  from public, anon, authenticated;
drop trigger if exists ca_elan_tesdiq_tarixi_trigger on public.elanlar;
create trigger ca_elan_tesdiq_tarixi_trigger
  before insert or update on public.elanlar
  for each row execute function public.ca_elan_tesdiq_tarixini_qeyd_et();

-- Existing privileged API, same signature and authorization, now idempotent.
-- The listing row lock serializes RPC calls with the existing AFTER INSERT /
-- UPDATE OF ca_data trigger; no duplicate request is created by a retry.
create or replace function public.ca_paket_sorgusu_yarat(
  p_elan_id uuid, p_paket_adi text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_sorgu public.paket_sorgulari%rowtype;
  v_sorgu_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Giris teleb olunur' using errcode = '42501';
  end if;
  if p_paket_adi is null or p_paket_adi not in ('VIP', 'Premium', 'Standart') then
    raise exception 'Yanlis paket' using errcode = '22023';
  end if;

  perform 1 from public.elanlar
    where id = p_elan_id
      and satici_id = (select auth.uid())
      and veziyyet = 'gozlemede'
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

  insert into public.paket_sorgulari (elan_id, satici_id, paket_adi)
    values (p_elan_id, (select auth.uid()), p_paket_adi)
    returning id into v_sorgu_id;
  return v_sorgu_id;
end;
$function$;
revoke all on function public.ca_paket_sorgusu_yarat(uuid, text)
  from public, anon;
grant execute on function public.ca_paket_sorgusu_yarat(uuid, text)
  to authenticated;

-- Keep automatic request creation in the listing's own transaction. The
-- trigger and explicit retry RPC now share one ownership/idempotency rule.
-- An empty requestedPackage means an ordinary edit, with no new purchase.
create or replace function public.ca_elan_paket_sorgusu_avtomatik()
returns trigger
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_label text;
  v_package text;
begin
  if new.veziyyet <> 'gozlemede' then
    return new;
  end if;
  v_label := coalesce(new.ca_data->>'requestedPackage', '');
  v_package := case
    when v_label like '%15 AZN%' then 'VIP'
    when v_label like '%5 AZN%' then 'Premium'
    when v_label like '%3 AZN%' then 'Standart'
    else null
  end;
  if v_package is null then
    return new;
  end if;
  perform public.ca_paket_sorgusu_yarat(new.id, v_package);
  return new;
end;
$function$;
revoke all on function public.ca_elan_paket_sorgusu_avtomatik()
  from public, anon, authenticated;
-- Preserve the existing AFTER INSERT OR UPDATE OF ca_data trigger, which
-- already invokes this function. No per-record UPDATE is performed here.

-- Keep the existing admin contract. Archived listings cannot be reactivated;
-- ordinary edit/reapproval never extends a paid package's recorded interval.
-- ca_admin_paket_tesdiq already clears both dates for a NEW approved request.
create or replace function public.ca_admin_status(p_id uuid, p_status text)
returns void
language plpgsql
security definer
set search_path = ''
as $function$
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
  if not found or v_elan.veziyyet = 'silindi' then
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
      v_gun := case v_paket
        when 'VIP' then 15 when 'Premium' then 5 when 'Standart' then 3
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
    if v_elan.paket_adi in ('VIP', 'Premium', 'Standart') then
      raise exception 'Tesdiqlenmis odenis tapilmadi' using errcode = '22023';
    end if;
  end if;

  update public.elanlar set veziyyet = p_status where id = p_id;
end;
$function$;
revoke all on function public.ca_admin_status(uuid, text) from public, anon;
grant execute on function public.ca_admin_status(uuid, text) to authenticated;

create or replace function public.ca_admin_list()
returns table(
  id uuid, marka text, model text, il integer, qiymet numeric, seher text,
  tesvir text, veziyyet text, yaradildi timestamptz
)
language plpgsql
stable
security definer
set search_path = ''
as $function$
begin
  if auth.uid() is null or not public.cenub_admin_yoxla() then
    raise exception 'Admin icazesi yoxdur' using errcode = '42501';
  end if;
  return query
    select e.id, e.marka, e.model, e.il, e.qiymet, e.seher,
      e.tesvir, e.veziyyet, e.yaradildi
    from public.elanlar e
    where e.veziyyet <> 'silindi'
    order by e.yaradildi desc limit 1000;
end;
$function$;
revoke all on function public.ca_admin_list() from public, anon;
grant execute on function public.ca_admin_list() to authenticated;

-- Hide pending requests for archived listings from the actionable payment
-- queue; keep confirmed/rejected payment history and all underlying rows.
create or replace function public.ca_admin_paket_sorgulari()
returns table(
  id uuid, elan_id uuid, paket_adi text, odenis_veziyyeti text,
  yaradilib timestamptz, tesdiqlenib timestamptz, marka text, model text
)
language plpgsql
security definer
set search_path = ''
as $function$
begin
  if auth.uid() is null or not public.cenub_admin_yoxla() then
    raise exception 'Admin icazesi yoxdur' using errcode = '42501';
  end if;
  return query
    select p.id, p.elan_id, p.paket_adi, p.odenis_veziyyeti,
      p.yaradilib, p.tesdiqlenib, e.marka::text, e.model::text
    from public.paket_sorgulari p
    join public.elanlar e on e.id = p.elan_id
    where e.veziyyet <> 'silindi' or p.odenis_veziyyeti <> 'gozlemede'
    order by p.yaradilib desc;
end;
$function$;
revoke all on function public.ca_admin_paket_sorgulari() from public, anon;
grant execute on function public.ca_admin_paket_sorgulari() to authenticated;

notify pgrst, 'reload schema';

-- Public browsing uses caller permissions and the existing active-only RLS.
-- No SECURITY DEFINER, no private approval notes and no fixed listing-count cap.
-- These pure helpers mirror caValue/text.trim() and caNumber() for legacy JSON.
create or replace function public.ca_listing_value(variadic p_values text[])
returns text
language sql immutable parallel safe security invoker
set search_path = ''
as $function$
  select btrim(v, U&'\0009\000A\000B\000C\000D\0020\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF')
  from unnest(p_values) with ordinality as candidates(v, n)
  where v is not null
    and btrim(v, U&'\0009\000A\000B\000C\000D\0020\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF') <> ''
  order by n limit 1;
$function$;
revoke all on function public.ca_listing_value(text[]) from public;
grant execute on function public.ca_listing_value(text[]) to anon, authenticated;

create or replace function public.ca_listing_number(p_value text)
returns double precision
language plpgsql immutable strict parallel safe security invoker
set search_path = ''
as $function$
declare
  v_text text;
  v_number double precision;
begin
  -- ECMAScript whitespace, including NBSP and narrow NBSP thousands separators.
  v_text := translate(p_value, U&'\0009\000A\000B\000C\000D\0020\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF', '');
  v_text := substring(v_text from '^[+-]?[0-9][0-9.,]*');
  if v_text is null then return null; end if;
  if strpos(v_text,'.') > 0 and strpos(v_text,',') > 0 then
    if strpos(reverse(v_text),'.') < strpos(reverse(v_text),',') then
      v_text := replace(v_text,',','');
    else
      v_text := regexp_replace(replace(v_text,'.',''),',','.');
    end if;
  elsif v_text ~ '^[+-]?[0-9]{1,3}([.,][0-9]{3})+$' then
    v_text := translate(v_text,'.,','');
  else
    v_text := regexp_replace(v_text,',','.');
  end if;
  if v_text !~ '^[+-]?[0-9]+([.][0-9]*)?$' then return null; end if;
  begin
    v_number := v_text::double precision;
  exception when numeric_value_out_of_range then
    -- JavaScript permits tiny values to round to zero; PostgreSQL reports
    -- double-precision underflow instead. Overflow still becomes a missing value.
    begin
      if abs(v_text::numeric) < '2.4703282292062327e-324'::numeric then
        return 0::double precision;
      end if;
    exception when numeric_value_out_of_range then
      null;
    end;
    return null;
  end;
  if v_number >= 0 and v_number <= '1.7976931348623157e308'::double precision then
    return v_number;
  end if;
  return null;
end;
$function$;
revoke all on function public.ca_listing_number(text) from public;
grant execute on function public.ca_listing_number(text) to anon, authenticated;

-- Keep the selected legacy alias's JSON type: JSON number 1.234 is a number,
-- whereas JSON string "1.234" follows caNumber's thousands-separator rule.
create or replace function public.ca_listing_number(variadic p_values jsonb[])
returns double precision
language plpgsql immutable parallel safe security invoker
set search_path = ''
as $function$
declare
  v_value jsonb;
  v_number double precision;
begin
  select v into v_value
    from unnest(p_values) with ordinality as candidates(v,n)
    where v is not null and v <> 'null'::jsonb
      and public.ca_listing_value(v#>>'{}') is not null
    order by n limit 1;
  if v_value is null then return null; end if;
  if jsonb_typeof(v_value) <> 'number' then
    return public.ca_listing_number(v_value#>>'{}');
  end if;
  begin
    v_number := (v_value#>>'{}')::double precision;
  exception when numeric_value_out_of_range then
    if abs((v_value#>>'{}')::numeric) < '2.4703282292062327e-324'::numeric then
      return 0::double precision;
    end if;
    return null;
  end;
  if v_number >= 0 and v_number <= '1.7976931348623157e308'::double precision then
    return v_number;
  end if;
  return null;
end;
$function$;
revoke all on function public.ca_listing_number(jsonb[]) from public;
grant execute on function public.ca_listing_number(jsonb[]) to anon, authenticated;

create or replace function public.ca_browse_listings(
  p_filters jsonb default '{}'::jsonb,
  p_page integer default 1,
  p_page_size integer default 24
) returns jsonb
language plpgsql stable security invoker
set search_path = ''
as $function$
declare
  v_filters jsonb := coalesce(p_filters,'{}'::jsonb);
  v_page integer := greatest(1,coalesce(p_page,1));
  v_size integer := least(48,greatest(1,coalesce(p_page_size,24)));
  v_result jsonb;
begin
  if jsonb_typeof(v_filters) <> 'object' then
    raise exception 'Filters must be an object' using errcode='22023';
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
    where e.veziyyet='aktiv'
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
  ), paged as (
    select m.* from matched m cross join settings q
    order by m._rank,
      case when q.sort='priceAsc' then m.qiymet end asc nulls last,
      case when q.sort='priceDesc' then m.qiymet end desc nulls last,
      m.yaradildi desc, m.id desc
    limit v_size offset ((v_page::bigint-1)*v_size)
  ), promoted as (
    select s.* from ranked s where s._pack='VIP'
    order by s.yaradildi desc,s.id desc limit 6
  ), totals as (
    select count(id) as n from matched
  )
  select jsonb_build_object(
    'items',coalesce((select jsonb_agg((to_jsonb(p) - array['_make','_model','_city','_vehicle','_state','_body','_color','_market','_seats','_mileage','_engine','_horsepower','_equipment','_pack','_rank']::text[])
      order by p._rank,
        case when v_filters->>'sort'='priceAsc' then p.qiymet end asc nulls last,
        case when v_filters->>'sort'='priceDesc' then p.qiymet end desc nulls last,
        p.yaradildi desc,p.id desc) from paged p),'[]'::jsonb),
    'total',t.n,'page',v_page,'page_size',v_size,
    'total_pages',(t.n+v_size-1)/v_size,
    'vip_items',coalesce((select jsonb_agg((to_jsonb(p) - array['_make','_model','_city','_vehicle','_state','_body','_color','_market','_seats','_mileage','_engine','_horsepower','_equipment','_pack','_rank']::text[])
      order by p.yaradildi desc,p.id desc) from promoted p),'[]'::jsonb),
    'today_approved',(select count(id) from source
      where tesdiq_tarixi is not null
        and (tesdiq_tarixi at time zone 'Asia/Baku')::date=(now() at time zone 'Asia/Baku')::date)
  ) into v_result from totals t;
  return v_result;
end;
$function$;
revoke all on function public.ca_browse_listings(jsonb,integer,integer) from public;
grant execute on function public.ca_browse_listings(jsonb,integer,integer) to anon, authenticated;

-- Indexes for the existing listing/owner/payment lookup patterns.
-- No user rows or image/package values are rewritten.
create index if not exists elanlar_active_created_id_idx
  on public.elanlar (yaradildi desc, id desc) where veziyyet = 'aktiv';
create index if not exists elanlar_owner_created_id_idx
  on public.elanlar (satici_id, yaradildi desc, id desc);
create index if not exists paket_sorgulari_listing_status_created_idx
  on public.paket_sorgulari (elan_id, odenis_veziyyeti, yaradilib desc, id desc);
create index if not exists paket_sorgulari_seller_idx
  on public.paket_sorgulari (satici_id);

-- An event-trigger function cannot be called as a client RPC and requires no
-- browser EXECUTE grant. Its existing event-trigger invocation is preserved.
revoke all on function public.rls_auto_enable() from public, anon, authenticated;

notify pgrst, 'reload schema';
