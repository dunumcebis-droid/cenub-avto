-- Run after database/photo-manager-legacy-subsets.sql.
-- Synthetic metadata only; no files, account API, HTTP or emails are created.
-- If needed one random fixture.invalid Auth row exists ONLY until ROLLBACK.
-- Existing rows and feature flags are preserved; NEVER replace ROLLBACK with COMMIT.
begin;
create temporary table ca_legacy_photo_results(name text primary key);
do $$ begin
 execute format('grant usage on schema %I to anon,authenticated',(select nspname from pg_namespace where oid=pg_my_temp_schema()));
end $$;
grant select,insert on ca_legacy_photo_results to authenticated;
create function pg_temp.ca_legacy_photo_check(p_name text,p_ok boolean)
returns void language plpgsql security invoker set search_path='' as $$
begin
 if p_ok is distinct from true then raise exception 'FAILED: %',p_name;end if;
 insert into pg_temp.ca_legacy_photo_results values(p_name);
end $$;
create function pg_temp.ca_legacy_photo_blocked(p_name text,p_sql text)
returns void language plpgsql security invoker set search_path='' as $$
declare blocked boolean:=false;
begin
 begin execute p_sql;exception when check_violation then blocked:=true;end;
 perform pg_temp.ca_legacy_photo_check(p_name,blocked);
end $$;
grant execute on function pg_temp.ca_legacy_photo_check(text,boolean),pg_temp.ca_legacy_photo_blocked(text,text) to authenticated;

do $test$
declare
 owner_id uuid;other_owner uuid;group_id uuid;ungrouped_id uuid;over36_id uuid;normal_id uuid;
 marker text:='CA_LEGACY_PHOTO_'||gen_random_uuid()::text;
 old_flags jsonb;before_packages bigint;before_reviews bigint;
 before_auth_users bigint;synthetic_owner boolean:=false;
 front_urls text[];ungrouped_urls text[];over36_urls text[];reordered text[];gallery text[];
 front_new text;rear_moved text;foreign_url text;proof_id uuid;path_value text;payload jsonb;groups_value jsonb;affected integer;i integer;
 prefix constant text:='https://iqdtehqxusfiwokrzceo.supabase.co/storage/v1/object/public/elan-sekilleri/';
