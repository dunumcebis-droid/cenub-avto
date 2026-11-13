-- Additive marketplace features. Existing photographs, packages and listing data stay intact.
alter table public.elanlar add column if not exists is_sold boolean not null default false;
grant select(is_sold) on public.elanlar to anon,authenticated;
alter policy "Aktiv elanlar hamıya görünür" on public.elanlar using(veziyyet='aktiv' and not is_sold);
grant usage on schema ca_private to anon,authenticated;

create table if not exists ca_private.listing_stats(
 elan_id uuid primary key references public.elanlar(id) on delete cascade,
 views bigint not null default 0,contact_clicks bigint not null default 0
);
create table if not exists ca_private.listing_events(
 elan_id uuid not null references public.elanlar(id) on delete cascade,
 kind text not null check(kind in ('view','contact')),day date not null,visitor_hash text not null,
 primary key(elan_id,kind,day,visitor_hash)
);
create index if not exists ca_listing_event_visitor_day on ca_private.listing_events(day,visitor_hash);
create table if not exists ca_private.listing_reports(
 id uuid primary key default gen_random_uuid(),elan_id uuid not null references public.elanlar(id) on delete cascade,
 reporter_id uuid not null references auth.users(id) on delete cascade,
 reason text not null check(reason in ('fraud','wrong_info','duplicate','inappropriate','other')),
 details text not null default '' check(length(details)<=1000),status text not null default 'open' check(status in ('open','resolved','dismissed')),
 created_at timestamptz not null default now(),admin_note text not null default '' check(length(admin_note)<=1000),resolved_at timestamptz
);
create unique index if not exists ca_report_one_open on ca_private.listing_reports(elan_id,reporter_id) where status='open';
create index if not exists ca_report_status_created on ca_private.listing_reports(status,created_at desc,id);
create index if not exists ca_report_owner_created on ca_private.listing_reports(reporter_id,created_at);
create table if not exists ca_private.saved_searches(
 id uuid primary key default gen_random_uuid(),owner_id uuid not null references auth.users(id) on delete cascade,
 name text not null check(length(name) between 1 and 80),filters jsonb not null check(jsonb_typeof(filters)='object'),
 filter_hash text not null,start_seq bigint not null,created_at timestamptz not null default now(),unique(owner_id,filter_hash)
);
create table if not exists ca_private.approved_listing_events(
 seq bigint generated always as identity primary key,elan_id uuid not null references public.elanlar(id) on delete cascade,created_at timestamptz not null default now()
);
create table if not exists ca_private.notification_progress(
 owner_id uuid primary key references auth.users(id) on delete cascade,cursor_seq bigint not null default 0
);
create table if not exists ca_private.search_notifications(
 id uuid primary key default gen_random_uuid(),owner_id uuid not null references auth.users(id) on delete cascade,
 search_id uuid not null references ca_private.saved_searches(id) on delete cascade,
 elan_id uuid not null references public.elanlar(id) on delete cascade,created_at timestamptz not null default now(),is_read boolean not null default false,
 unique(search_id,elan_id)
);
create index if not exists ca_search_owner_created on ca_private.saved_searches(owner_id,created_at);
create index if not exists ca_notification_owner_created on ca_private.search_notifications(owner_id,created_at desc,id);
-- Browser roles can call only explicitly granted APIs; never the source tables.
do $security$
declare t text;
begin
 foreach t in array array['listing_stats','listing_events','listing_reports','saved_searches','approved_listing_events','notification_progress','search_notifications'] loop
  execute format('alter table ca_private.%I enable row level security',t);
  execute format('revoke all on ca_private.%I from public,anon,authenticated',t);
  if not exists(select 1 from pg_policies where schemaname='ca_private' and tablename=t and policyname='service_only') then
   execute format('create policy service_only on ca_private.%I for all to service_role using(true) with check(true)',t);
  end if;
 end loop;
end $security$;

