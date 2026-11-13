-- Trusted photograph review. Inactive until a configured provider is tested.
-- Existing vehicle rows, images and packages are never rewritten.
create table if not exists ca_private.photo_review_config (
 singleton boolean primary key default true check(singleton),
 enabled boolean not null default false
);
insert into ca_private.photo_review_config(singleton,enabled) values(true,false) on conflict(singleton) do nothing;
create table if not exists ca_private.photo_reviews (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default clock_timestamp(),
 completed_at timestamptz,
 category text check(category in ('front','rear','side','interior','engine','other')),
 path text unique,
 sha256 text check(sha256 ~ '^[0-9a-f]{64}$'),
 verdict jsonb,
 approved boolean not null default false
);
create index if not exists ca_photo_review_owner_time on ca_private.photo_reviews(owner_id,created_at desc);
alter table ca_private.photo_review_config enable row level security;
alter table ca_private.photo_reviews enable row level security;
-- Explicit service-only policies; no client grants and no exposed schema.
do $private_policies$
begin
 if not exists(select 1 from pg_policies where schemaname='ca_private' and tablename='photo_reviews' and policyname='service_only_photo_reviews') then
  create policy service_only_photo_reviews on ca_private.photo_reviews for all to service_role using(true) with check(true);
 end if;
 if not exists(select 1 from pg_policies where schemaname='ca_private' and tablename='photo_review_config' and policyname='service_only_photo_config') then
  create policy service_only_photo_config on ca_private.photo_review_config for all to service_role using(true) with check(true);
 end if;
end $private_policies$;
revoke all on ca_private.photo_review_config,ca_private.photo_reviews from public,anon,authenticated;

create or replace function public.ca_photo_review_service_status()
returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('enabled',coalesce((select enabled from ca_private.photo_review_config where singleton),false));
$$;
revoke all on function public.ca_photo_review_service_status() from public,anon,authenticated;
grant execute on function public.ca_photo_review_service_status() to service_role;

create or replace function public.ca_photo_review_reserve(p_owner uuid)
returns uuid language plpgsql security definer set search_path='' as $$
declare result uuid;
begin
 if p_owner is null or not exists(select 1 from auth.users where id=p_owner) then raise exception 'CA_PHOTO_REVIEW_OWNER' using errcode='22023';end if;
 if not coalesce((select enabled from ca_private.photo_review_config where singleton),false) then raise exception 'CA_PHOTO_REVIEW_DISABLED';end if;
 perform pg_advisory_xact_lock(hashtextextended('ca_photo_review:'||p_owner::text,0));
 if (select count(*) from ca_private.photo_reviews where owner_id=p_owner and created_at>clock_timestamp()-interval '10 minutes')>=120
 or (select count(*) from ca_private.photo_reviews where owner_id=p_owner and created_at>clock_timestamp()-interval '1 day')>=2000 then
  raise exception 'CA_PHOTO_REVIEW_RATE_LIMIT';
 end if;
 insert into ca_private.photo_reviews(owner_id) values(p_owner) returning id into result;
 return result;
end $$;
revoke all on function public.ca_photo_review_reserve(uuid) from public,anon,authenticated;
grant execute on function public.ca_photo_review_reserve(uuid) to service_role;

