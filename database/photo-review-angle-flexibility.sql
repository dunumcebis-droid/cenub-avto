-- Allow a trusted vehicle photograph in any gallery slot, regardless of observed angle.
-- Function-only migration: no existing photos, listings, flags or payment rows change.
-- Client access, reviewed-path ownership, quotas and gallery limits remain enforced.
create or replace function public.ca_photo_review_complete(p_review_id uuid,p_owner uuid,p_category text,p_path text,p_sha256 text,p_verdict jsonb)
returns boolean language plpgsql security definer set search_path='' as $$
declare changed uuid;
begin
 if not ca_private.photo_review_allowed(p_owner) then raise exception 'CA_PHOTO_REVIEW_DISABLED';end if;
 if p_owner is null or p_category is null or p_category not in ('front','rear','side','interior','engine','other')
 or p_path is distinct from p_owner::text||'/checked/'||p_review_id::text||'-ca-wm1.jpg'
 or p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'CA_PHOTO_REVIEW_INVALID' using errcode='22023';end if;
 if jsonb_typeof(p_verdict) is distinct from 'object' then raise exception 'CA_PHOTO_REVIEW_INVALID';end if;
 if (select count(*) from jsonb_object_keys(p_verdict))<>4
 or p_verdict->'is_vehicle_photo' is distinct from 'true'::jsonb
 or p_verdict->'contains_screen_ui' is distinct from 'false'::jsonb
 -- The observed view is informational; the caller's gallery slot is independent.
 or jsonb_typeof(p_verdict->'category') is distinct from 'string'
 or coalesce(p_verdict->>'category','') not in ('front','rear','side','interior','engine','other','uncertain')
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

create or replace function ca_private.check_listing_photo_reviews()
returns trigger language plpgsql security definer set search_path='' as $$
declare
 groups jsonb;previous_groups jsonb;group_name text;items jsonb;source jsonb;photo_url text;
 flat_urls text[]:='{}';legacy boolean;oversized boolean;previous_count integer;prefix constant text:='https://iqdtehqxusfiwokrzceo.supabase.co/storage/v1/object/public/elan-sekilleri/';
 categories constant text[]:=array['front','rear','side','interior','engine','other'];
begin
 if not ca_private.photo_review_allowed(new.satici_id) then return new;end if;
 if tg_op='UPDATE' and new.satici_id=old.satici_id and new.sekiller is not distinct from old.sekiller
 and new.ca_data->'photos' is not distinct from old.ca_data->'photos'
 and new.ca_data->'photo' is not distinct from old.ca_data->'photo' then return new;end if;
 groups:=new.ca_data->'photos';
 if jsonb_typeof(groups) is distinct from 'object' then raise exception 'Şəkilləri yenidən seç və yoxlat.' using errcode='23514';end if;
 if exists(select 1 from jsonb_object_keys(groups) k where not(k=any(categories))) then raise exception 'Naməlum şəkil bölməsi.' using errcode='23514';end if;
 if tg_op='UPDATE' then previous_groups:=old.ca_data->'photos';end if;
 foreach group_name in array categories loop
  items:=coalesce(groups->group_name,'[]'::jsonb);
  if jsonb_typeof(items) is distinct from 'array' then raise exception 'Şəkil bölməsi düzgün deyil.' using errcode='23514';end if;
  oversized:=jsonb_array_length(items)>6;
  if oversized then
   if tg_op<>'UPDATE' or new.satici_id<>old.satici_id then
    raise exception 'Hər bölmədə maksimum 6 şəkil ola bilər.' using errcode='23514';
   end if;
   -- Count only this row's previous URLs in the same category. Older galleries
   -- without category metadata have the same implicit 'other' membership used
   -- by the per-URL legacy check below. Reordering/deleting cannot add capacity.
   select count(distinct u) into previous_count from unnest(coalesce(old.sekiller,'{}'::text[])) u
   where coalesce(jsonb_typeof(previous_groups)='object'
      and jsonb_typeof(previous_groups->group_name)='array'
      and (previous_groups->group_name)?u,false)
    or (group_name='other' and not exists(
      select 1 from unnest(categories) c
      where jsonb_typeof(previous_groups->c)='array' and (previous_groups->c)?u));
   if jsonb_array_length(items)>previous_count then
    raise exception 'Hər bölmədə maksimum 6 şəkil ola bilər.' using errcode='23514';
   end if;
  end if;
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
   -- While a legacy category is oversized, even a newly reviewed URL or a
   -- reviewed URL moved from another category must wait until the group is <=6.
   if oversized and not legacy then
    raise exception 'Hər bölmədə maksimum 6 şəkil ola bilər.' using errcode='23514';
   end if;
   if not legacy and not exists(select 1 from ca_private.photo_reviews r
    where r.owner_id=new.satici_id and r.approved and photo_url=prefix||r.path) then
    raise exception 'Şəkil yoxlamadan keçməyib. Şəkli yenidən əlavə et.' using errcode='23514';
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

notify pgrst,'reload schema';
