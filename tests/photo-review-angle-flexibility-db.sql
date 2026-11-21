-- Cross-angle review and cross-slot gallery regression after photo-review-angle-flexibility.sql.
-- Synthetic identities and Storage metadata only; no Auth HTTP, provider calls or file bytes.
-- All fixtures, temporary feature flags and helper functions exist only until ROLLBACK.
-- NEVER replace ROLLBACK with COMMIT.
begin;
create temporary table ca_angle_photo_results(name text primary key);
do $$ begin
 execute format('grant usage on schema %I to anon,authenticated',(select nspname from pg_namespace where oid=pg_my_temp_schema()));
end $$;
grant select,insert on ca_angle_photo_results to authenticated;
create function pg_temp.ca_angle_photo_check(p_name text,p_ok boolean)
returns void language plpgsql security invoker set search_path='' as $$
begin
 if p_ok is distinct from true then raise exception 'FAILED: %',p_name;end if;
 insert into pg_temp.ca_angle_photo_results values(p_name);
end $$;
create function pg_temp.ca_angle_photo_rejected(p_name text,p_sql text,p_state text,p_message text default null)
returns void language plpgsql security invoker set search_path='' as $$
declare blocked boolean:=false;actual_state text;actual_message text;
begin
 begin execute p_sql;
 exception when others then
  get stacked diagnostics actual_state=returned_sqlstate,actual_message=message_text;
  blocked:=actual_state=p_state and (p_message is null or actual_message=p_message);
 end;
 perform pg_temp.ca_angle_photo_check(p_name,blocked);
end $$;
grant execute on function pg_temp.ca_angle_photo_check(text,boolean),pg_temp.ca_angle_photo_rejected(text,text,text,text) to authenticated;

do $test$
declare
 owner_id uuid:=gen_random_uuid();other_owner uuid:=gen_random_uuid();listing_id uuid;
 marker text:='CA_PHOTO_ANGLE_'||gen_random_uuid()::text;
 old_flags jsonb;before_packages bigint;before_users bigint;before_reviews bigint;before_listings bigint;
 review_ids uuid[]:='{}';paths text[]:='{}';urls text[]:='{}';fixture_owner uuid;
 requested_slots text[]:=array['front','side','rear','front','front'];
 observed_views text[]:=array['rear','front','uncertain','rear','front'];
 prefix constant text:='https://iqdtehqxusfiwokrzceo.supabase.co/storage/v1/object/public/elan-sekilleri/';
 verdict_value jsonb;payload jsonb;gallery text[];case_name text;path_value text;missing_id uuid;missing_path text;foreign_path text;
 affected integer;i integer;