create or replace function public.ca_photo_review_complete(p_review_id uuid,p_owner uuid,p_category text,p_path text,p_sha256 text,p_verdict jsonb)
returns boolean language plpgsql security definer set search_path='' as $$
declare changed uuid;
begin
 if not coalesce((select enabled from ca_private.photo_review_config where singleton),false) then raise exception 'CA_PHOTO_REVIEW_DISABLED';end if;
 if p_owner is null or p_category is null or p_category not in ('front','rear','side','interior','engine','other')
 or p_path is distinct from p_owner::text||'/checked/'||p_review_id::text||'-ca-wm1.jpg'
 or p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'CA_PHOTO_REVIEW_INVALID' using errcode='22023';end if;
 if jsonb_typeof(p_verdict) is distinct from 'object' then raise exception 'CA_PHOTO_REVIEW_INVALID';end if;
 if (select count(*) from jsonb_object_keys(p_verdict))<>4
 or p_verdict->'is_vehicle_photo' is distinct from 'true'::jsonb
 or p_verdict->'contains_screen_ui' is distinct from 'false'::jsonb
 or p_verdict->>'category' is distinct from p_category
 or jsonb_typeof(p_verdict->'confidence') is distinct from 'number' then raise exception 'CA_PHOTO_REVIEW_INVALID';end if;
 if (p_verdict->>'confidence')::numeric<0.85 or (p_verdict->>'confidence')::numeric>1 then raise exception 'CA_PHOTO_REVIEW_INVALID';end if;
 if not exists(select 1 from storage.objects where bucket_id='elan-sekilleri' and name=p_path) then raise exception 'CA_PHOTO_REVIEW_OBJECT_MISSING';end if;
 update ca_private.photo_reviews set category=p_category,path=p_path,sha256=p_sha256,verdict=p_verdict,approved=true,completed_at=clock_timestamp()
 where id=p_review_id and owner_id=p_owner and not approved and created_at>clock_timestamp()-interval '15 minutes' returning id into changed;
 if changed is null and not exists(select 1 from ca_private.photo_reviews where id=p_review_id and owner_id=p_owner and approved and category=p_category and path=p_path and sha256=p_sha256) then
  raise exception 'CA_PHOTO_REVIEW_NOT_RESERVED';
 end if;
 return true;