begin
 select count(*) into before_auth_users from auth.users;
 select u.id into owner_id from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) order by u.created_at,u.id limit 1;
 select u.id into other_owner from auth.users u where u.id<>owner_id and not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) order by u.created_at,u.id limit 1;
 if owner_id is null then raise exception 'SETUP: existing nonadmin identity required';end if;
 if other_owner is null then
  other_owner:=gen_random_uuid();synthetic_owner:=true;
  insert into auth.users(id,email,aud,role,raw_app_meta_data,raw_user_meta_data,created_at,updated_at)
  values(other_owner,'ca-photo-rollback-'||other_owner::text||'@fixture.invalid','authenticated','authenticated','{}','{}',now(),now());
 end if;
 select to_jsonb(c) into old_flags from ca_private.photo_review_config c where singleton;
 select count(*) into before_packages from public.paket_sorgulari;
 select count(*) into before_reviews from ca_private.photo_reviews;
 update ca_private.photo_review_config set enabled=false,admin_preview=false where singleton;
 select array_agg('https://fixture.invalid/'||marker||'/front-'||n||'.jpg' order by n) into front_urls from generate_series(1,8)n;
 select array_agg('https://fixture.invalid/'||marker||'/ungrouped-'||n||'.jpg' order by n) into ungrouped_urls from generate_series(1,36)n;
 select array_agg('https://fixture.invalid/'||marker||'/over36-'||n||'.jpg' order by n) into over36_urls from generate_series(1,40)n;
 -- Proof fixtures are private metadata, rolled back without creating stored bytes.
 for i in 1..3 loop
  proof_id:=gen_random_uuid();
  path_value:=(case when i=3 then other_owner else owner_id end)::text||'/checked/'||proof_id::text||'-ca-wm1.jpg';
  insert into ca_private.photo_reviews(id,owner_id,category,path,sha256,approved,completed_at,verdict)
   values(proof_id,case when i=3 then other_owner else owner_id end,'front',path_value,repeat('a',64),true,now(),'{"is_vehicle_photo":true,"contains_screen_ui":false,"category":"front","confidence":0.95}');
  if i=1 then front_new:=prefix||path_value;elsif i=2 then rear_moved:=prefix||path_value;else foreign_url:=prefix||path_value;end if;
 end loop;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
 values(owner_id,marker,'Oversized grouped',2020,100,'gozlemede',front_urls||array[rear_moved],jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls),'rear',jsonb_build_array(rear_moved)),'photo',front_urls[1])) returning id into group_id;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
 values(owner_id,marker,'Ungrouped legacy',2020,100,'gozlemede',ungrouped_urls,'{}') returning id into ungrouped_id;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
 values(owner_id,marker,'Old over 36',2020,100,'gozlemede',over36_urls,jsonb_build_object('photos',jsonb_build_object('other',to_jsonb(over36_urls)),'photo',over36_urls[1])) returning id into over36_id;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
 values(owner_id,marker,'Normal category',2020,100,'gozlemede',front_urls[1:5],jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls[1:5])),'photo',front_urls[1])) returning id into normal_id;
 update ca_private.photo_review_config set enabled=true,admin_preview=false where singleton;
 perform set_config('request.jwt.claim.sub',owner_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',owner_id,'role','authenticated')::text,true);
 perform set_config('role','authenticated',true);

 select array_agg(u order by ordinal desc) into reordered from unnest(front_urls) with ordinality t(u,ordinal);
 update public.elanlar set sekiller=reordered||array[rear_moved],ca_data=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered),'rear',jsonb_build_array(rear_moved)),'photo',reordered[1]) where id=group_id;
 get diagnostics affected=row_count;
 perform pg_temp.ca_legacy_photo_check('oversized_group_reorder_and_cover_succeeds',affected=1 and exists(select 1 from public.elanlar where id=group_id and sekiller=reordered||array[rear_moved] and ca_data->>'photo'=reordered[1]));

 gallery:=reordered||array[front_new,rear_moved];
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered||array[front_new]),'rear',jsonb_build_array(rear_moved)),'photo',reordered[1]);
 perform pg_temp.ca_legacy_photo_blocked('oversized_group_cannot_grow_even_with_valid_proof',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',gallery,payload,group_id));
 gallery:=reordered[1:7]||array[front_new,rear_moved];
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered[1:7]||array[front_new]),'rear',jsonb_build_array(rear_moved)),'photo',reordered[1]);
 perform pg_temp.ca_legacy_photo_blocked('oversized_group_cannot_replace_old_url_even_with_valid_proof',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',gallery,payload,group_id));
 gallery:=reordered[1:7]||array[rear_moved];
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(gallery)),'photo',reordered[1]);
 perform pg_temp.ca_legacy_photo_blocked('oversized_group_cannot_import_reviewed_url_from_another_category',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',gallery,payload,group_id));

 reordered:=reordered[1:7];
 update public.elanlar set sekiller=reordered||array[rear_moved],ca_data=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered),'rear',jsonb_build_array(rear_moved)),'photo',reordered[1]) where id=group_id;
 get diagnostics affected=row_count;
 perform pg_temp.ca_legacy_photo_check('oversized_group_single_delete_8_to7_succeeds',affected=1);
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered||array[front_urls[1]]),'rear',jsonb_build_array(rear_moved)),'photo',reordered[1]);
 perform pg_temp.ca_legacy_photo_blocked('deleted_url_cannot_be_reintroduced_while_oversized',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',reordered||array[front_urls[1],rear_moved],payload,group_id));
 reordered:=reordered[1:6];
 update public.elanlar set sekiller=reordered||array[rear_moved],ca_data=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered),'rear',jsonb_build_array(rear_moved)),'photo',reordered[1]) where id=group_id;
 get diagnostics affected=row_count;
 perform pg_temp.ca_legacy_photo_check('oversized_group_can_return_to_normal_limit',affected=1);
 reordered:=reordered[1:5];
 update public.elanlar set sekiller=reordered||array[rear_moved],ca_data=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered),'rear',jsonb_build_array(rear_moved)),'photo',reordered[1]) where id=group_id;
 update public.elanlar set sekiller=reordered||array[front_new,rear_moved],ca_data=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered||array[front_new]),'rear',jsonb_build_array(rear_moved)),'photo',front_new) where id=group_id;
 get diagnostics affected=row_count;
 perform pg_temp.ca_legacy_photo_check('normal_group_still_accepts_same_owner_same_category_reviewed_photo',affected=1);

 -- Legacy galleries lacking categories retain their implicit 'other' identity.
 select array_agg(u order by ordinal desc) into reordered from unnest(ungrouped_urls) with ordinality t(u,ordinal);
 update public.elanlar set sekiller=reordered,ca_data=jsonb_build_object('photos',jsonb_build_object('other',to_jsonb(reordered)),'photo',reordered[1]) where id=ungrouped_id;
 get diagnostics affected=row_count;
 perform pg_temp.ca_legacy_photo_check('ungrouped36_can_materialize_other_and_reorder',affected=1);
 reordered:=reordered[1:35];
 update public.elanlar set sekiller=reordered,ca_data=jsonb_build_object('photos',jsonb_build_object('other',to_jsonb(reordered)),'photo',reordered[1]) where id=ungrouped_id;
 get diagnostics affected=row_count;
 perform pg_temp.ca_legacy_photo_check('ungrouped36_can_delete_one_photo',affected=1);
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(reordered)),'photo',reordered[1]);
 perform pg_temp.ca_legacy_photo_blocked('ungrouped_legacy_cannot_change_category',format('update public.elanlar set ca_data=%L::jsonb where id=%L',payload,ungrouped_id));
 update public.elanlar set sekiller=over36_urls[1:39],ca_data=jsonb_build_object('photos',jsonb_build_object('other',to_jsonb(over36_urls[1:39])),'photo',over36_urls[1]) where id=over36_id;
 get diagnostics affected=row_count;
 perform pg_temp.ca_legacy_photo_check('old_total_over36_can_shrink',affected=1);

 -- The rest of the trusted-photo boundary must remain unchanged.
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls[1:5]||array['https://fixture.invalid/new-unreviewed.jpg'])),'photo',front_urls[1]);
 perform pg_temp.ca_legacy_photo_blocked('new_unreviewed_photo_still_denied',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',front_urls[1:5]||array['https://fixture.invalid/new-unreviewed.jpg'],payload,normal_id));
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls[1:5]||array[foreign_url])),'photo',front_urls[1]);
 perform pg_temp.ca_legacy_photo_blocked('other_owner_proof_still_denied',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',front_urls[1:5]||array[foreign_url],payload,normal_id));
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls[1:5]),'rear',jsonb_build_array(front_new)),'photo',front_urls[1]);
 perform pg_temp.ca_legacy_photo_blocked('wrong_category_proof_still_denied',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',front_urls[1:5]||array[front_new],payload,normal_id));
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls[1:5]||array[front_urls[1]])),'photo',front_urls[1]);
 perform pg_temp.ca_legacy_photo_blocked('duplicate_url_still_denied',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',front_urls[1:5]||array[front_urls[1]],payload,normal_id));
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls[1:5])),'photo',front_new);
 perform pg_temp.ca_legacy_photo_blocked('cover_outside_gallery_still_denied',format('update public.elanlar set ca_data=%L::jsonb where id=%L',payload,normal_id));
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls[1:5])),'photo',front_urls[1]);
 perform pg_temp.ca_legacy_photo_blocked('gallery_category_mismatch_still_denied',format('update public.elanlar set sekiller=%L::text[],ca_data=%L::jsonb where id=%L',front_urls[1:4],payload,normal_id));
 perform pg_temp.ca_legacy_photo_blocked('empty_gallery_still_denied',format('update public.elanlar set sekiller=''{}''::text[],ca_data=''{"photos":{}}''::jsonb where id=%L',normal_id));
 payload:=jsonb_build_object('photos',jsonb_build_object('front',to_jsonb(front_urls[1:7])),'photo',front_urls[1]);
 perform pg_temp.ca_legacy_photo_blocked('new_listing_cannot_use_oversized_category',format('insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data) values(%L,%L,''New oversized'',2020,100,''gozlemede'',%L::text[],%L::jsonb)',owner_id,marker,front_urls[1:7],payload));

 perform set_config('request.jwt.claim.sub',other_owner::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',other_owner,'role','authenticated')::text,true);
 begin update public.elanlar set qiymet=999 where id=group_id;get diagnostics affected=row_count;exception when insufficient_privilege then affected:=0;end;
 perform pg_temp.ca_legacy_photo_check('other_owner_cannot_edit_legacy_listing',affected=0);
 perform set_config('role','none',true);
 perform pg_temp.ca_legacy_photo_check('all_photo_fixtures_remain_pending',not exists(select 1 from public.elanlar where id in(group_id,ungrouped_id,over36_id,normal_id) and veziyyet<>'gozlemede'));
 perform pg_temp.ca_legacy_photo_check('payment_rows_unchanged',(select count(*)=before_packages from public.paket_sorgulari));
 perform pg_temp.ca_legacy_photo_check('only_three_synthetic_proofs_created',(select count(*)=before_reviews+3 from ca_private.photo_reviews));
 perform pg_temp.ca_legacy_photo_check('only_optional_transactional_auth_fixture_created',(select count(*)=before_auth_users+synthetic_owner::int from auth.users));
 perform pg_temp.ca_legacy_photo_check('guard_remains_private_definer',(select prosecdef and proconfig=array['search_path=""']::text[] from pg_proc where oid='ca_private.check_listing_photo_reviews()'::regprocedure)
  and not has_function_privilege('anon','ca_private.check_listing_photo_reviews()','EXECUTE') and not has_function_privilege('authenticated','ca_private.check_listing_photo_reviews()','EXECUTE'));
 update ca_private.photo_review_config set enabled=(old_flags->>'enabled')::boolean,admin_preview=(old_flags->>'admin_preview')::boolean where singleton;
 perform pg_temp.ca_legacy_photo_check('photo_review_flags_restored',(select to_jsonb(c)=old_flags from ca_private.photo_review_config c where singleton));
end $test$;
select count(*) passed_count,array_agg(name order by name) passed_tests from ca_legacy_photo_results;
rollback;