create or replace function ca_private.api_mark_listing_sold(p_id uuid)
returns uuid language plpgsql security definer set search_path='' as $$
declare result uuid;
begin
 if auth.uid() is null then raise exception 'Hesabına daxil ol.' using errcode='42501';end if;
 update public.elanlar set is_sold=true where id=p_id and satici_id=auth.uid() and veziyyet<>'silindi' returning id into result;
 if result is null then raise exception 'Elan tapılmadı və ya sizə aid deyil.' using errcode='42501';end if;
 return result;
end $$;

create or replace function ca_private.api_record_listing_event(p_id uuid,p_kind text,p_visitor uuid)
returns boolean language plpgsql security definer set search_path='' as $$
declare d date:=(now() at time zone 'Asia/Baku')::date;h text;changed integer;
begin
 if p_kind is null or p_kind not in ('view','contact') or p_visitor is null then return false;end if;
 if not exists(select 1 from public.elanlar where id=p_id and veziyyet='aktiv' and not is_sold and (auth.uid() is null or satici_id<>auth.uid())) then return false;end if;
 h:=md5(p_visitor::text||d::text);
 perform pg_advisory_xact_lock(hashtextextended('ca_event:'||h,0));
 if (select count(*) from ca_private.listing_events where day=d and visitor_hash=h)>=200 then return false;end if;
 insert into ca_private.listing_events(elan_id,kind,day,visitor_hash) values(p_id,p_kind,d,h) on conflict do nothing;
 get diagnostics changed=row_count;
 if changed=1 then
  insert into ca_private.listing_stats(elan_id,views,contact_clicks) values(p_id,(p_kind='view')::int,(p_kind='contact')::int)
  on conflict(elan_id) do update set views=ca_private.listing_stats.views+excluded.views,contact_clicks=ca_private.listing_stats.contact_clicks+excluded.contact_clicks;
 end if;
 delete from ca_private.listing_events where ctid in(select ctid from ca_private.listing_events where day<d-2 limit 100);
 return changed=1;
end $$;

create or replace function ca_private.api_my_listing_stats(p_ids uuid[])
returns jsonb language plpgsql stable security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'Hesabına daxil ol.' using errcode='42501';end if;
 if coalesce(cardinality(p_ids),0)>100 then raise exception 'Maksimum 100 elan.' using errcode='22023';end if;
 return coalesce((select jsonb_agg(jsonb_build_object('id',e.id,'views',coalesce(s.views,0),'contact_clicks',coalesce(s.contact_clicks,0))) from public.elanlar e left join ca_private.listing_stats s on s.elan_id=e.id where e.satici_id=auth.uid() and e.id=any(p_ids)),'[]'::jsonb);
end $$;

create or replace function ca_private.api_report_listing(p_id uuid,p_reason text,p_details text)
returns uuid language plpgsql security definer set search_path='' as $$
declare result uuid;
begin
 if auth.uid() is null then raise exception 'Şikayət üçün hesabına daxil ol.' using errcode='42501';end if;
 if p_reason is null or p_reason not in ('fraud','wrong_info','duplicate','inappropriate','other') or length(coalesce(p_details,''))>1000 then raise exception 'Şikayət məlumatı düzgün deyil.' using errcode='22023';end if;
 if not exists(select 1 from public.elanlar where id=p_id and veziyyet='aktiv' and not is_sold and satici_id<>auth.uid()) then raise exception 'Şikayət üçün elan əlçatan deyil.' using errcode='22023';end if;
 perform pg_advisory_xact_lock(hashtextextended('ca_report:'||auth.uid()::text,0));
 select id into result from ca_private.listing_reports where elan_id=p_id and reporter_id=auth.uid() and status='open';if found then return result;end if;
 if (select count(*) from ca_private.listing_reports where reporter_id=auth.uid() and created_at>now()-interval '1 day')>=10 then raise exception 'Gündəlik şikayət limitinə çatmısınız.' using errcode='22023';end if;
 insert into ca_private.listing_reports(elan_id,reporter_id,reason,details) values(p_id,auth.uid(),p_reason,btrim(coalesce(p_details,''))) returning id into result;return result;
end $$;