end $$;
revoke all on function public.ca_photo_review_complete(uuid,uuid,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.ca_photo_review_complete(uuid,uuid,text,text,text,jsonb) to service_role;

-- Proof refers to immutable bytes. Client uploads/deletes cannot touch this namespace.
do $policies$
begin
 if not exists(select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='ca_reviewed_photos_no_client_insert') then
  create policy ca_reviewed_photos_no_client_insert on storage.objects as restrictive for insert to authenticated
  with check(bucket_id<>'elan-sekilleri' or split_part(name,'/',2)<>'checked');
 end if;
 if not exists(select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='ca_reviewed_photos_no_client_update') then
  create policy ca_reviewed_photos_no_client_update on storage.objects as restrictive for update to authenticated
  using(bucket_id<>'elan-sekilleri' or split_part(name,'/',2)<>'checked')
  with check(bucket_id<>'elan-sekilleri' or split_part(name,'/',2)<>'checked');
 end if;
 if not exists(select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='ca_reviewed_photos_no_client_delete') then
  create policy ca_reviewed_photos_no_client_delete on storage.objects as restrictive for delete to authenticated
  using(bucket_id<>'elan-sekilleri' or split_part(name,'/',2)<>'checked');
 end if;
end $policies$;

create or replace function ca_private.check_listing_photo_reviews()
returns trigger language plpgsql security definer set search_path='' as $$
declare
 groups jsonb;previous_groups jsonb;group_name text;items jsonb;source jsonb;photo_url text;
 flat_urls text[]:='{}';legacy boolean;prefix constant text:='https://iqdtehqxusfiwokrzceo.supabase.co/storage/v1/object/public/elan-sekilleri/';
 categories constant text[]:=array['front','rear','side','interior','engine','other'];
begin
 if not coalesce((select enabled from ca_private.photo_review_config where singleton),false) then return new;end if;
 if tg_op='UPDATE' and new.satici_id=old.satici_id and new.sekiller is not distinct from old.sekiller
 and new.ca_data->'photos' is not distinct from old.ca_data->'photos'
 and new.ca_data->'photo' is not distinct from old.ca_data->'photo' then return new;end if;
 groups:=new.ca_data->'photos';
 if jsonb_typeof(groups) is distinct from 'object' then raise exception 'Şəkilləri uyğun bölmələr üzrə yenidən seç və yoxlat.' using errcode='23514';end if;
 if exists(select 1 from jsonb_object_keys(groups) k where not(k=any(categories))) then raise exception 'Naməlum şəkil bölməsi.' using errcode='23514';end if;
 if tg_op='UPDATE' then previous_groups:=old.ca_data->'photos';end if;
 foreach group_name in array categories loop
  items:=coalesce(groups->group_name,'[]'::jsonb);
  if jsonb_typeof(items) is distinct from 'array' then raise exception 'Şəkil bölməsi düzgün deyil.' using errcode='23514';end if;
  if jsonb_array_length(items)>6 and not(tg_op='UPDATE' and items is not distinct from previous_groups->group_name) then raise exception 'Hər bölmədə maksimum 6 şəkil ola bilər.' using errcode='23514';end if;
  for source in select value from jsonb_array_elements(items) loop
   if jsonb_typeof(source)<>'string' then raise exception 'Şəkil keçidi düzgün deyil.' using errcode='23514';end if;
   photo_url:=source#>>'{}';
   if photo_url='' then raise exception 'Boş şəkil keçidi.' using errcode='23514';end if;
   flat_urls:=array_append(flat_urls,photo_url);
   legacy:=false;
   if tg_op='UPDATE' and new.satici_id=old.satici_id and photo_url=any(coalesce(old.sekiller,'{}'::text[])) then
    -- Exactly the old row and group. Ungrouped old storage photos render as 'other'.
    legacy:=coalesce(jsonb_typeof(previous_groups)='object' and jsonb_typeof(previous_groups->group_name)='array' and (previous_groups->group_name)?photo_url,false);
    if not legacy and group_name='other' then
     legacy:=not exists(select 1 from unnest(categories) c where jsonb_typeof(previous_groups->c)='array' and (previous_groups->c)?photo_url);
    end if;
   end if;
   if not legacy and not exists(select 1 from ca_private.photo_reviews r
    where r.owner_id=new.satici_id and r.approved and r.category=group_name and photo_url=prefix||r.path) then
    raise exception 'Şəkil seçilən bölmə üçün yoxlamadan keçməyib. Uyğun şəkli yenidən əlavə et.' using errcode='23514';
   end if;
  end loop;
 end loop;
 if cardinality(flat_urls)<1 then raise exception 'Ən azı 1 yoxlanmış şəkil lazımdır.' using errcode='23514';end if;
 if cardinality(flat_urls)>36 and not(tg_op='UPDATE' and cardinality(flat_urls)<=coalesce(cardinality(old.sekiller),0)) then raise exception 'Maksimum 36 şəkil ola bilər.' using errcode='23514';end if;
 if cardinality(flat_urls)<>(select count(distinct u) from unnest(flat_urls) u) then raise exception 'Eyni şəkli bir neçə dəfə əlavə etmə.' using errcode='23514';end if;
 if cardinality(flat_urls) is distinct from cardinality(new.sekiller)
 or exists(select 1 from unnest(flat_urls) u where not(u=any(new.sekiller))) then raise exception 'Şəkil bölmələri və qalereya uyğun gəlmir.' using errcode='23514';end if;
 if new.ca_data->>'photo' is not null and not((new.ca_data->>'photo')=any(flat_urls)) then raise exception 'Əsas şəkil yoxlanmış şəkillərdən seçilməlidir.' using errcode='23514';end if;
 return new;
end $$;
revoke all on function ca_private.check_listing_photo_reviews() from public,anon,authenticated;
do $trigger$
begin
 if not exists(select 1 from pg_trigger where tgname='ca_check_listing_photo_reviews' and tgrelid='public.elanlar'::regclass) then
  create trigger ca_check_listing_photo_reviews before insert or update on public.elanlar
  for each row execute function ca_private.check_listing_photo_reviews();
 end if;
end $trigger$;
notify pgrst,'reload schema';