begin
 select count(*) into before_packages from public.paket_sorgulari;
 select count(*) into before_users from auth.users;
 select count(*) into before_reviews from ca_private.photo_reviews;
 select count(*) into before_listings from public.elanlar;
 select to_jsonb(c) into old_flags from ca_private.photo_review_config c where singleton;
 if old_flags is null then raise exception 'SETUP: photo review configuration missing';end if;
 insert into auth.users(id,email,aud,role,raw_app_meta_data,raw_user_meta_data,created_at,updated_at) values
 (owner_id,'ca-angle-'||owner_id::text||'@fixture.invalid','authenticated','authenticated','{}','{}',now(),now()),
 (other_owner,'ca-angle-'||other_owner::text||'@fixture.invalid','authenticated','authenticated','{}','{}',now(),now());
 update ca_private.photo_review_config set enabled=true,admin_preview=false where singleton;
 for i in 1..5 loop
  fixture_owner:=case when i=4 then other_owner else owner_id end;
  review_ids:=array_append(review_ids,public.ca_photo_review_reserve(fixture_owner));
  path_value:=fixture_owner::text||'/checked/'||review_ids[i]::text||'-ca-wm1.jpg';
  paths:=array_append(paths,path_value);urls:=array_append(urls,prefix||path_value);
  insert into storage.objects(bucket_id,name,metadata)
   values('elan-sekilleri',path_value,'{"mimetype":"image/jpeg","size":100}'::jsonb);
 end loop;
 for i in 1..4 loop
  fixture_owner:=case when i=4 then other_owner else owner_id end;
  verdict_value:=jsonb_build_object('is_vehicle_photo',true,'contains_screen_ui',false,'category',observed_views[i],'confidence',0.95);
  if public.ca_photo_review_complete(review_ids[i],fixture_owner,requested_slots[i],paths[i],repeat('a',64),verdict_value) is distinct from true then
   raise exception 'FAILED: cross-angle completion %',i;
  end if;
  perform pg_temp.ca_angle_photo_check(case i
   when 1 then 'rear_view_completes_in_front_slot'
   when 2 then 'front_view_completes_in_side_slot'
   when 3 then 'uncertain_angle_genuine_photo_completes'
   else 'foreign_owner_has_own_independent_proof' end,
   exists(select 1 from ca_private.photo_reviews r where r.id=review_ids[i] and r.owner_id=fixture_owner and r.approved
    and r.category=requested_slots[i] and r.verdict=verdict_value));
 end loop;
 verdict_value:='{"is_vehicle_photo":true,"contains_screen_ui":false,"category":"rear","confidence":0.95}'::jsonb;
 perform pg_temp.ca_angle_photo_check('cross_angle_completion_remains_idempotent',
  public.ca_photo_review_complete(review_ids[1],owner_id,'front',paths[1],repeat('a',64),verdict_value));
 perform pg_temp.ca_angle_photo_rejected('completed_proof_hash_immutable',format(
  'select public.ca_photo_review_complete(%L::uuid,%L::uuid,''front'',%L,%L,%L::jsonb)',review_ids[1],owner_id,paths[1],repeat('b',64),verdict_value),'P0001','CA_PHOTO_REVIEW_NOT_RESERVED');

 -- Angle flexibility must never weaken the trusted photographic-content verdict.
 foreach case_name in array array['screenshot','non_vehicle','not_vehicle_category','unknown_category','missing_category','null_category','numeric_category','low_confidence','excess_confidence','null_confidence','extra_field','missing_photo_indicator'] loop
  payload:=case case_name
   when 'screenshot' then jsonb_set(verdict_value,'{contains_screen_ui}','true')
   when 'non_vehicle' then jsonb_set(verdict_value,'{is_vehicle_photo}','false')
   when 'not_vehicle_category' then jsonb_set(verdict_value,'{category}','"not_vehicle"')
   when 'unknown_category' then jsonb_set(verdict_value,'{category}','"untrusted"')
   when 'missing_category' then verdict_value-'category'
   when 'null_category' then jsonb_set(verdict_value,'{category}','null')
   when 'numeric_category' then jsonb_set(verdict_value,'{category}','42')
   when 'low_confidence' then jsonb_set(verdict_value,'{confidence}','0.84')
   when 'excess_confidence' then jsonb_set(verdict_value,'{confidence}','1.01')
   when 'null_confidence' then jsonb_set(verdict_value,'{confidence}','null')
   when 'extra_field' then verdict_value||'{"approved":true}'::jsonb
   else verdict_value-'is_vehicle_photo' end;
  perform pg_temp.ca_angle_photo_rejected('verdict_rejects_'||case_name,format(
   'select public.ca_photo_review_complete(%L::uuid,%L::uuid,''front'',%L,%L,%L::jsonb)',review_ids[5],owner_id,paths[5],repeat('a',64),payload),'P0001','CA_PHOTO_REVIEW_INVALID');
 end loop;
 perform pg_temp.ca_angle_photo_rejected('requested_slot_still_validated',format(
  'select public.ca_photo_review_complete(%L::uuid,%L::uuid,''bogus'',%L,%L,%L::jsonb)',review_ids[5],owner_id,paths[5],repeat('a',64),verdict_value),'22023','CA_PHOTO_REVIEW_INVALID');
 perform pg_temp.ca_angle_photo_rejected('review_path_must_match_owner_and_reservation',format(
  'select public.ca_photo_review_complete(%L::uuid,%L::uuid,''front'',%L,%L,%L::jsonb)',review_ids[5],owner_id,paths[4],repeat('a',64),verdict_value),'22023','CA_PHOTO_REVIEW_INVALID');
 foreign_path:=other_owner::text||'/checked/'||review_ids[5]::text||'-ca-wm1.jpg';
 insert into storage.objects(bucket_id,name,metadata) values('elan-sekilleri',foreign_path,'{"mimetype":"image/jpeg","size":100}'::jsonb);
 perform pg_temp.ca_angle_photo_rejected('reservation_cannot_be_completed_for_other_owner',format(
  'select public.ca_photo_review_complete(%L::uuid,%L::uuid,''front'',%L,%L,%L::jsonb)',review_ids[5],other_owner,foreign_path,repeat('a',64),verdict_value),'P0001','CA_PHOTO_REVIEW_NOT_RESERVED');
 missing_id:=public.ca_photo_review_reserve(owner_id);
 missing_path:=owner_id::text||'/checked/'||missing_id::text||'-ca-wm1.jpg';
 perform pg_temp.ca_angle_photo_rejected('completion_still_requires_storage_object',format(
  'select public.ca_photo_review_complete(%L::uuid,%L::uuid,''front'',%L,%L,%L::jsonb)',missing_id,owner_id,missing_path,repeat('a',64),verdict_value),'P0001','CA_PHOTO_REVIEW_OBJECT_MISSING');
 update ca_private.photo_reviews set created_at=clock_timestamp()-interval '20 minutes' where id=review_ids[5];
 perform pg_temp.ca_angle_photo_rejected('expired_reservation_still_denied',format(
  'select public.ca_photo_review_complete(%L::uuid,%L::uuid,''front'',%L,%L,%L::jsonb)',review_ids[5],owner_id,paths[5],repeat('a',64),verdict_value),'P0001','CA_PHOTO_REVIEW_NOT_RESERVED');

 perform pg_temp.ca_angle_photo_check('service_completion_only',
  has_function_privilege('service_role','public.ca_photo_review_complete(uuid,uuid,text,text,text,jsonb)','EXECUTE')
  and not has_function_privilege('anon','public.ca_photo_review_complete(uuid,uuid,text,text,text,jsonb)','EXECUTE')
  and not has_function_privilege('authenticated','public.ca_photo_review_complete(uuid,uuid,text,text,text,jsonb)','EXECUTE'));
 perform pg_temp.ca_angle_photo_check('proof_tables_still_private',
  not has_table_privilege('anon','ca_private.photo_reviews','SELECT,INSERT,UPDATE,DELETE')
  and not has_table_privilege('authenticated','ca_private.photo_reviews','SELECT,INSERT,UPDATE,DELETE')
  and not has_table_privilege('authenticated','ca_private.photo_review_config','SELECT,UPDATE'));
 perform set_config('request.jwt.claim.sub',owner_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',owner_id,'role','authenticated')::text,true);
 perform set_config('role','authenticated',true);
 gallery:=array[urls[1],urls[2],urls[3]];
 payload:=jsonb_build_object('photos',jsonb_build_object('rear',jsonb_build_array(urls[1]),'front',jsonb_build_array(urls[2]),'side',jsonb_build_array(urls[3])),'photo',urls[2]);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
 values(owner_id,marker,'Any observed view and slot',2020,100,'gozlemede',gallery,payload) returning id into listing_id;
 perform pg_temp.ca_angle_photo_check('owned_reviewed_photos_create_listing_in_different_slots',listing_id is not null
  and exists(select 1 from public.elanlar where id=listing_id and ca_data->'photos'=payload->'photos' and veziyyet='gozlemede'));
 payload:=jsonb_build_object('photos',jsonb_build_object('engine',to_jsonb(gallery)),'photo',urls[3]);
 update public.elanlar set ca_data=payload where id=listing_id;
 get diagnostics affected=row_count;
 perform pg_temp.ca_angle_photo_check('owned_reviewed_photos_move_between_allowed_slots',affected=1
  and exists(select 1 from public.elanlar where id=listing_id and ca_data->'photos'->'engine'=to_jsonb(gallery)));
 foreach case_name in array array['other_owner','unreviewed','forged_approval','altered_proof_url','unknown_group','nonarray_group','duplicate_group_url','gallery_mismatch','cover_mismatch','empty_gallery','oversized_group'] loop
  gallery:=array[urls[1],urls[2],urls[3]];
  payload:=jsonb_build_object('photos',jsonb_build_object('engine',to_jsonb(gallery)),'photo',urls[3]);
  case case_name
   when 'other_owner' then gallery:=array[urls[4]];payload:=jsonb_build_object('photos',jsonb_build_object('side',to_jsonb(gallery)),'photo',urls[4]);
   when 'unreviewed' then gallery:=array[urls[5]];payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(gallery)),'photo',urls[5]);
   when 'forged_approval' then gallery:=array[urls[5]];payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(gallery)),'photo',urls[5],'photo_review',jsonb_build_object('approved',true,'review_id',review_ids[5]));
   when 'altered_proof_url' then gallery:=array[urls[1]||'?forged=1'];payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(gallery)),'photo',gallery[1]);
   when 'unknown_group' then payload:=jsonb_set(payload,'{photos}',jsonb_build_object('unknown',to_jsonb(gallery)));
   when 'nonarray_group' then payload:=jsonb_set(payload,'{photos,engine}','42');
   when 'duplicate_group_url' then gallery:=array[urls[1],urls[1]];payload:=jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(urls[1]),'rear',jsonb_build_array(urls[1])),'photo',urls[1]);
   when 'gallery_mismatch' then gallery:=array[urls[1],urls[2]];
   when 'cover_mismatch' then payload:=jsonb_set(payload,'{photo}',to_jsonb(urls[4]));
   when 'empty_gallery' then gallery:='{}'::text[];payload:='{"photos":{}}'::jsonb;
   when 'oversized_group' then gallery:=array_fill(urls[1],array[7]);payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(gallery)),'photo',urls[1]);
  end case;
  perform pg_temp.ca_angle_photo_rejected('listing_rejects_'||case_name,format(
   'update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L::uuid',gallery,payload,listing_id),'23514');
 end loop;
 perform pg_temp.ca_angle_photo_rejected('browser_cannot_complete_own_proof',format(
  'select public.ca_photo_review_complete(%L::uuid,%L::uuid,''front'',%L,%L,%L::jsonb)',review_ids[5],owner_id,paths[5],repeat('a',64),verdict_value),'42501');
 perform set_config('request.jwt.claim.sub',other_owner::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',other_owner,'role','authenticated')::text,true);
 begin update public.elanlar set qiymet=999 where id=listing_id;get diagnostics affected=row_count;
 exception when insufficient_privilege then affected:=0;end;
 perform pg_temp.ca_angle_photo_check('other_owner_cannot_edit_listing',affected=0);
 perform set_config('role','none',true);
 perform pg_temp.ca_angle_photo_check('review_fixtures_unapproved_after_rejections',
  exists(select 1 from ca_private.photo_reviews where id=review_ids[5] and not approved));
 perform pg_temp.ca_angle_photo_check('only_synthetic_auth_rows_added',(select count(*)=before_users+2 from auth.users));
 perform pg_temp.ca_angle_photo_check('only_synthetic_listing_added',(select count(*)=before_listings+1 from public.elanlar));
 perform pg_temp.ca_angle_photo_check('only_synthetic_reviews_added',(select count(*)=before_reviews+6 from ca_private.photo_reviews));
 perform pg_temp.ca_angle_photo_check('payment_rows_unchanged',(select count(*)=before_packages from public.paket_sorgulari));
 update ca_private.photo_review_config set enabled=(old_flags->>'enabled')::boolean,admin_preview=(old_flags->>'admin_preview')::boolean where singleton;
 perform pg_temp.ca_angle_photo_check('photo_review_flags_restored',(select to_jsonb(c)=old_flags from ca_private.photo_review_config c where singleton));
end $test$;
select count(*) passed_count,array_agg(name order by name) passed_tests from ca_angle_photo_results;
rollback;