create or replace function ca_private.api_admin_browse_reports(p_status text,p_page integer,p_page_size integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare sz integer:=least(48,greatest(1,coalesce(p_page_size,24)));pg integer;total bigint;
begin
 if auth.uid() is null or not public.cenub_admin_yoxla() then raise exception 'Admin icazəsi yoxdur.' using errcode='42501';end if;
 if p_status is null or p_status not in ('all','open','resolved','dismissed') then raise exception 'Yanlış status.' using errcode='22023';end if;
 select count(*) into total from ca_private.listing_reports where p_status='all' or status=p_status;
 pg:=greatest(1,least(greatest(1,coalesce(p_page,1)),greatest(1,(total+sz-1)/sz)));
 return jsonb_build_object('total',total,'page',pg,'total_pages',(total+sz-1)/sz,'items',coalesce((select jsonb_agg(to_jsonb(r)) from(select r.id,r.elan_id,e.marka,e.model,r.reason,r.details,r.status,r.created_at,r.admin_note from ca_private.listing_reports r join public.elanlar e on e.id=r.elan_id where p_status='all' or r.status=p_status order by r.created_at desc,r.id desc limit sz offset (pg-1)*sz)r),'[]'::jsonb));
end $$;

create or replace function ca_private.api_admin_resolve_report(p_report_id uuid,p_status text,p_note text)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null or not public.cenub_admin_yoxla() then raise exception 'Admin icazəsi yoxdur.' using errcode='42501';end if;
 if p_status is null or p_status not in ('resolved','dismissed') or length(coalesce(p_note,''))>1000 then raise exception 'Yanlış qərar.' using errcode='22023';end if;
 update ca_private.listing_reports set status=p_status,admin_note=coalesce(p_note,''),resolved_at=now() where id=p_report_id;
 return found;
end $$;

create or replace function ca_private.clean_saved_filters(p_filters jsonb)
returns jsonb language plpgsql immutable security invoker set search_path='' as $$
declare k text;v jsonb;result jsonb:='{}';n numeric;
begin
 if jsonb_typeof(p_filters) is distinct from 'object' or octet_length(p_filters::text)>10000 then raise exception 'Axtarış məlumatı düzgün deyil.' using errcode='22023';end if;
 for k,v in select key,value from jsonb_each(p_filters) loop
  if k=any(array['price','priceMin','priceMax','yearMin','yearMax','kmMin','kmMax','engineMin','engineMax','hpMin','hpMax']) then
   if v='null'::jsonb or v='""'::jsonb then continue;end if;
   n:=public.ca_listing_number(v);if n is null or n<0 or n>1000000000000 then raise exception 'Axtarış rəqəmi düzgün deyil.' using errcode='22023';end if;result:=result||jsonb_build_object(k,n);
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
end $$;

create or replace function ca_private.api_save_search(p_name text,p_filters jsonb)
returns uuid language plpgsql security definer set search_path='' as $$
declare f jsonb;result uuid;seq bigint;label text:=btrim(coalesce(p_name,''));h text;
begin
 if auth.uid() is null then raise exception 'Hesabına daxil ol.' using errcode='42501';end if;
 if length(label)<1 or length(label)>80 then raise exception 'Axtarışın adı 1–80 simvol olmalıdır.' using errcode='22023';end if;
 f:=ca_private.clean_saved_filters(p_filters);h:=md5(f::text);
 perform pg_advisory_xact_lock(hashtextextended('ca_search:'||auth.uid()::text,0));
 select id into result from ca_private.saved_searches where owner_id=auth.uid() and filter_hash=h and filters=f;
 if found then update ca_private.saved_searches set name=label where id=result;return result;end if;
 if (select count(*) from ca_private.saved_searches where owner_id=auth.uid())>=20 then raise exception 'Maksimum 20 yadda saxlanmış axtarış ola bilər.' using errcode='22023';end if;
 select coalesce(max(e.seq),0) into seq from ca_private.approved_listing_events e;
 insert into ca_private.saved_searches(owner_id,name,filters,filter_hash,start_seq) values(auth.uid(),label,f,h,seq) returning id into result;
 insert into ca_private.notification_progress(owner_id,cursor_seq) values(auth.uid(),seq) on conflict do nothing;
 return result;
end $$;
create or replace function ca_private.api_list_saved_searches()
returns jsonb language plpgsql stable security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'Hesabına daxil ol.' using errcode='42501';end if;
 return coalesce((select jsonb_agg(jsonb_build_object('id',id,'name',name,'filters',filters,'created_at',created_at) order by created_at desc,id) from ca_private.saved_searches where owner_id=auth.uid()),'[]'::jsonb);
end $$;
create or replace function ca_private.api_delete_saved_search(p_id uuid)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'Hesabına daxil ol.' using errcode='42501';end if;
 delete from ca_private.saved_searches where id=p_id and owner_id=auth.uid();return found;
end $$;

create or replace function ca_private.enqueue_approved_listing()
returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.veziyyet='aktiv' and not new.is_sold then
  if tg_op='INSERT' or old.veziyyet is distinct from 'aktiv' or old.is_sold then
   -- Serialize allocation until commit so a cursor never skips a later-committed lower sequence.
   perform pg_advisory_xact_lock(hashtextextended('ca_approval_event_sequence',0));
   insert into ca_private.approved_listing_events(elan_id) values(new.id);
  end if;
 end if;
 return new;
end $$;
revoke all on function ca_private.enqueue_approved_listing() from public,anon,authenticated;
do $$begin
 if not exists(select 1 from pg_trigger where tgname='ca_market_approved_event' and tgrelid='public.elanlar'::regclass) then
  create trigger ca_market_approved_event after insert or update on public.elanlar for each row execute function ca_private.enqueue_approved_listing();
 end if;
end$$;

-- Process only the signed-in user's preferences; publication never scans all users.
create or replace function ca_private.api_list_notifications(p_page integer,p_page_size integer)
returns jsonb language plpgsql security definer set search_path='' as $$
declare cursor_value bigint;last_seq bigint;approval_event record;saved_search record;sz integer:=least(48,greatest(1,coalesce(p_page_size,24)));pg integer;total bigint;unread bigint;
begin
 if auth.uid() is null then raise exception 'Hesabına daxil ol.' using errcode='42501';end if;
 perform pg_advisory_xact_lock(hashtextextended('ca_notifications:'||auth.uid()::text,0));
 select coalesce(max(seq),0) into last_seq from ca_private.approved_listing_events;
 insert into ca_private.notification_progress(owner_id,cursor_seq) values(auth.uid(),last_seq) on conflict do nothing;
 select cursor_seq into cursor_value from ca_private.notification_progress where owner_id=auth.uid() for update;
 for approval_event in select q.seq,q.elan_id from ca_private.approved_listing_events q where q.seq>cursor_value order by q.seq limit 100 loop
  for saved_search in select * from ca_private.saved_searches where owner_id=auth.uid() and start_seq<approval_event.seq loop
   if exists(select 1 from public.elanlar where id=approval_event.elan_id and satici_id<>auth.uid()) and ca_private.search_matches(approval_event.elan_id,saved_search.filters) then
    insert into ca_private.search_notifications(owner_id,search_id,elan_id) values(auth.uid(),saved_search.id,approval_event.elan_id) on conflict(search_id,elan_id) do nothing;
   end if;
  end loop;
  cursor_value:=approval_event.seq;
 end loop;
 update ca_private.notification_progress set cursor_seq=cursor_value where owner_id=auth.uid();
 select count(*),count(*) filter(where not n.is_read) into total,unread from ca_private.search_notifications n join public.elanlar e on e.id=n.elan_id where n.owner_id=auth.uid() and e.veziyyet='aktiv' and not e.is_sold;
 pg:=greatest(1,least(greatest(1,coalesce(p_page,1)),greatest(1,(total+sz-1)/sz)));
 return jsonb_build_object('total',total,'unread_count',unread,'page',pg,'total_pages',(total+sz-1)/sz,'processing',cursor_value<last_seq,'items',coalesce((select jsonb_agg(to_jsonb(r)) from(select n.id,n.search_id,s.name as search_name,n.elan_id,e.marka,e.model,e.il,e.qiymet,e.seher,n.created_at,n.is_read from ca_private.search_notifications n join ca_private.saved_searches s on s.id=n.search_id join public.elanlar e on e.id=n.elan_id where n.owner_id=auth.uid() and e.veziyyet='aktiv' and not e.is_sold order by n.created_at desc,n.id desc limit sz offset (pg-1)*sz)r),'[]'::jsonb));
end $$;
create or replace function ca_private.api_mark_notification_read(p_id uuid)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'Hesabına daxil ol.' using errcode='42501';end if;
 update ca_private.search_notifications set is_read=true where owner_id=auth.uid() and (p_id is null or id=p_id);return found;
end $$;

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
    where e.veziyyet='aktiv' and not e.is_sold
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
$function$
;

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
$function$
;

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
$function$
;

create or replace function public.ca_admin_list()
returns table(id uuid,marka text,model text,il integer,qiymet numeric,seher text,tesvir text,veziyyet text,yaradildi timestamptz)
language plpgsql stable security invoker set search_path='' as $$
begin
 if auth.uid() is null or not public.cenub_admin_yoxla() then raise exception 'Admin icazəsi yoxdur.' using errcode='42501';end if;
 return query select e.id,e.marka,e.model,e.il,e.qiymet,e.seher,e.tesvir,case when e.is_sold then 'satilib' else e.veziyyet end,e.yaradildi from public.elanlar e where e.veziyyet<>'silindi' order by e.yaradildi desc,e.id desc;
end $$;

create or replace function ca_private.search_matches(p_id uuid,p_filters jsonb)
returns boolean language plpgsql stable security invoker set search_path='' as $$
declare v_filters jsonb:=p_filters;result boolean;
begin
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
end $$;
revoke all on function ca_private.search_matches(uuid,jsonb),ca_private.clean_saved_filters(jsonb) from public,anon,authenticated;

revoke all on function ca_private.api_mark_listing_sold(uuid) from public,anon,authenticated;
grant execute on function ca_private.api_mark_listing_sold(uuid) to authenticated;
create or replace function public.ca_mark_listing_sold(p_id uuid) returns uuid language sql security invoker set search_path='' as $api$ select ca_private.api_mark_listing_sold(p_id); $api$;
revoke all on function public.ca_mark_listing_sold(uuid) from public,anon,authenticated;
grant execute on function public.ca_mark_listing_sold(uuid) to authenticated;

revoke all on function ca_private.api_record_listing_event(uuid,text,uuid) from public,anon,authenticated;
grant execute on function ca_private.api_record_listing_event(uuid,text,uuid) to anon,authenticated;
create or replace function public.ca_record_listing_event(p_id uuid,p_kind text,p_visitor uuid) returns boolean language sql security invoker set search_path='' as $api$ select ca_private.api_record_listing_event(p_id,p_kind,p_visitor); $api$;
revoke all on function public.ca_record_listing_event(uuid,text,uuid) from public,anon,authenticated;
grant execute on function public.ca_record_listing_event(uuid,text,uuid) to anon,authenticated;

revoke all on function ca_private.api_my_listing_stats(uuid[]) from public,anon,authenticated;
grant execute on function ca_private.api_my_listing_stats(uuid[]) to authenticated;
create or replace function public.ca_my_listing_stats(p_ids uuid[]) returns jsonb language sql security invoker set search_path='' as $api$ select ca_private.api_my_listing_stats(p_ids); $api$;
revoke all on function public.ca_my_listing_stats(uuid[]) from public,anon,authenticated;
grant execute on function public.ca_my_listing_stats(uuid[]) to authenticated;

revoke all on function ca_private.api_report_listing(uuid,text,text) from public,anon,authenticated;
grant execute on function ca_private.api_report_listing(uuid,text,text) to authenticated;
create or replace function public.ca_report_listing(p_id uuid,p_reason text,p_details text) returns uuid language sql security invoker set search_path='' as $api$ select ca_private.api_report_listing(p_id,p_reason,p_details); $api$;
revoke all on function public.ca_report_listing(uuid,text,text) from public,anon,authenticated;
grant execute on function public.ca_report_listing(uuid,text,text) to authenticated;

revoke all on function ca_private.api_admin_browse_reports(text,integer,integer) from public,anon,authenticated;
grant execute on function ca_private.api_admin_browse_reports(text,integer,integer) to authenticated;
create or replace function public.ca_admin_browse_reports(p_status text,p_page integer,p_page_size integer) returns jsonb language sql security invoker set search_path='' as $api$ select ca_private.api_admin_browse_reports(p_status,p_page,p_page_size); $api$;
revoke all on function public.ca_admin_browse_reports(text,integer,integer) from public,anon,authenticated;
grant execute on function public.ca_admin_browse_reports(text,integer,integer) to authenticated;

revoke all on function ca_private.api_admin_resolve_report(uuid,text,text) from public,anon,authenticated;
grant execute on function ca_private.api_admin_resolve_report(uuid,text,text) to authenticated;
create or replace function public.ca_admin_resolve_report(p_report_id uuid,p_status text,p_note text) returns boolean language sql security invoker set search_path='' as $api$ select ca_private.api_admin_resolve_report(p_report_id,p_status,p_note); $api$;
revoke all on function public.ca_admin_resolve_report(uuid,text,text) from public,anon,authenticated;
grant execute on function public.ca_admin_resolve_report(uuid,text,text) to authenticated;

revoke all on function ca_private.api_save_search(text,jsonb) from public,anon,authenticated;
grant execute on function ca_private.api_save_search(text,jsonb) to authenticated;
create or replace function public.ca_save_search(p_name text,p_filters jsonb) returns uuid language sql security invoker set search_path='' as $api$ select ca_private.api_save_search(p_name,p_filters); $api$;
revoke all on function public.ca_save_search(text,jsonb) from public,anon,authenticated;
grant execute on function public.ca_save_search(text,jsonb) to authenticated;

revoke all on function ca_private.api_list_saved_searches() from public,anon,authenticated;
grant execute on function ca_private.api_list_saved_searches() to authenticated;
create or replace function public.ca_list_saved_searches() returns jsonb language sql security invoker set search_path='' as $api$ select ca_private.api_list_saved_searches(); $api$;
revoke all on function public.ca_list_saved_searches() from public,anon,authenticated;
grant execute on function public.ca_list_saved_searches() to authenticated;

revoke all on function ca_private.api_delete_saved_search(uuid) from public,anon,authenticated;
grant execute on function ca_private.api_delete_saved_search(uuid) to authenticated;
create or replace function public.ca_delete_saved_search(p_id uuid) returns boolean language sql security invoker set search_path='' as $api$ select ca_private.api_delete_saved_search(p_id); $api$;
revoke all on function public.ca_delete_saved_search(uuid) from public,anon,authenticated;
grant execute on function public.ca_delete_saved_search(uuid) to authenticated;

revoke all on function ca_private.api_list_notifications(integer,integer) from public,anon,authenticated;
grant execute on function ca_private.api_list_notifications(integer,integer) to authenticated;
create or replace function public.ca_list_notifications(p_page integer,p_page_size integer) returns jsonb language sql security invoker set search_path='' as $api$ select ca_private.api_list_notifications(p_page,p_page_size); $api$;
revoke all on function public.ca_list_notifications(integer,integer) from public,anon,authenticated;
grant execute on function public.ca_list_notifications(integer,integer) to authenticated;

revoke all on function ca_private.api_mark_notification_read(uuid) from public,anon,authenticated;
grant execute on function ca_private.api_mark_notification_read(uuid) to authenticated;
create or replace function public.ca_mark_notification_read(p_id uuid) returns boolean language sql security invoker set search_path='' as $api$ select ca_private.api_mark_notification_read(p_id); $api$;
revoke all on function public.ca_mark_notification_read(uuid) from public,anon,authenticated;
grant execute on function public.ca_mark_notification_read(uuid) to authenticated;
notify pgrst,'reload schema';
