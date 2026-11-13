-- Trusted vehicle-photo gate tests. Metadata fixtures only; no bytes or API calls.
-- Every synthetic row and the temporary feature toggle are rolled back.
-- NEVER replace ROLLBACK with COMMIT.
begin;
do $test$
declare
 test_owner uuid; other_id uuid; legacy_id uuid; approved_id uuid; front_review uuid; rear_review uuid;
 front_path text; rear_path text; front_url text; rear_url text;
 legacy_url text:='https://fixture.invalid/legacy-'||gen_random_uuid()::text||'.jpg';
 unreviewed_url text:='https://fixture.invalid/unreviewed-'||gen_random_uuid()::text||'.jpg';
 prefix constant text:='https://iqdtehqxusfiwokrzceo.supabase.co/storage/v1/object/public/elan-sekilleri/';
 verdict jsonb; payload jsonb; gallery text[]; case_name text; blocked boolean; affected bigint;
 existing_recent integer; i integer; reserved uuid; namespace_path text; before_packages bigint;
begin
 select u.id into test_owner from auth.users u
 where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id)
 order by u.id limit 1;
 select u.id into other_id from auth.users u where u.id<>test_owner order by u.id limit 1;
 if test_owner is null or other_id is null then raise exception 'Existing test identities unavailable';end if;
 select count(*) into before_packages from public.paket_sorgulari;

 -- Service helpers and their source tables are not public API capabilities.
 foreach case_name in array array['anon','authenticated'] loop
  if has_function_privilege(case_name,'public.ca_photo_review_service_status()','execute')
   or has_function_privilege(case_name,'public.ca_photo_review_reserve(uuid)','execute')
   or has_function_privilege(case_name,'public.ca_photo_review_complete(uuid,uuid,text,text,text,jsonb)','execute')
   or has_function_privilege(case_name,'ca_private.check_listing_photo_reviews()','execute')
   or has_table_privilege(case_name,'ca_private.photo_reviews','select,insert,update,delete')
   or has_table_privilege(case_name,'ca_private.photo_review_config','select,insert,update,delete') then
   raise exception 'Private photo-review capability exposed to %',case_name;
  end if;
 end loop;
 if not has_function_privilege('service_role','public.ca_photo_review_reserve(uuid)','execute') then raise exception 'Service reservation grant missing';end if;
 if not (select relrowsecurity from pg_class where oid='ca_private.photo_reviews'::regclass)
 or not (select relrowsecurity from pg_class where oid='ca_private.photo_review_config'::regclass) then raise exception 'Private-table RLS missing';end if;

 update ca_private.photo_review_config set enabled=false,admin_preview=false where singleton;
 if public.ca_photo_review_service_status() is distinct from '{"enabled":false,"admin_preview":false}'::jsonb then raise exception 'Disabled status mismatch';end if;
 blocked:=false;
 begin perform public.ca_photo_review_reserve(test_owner);
 exception when raise_exception then blocked:=sqlerrm='CA_PHOTO_REVIEW_DISABLED';end;
 if not blocked then raise exception 'Disabled review accepted reservation';end if;
 perform set_config('request.jwt.claim.sub',test_owner::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',test_owner,'role','authenticated')::text,true);
 perform set_config('role','authenticated',true);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
 values(test_owner,'CA_PHOTO_GATE_TEST','Legacy before activation',2020,100,'gozlemede',array[legacy_url],
 jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(legacy_url)),'photo',legacy_url)) returning id into legacy_id;
 perform set_config('role','none',true);

 update ca_private.photo_review_config set enabled=true where singleton;
 if public.ca_photo_review_service_status() is distinct from '{"enabled":true,"admin_preview":false}'::jsonb then raise exception 'Enabled status mismatch';end if;

 -- Only server-issued reservations completed against stored metadata become proofs.
 front_review:=public.ca_photo_review_reserve(test_owner);
 rear_review:=public.ca_photo_review_reserve(test_owner);
 front_path:=test_owner::text||'/checked/'||front_review::text||'-ca-wm1.jpg';
 rear_path:=test_owner::text||'/checked/'||rear_review::text||'-ca-wm1.jpg';
 front_url:=prefix||front_path;rear_url:=prefix||rear_path;
 verdict:='{"is_vehicle_photo":true,"contains_screen_ui":false,"category":"front","confidence":0.95}'::jsonb;
 blocked:=false;
 begin perform public.ca_photo_review_complete(front_review,test_owner,'front',front_path,repeat('a',64),verdict);
 exception when raise_exception then blocked:=sqlerrm='CA_PHOTO_REVIEW_OBJECT_MISSING';end;
 if not blocked then raise exception 'Proof accepted absent object';end if;
 insert into storage.objects(bucket_id,name,metadata) values
 ('elan-sekilleri',front_path,'{"mimetype":"image/jpeg","size":100}'::jsonb),
 ('elan-sekilleri',rear_path,'{"mimetype":"image/jpeg","size":100}'::jsonb);

 foreach case_name in array array['screenshot','non_vehicle','wrong_category','low_confidence','extra_field','null_confidence'] loop
  payload:=case case_name
   when 'screenshot' then jsonb_set(verdict,'{contains_screen_ui}','true'::jsonb)
   when 'non_vehicle' then jsonb_set(verdict,'{is_vehicle_photo}','false'::jsonb)
   when 'wrong_category' then jsonb_set(verdict,'{category}','"rear"'::jsonb)
   when 'low_confidence' then jsonb_set(verdict,'{confidence}','0.84'::jsonb)
   when 'extra_field' then verdict||'{"approved":true}'::jsonb
   else jsonb_set(verdict,'{confidence}','null'::jsonb) end;
  blocked:=false;
  begin perform public.ca_photo_review_complete(front_review,test_owner,'front',front_path,repeat('a',64),payload);
  exception when raise_exception then blocked:=sqlerrm='CA_PHOTO_REVIEW_INVALID';end;
  if not blocked then raise exception 'Invalid verdict accepted: %',case_name;end if;
 end loop;
 if not public.ca_photo_review_complete(front_review,test_owner,'front',front_path,repeat('a',64),verdict)
 or not public.ca_photo_review_complete(front_review,test_owner,'front',front_path,repeat('a',64),verdict)
 or not public.ca_photo_review_complete(rear_review,test_owner,'rear',rear_path,repeat('b',64),jsonb_set(verdict,'{category}','"rear"'::jsonb)) then
  raise exception 'Valid or idempotent completion failed';
 end if;
 blocked:=false;
 begin perform public.ca_photo_review_complete(front_review,test_owner,'front',front_path,repeat('c',64),verdict);
 exception when raise_exception then blocked:=sqlerrm='CA_PHOTO_REVIEW_NOT_RESERVED';end;
 if not blocked then raise exception 'Completed proof hash was mutable';end if;
 if not exists(select 1 from ca_private.photo_reviews where id=front_review and owner_id=test_owner and approved and sha256=repeat('a',64)) then raise exception 'Approved proof missing';end if;

 perform set_config('role','authenticated',true);
 -- Direct callers cannot read/write private proof/config tables, even with known IDs.
 foreach case_name in array array['proof_read','proof_write','config_read','config_write','reserve_call','complete_call','status_call'] loop
  blocked:=false;
  begin
   case case_name
    when 'proof_read' then perform id from ca_private.photo_reviews limit 1;
    when 'proof_write' then update ca_private.photo_reviews set approved=true where id=front_review;
    when 'config_read' then perform enabled from ca_private.photo_review_config;
    when 'config_write' then update ca_private.photo_review_config set enabled=false,admin_preview=false where singleton;
    when 'reserve_call' then perform public.ca_photo_review_reserve(test_owner);
    when 'complete_call' then perform public.ca_photo_review_complete(front_review,test_owner,'front',front_path,repeat('a',64),verdict);
    else perform public.ca_photo_review_service_status();
   end case;
  exception when insufficient_privilege then blocked:=true;end;
  if not blocked then raise exception 'Authenticated private operation permitted: %',case_name;end if;
 end loop;

 -- Checked bytes cannot be inserted, replaced, or deleted by their owner.
 namespace_path:=test_owner::text||'/checked/'||gen_random_uuid()::text||'-ca-wm1.jpg';
 blocked:=false;
 begin insert into storage.objects(bucket_id,name,metadata) values('elan-sekilleri',namespace_path,'{}'::jsonb);
 exception when insufficient_privilege then blocked:=true;end;
 if not blocked then raise exception 'Client inserted checked object';end if;
 begin
  update storage.objects set metadata='{"size":999}'::jsonb where bucket_id='elan-sekilleri' and name=front_path;
  get diagnostics affected=row_count;
 exception when insufficient_privilege then affected:=0;end;
 if affected<>0 then raise exception 'Client updated checked object';end if;
 begin
  delete from storage.objects where bucket_id='elan-sekilleri' and name=front_path;
  get diagnostics affected=row_count;
 exception when insufficient_privilege then affected:=0;end;
 if affected<>0 then raise exception 'Client deleted checked object';end if;

 -- A correctly categorized server-approved photograph can create a pending ad.
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
 values(test_owner,'CA_PHOTO_GATE_TEST','Approved front',2020,100,'gozlemede',array[front_url],
 jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(front_url)),'photo',front_url)) returning id into approved_id;

 foreach case_name in array array['unreviewed','forged_approval','front_in_rear','rear_in_front','gallery_mismatch','cover_mismatch','unknown_group','duplicate_group_url','empty_groups','nonarray_group','nonstring_url','import_legacy_url'] loop
  gallery:=array[front_url];
  payload:=jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(front_url)),'photo',front_url);
  case case_name
   when 'unreviewed' then gallery:=array[unreviewed_url];payload:=jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(unreviewed_url)),'photo',unreviewed_url);
   when 'forged_approval' then gallery:=array[unreviewed_url];payload:=jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(unreviewed_url)),'photo',unreviewed_url,'photo_review',jsonb_build_object('approved',true,'owner',test_owner,'review_id',front_review));
   when 'front_in_rear' then payload:=jsonb_build_object('photos',jsonb_build_object('rear',jsonb_build_array(front_url)),'photo',front_url);
   when 'rear_in_front' then gallery:=array[rear_url];payload:=jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(rear_url)),'photo',rear_url);
   when 'gallery_mismatch' then gallery:=array[unreviewed_url];
   when 'cover_mismatch' then payload:=jsonb_set(payload,'{photo}',to_jsonb(unreviewed_url));
   when 'unknown_group' then payload:=jsonb_set(payload,'{photos}',jsonb_build_object('unchecked',jsonb_build_array(front_url)));
   when 'duplicate_group_url' then gallery:=array[front_url,front_url];payload:=jsonb_set(payload,'{photos,front}',jsonb_build_array(front_url,front_url));
   when 'empty_groups' then gallery:='{}'::text[];payload:='{"photos":{}}'::jsonb;
   when 'nonarray_group' then payload:=jsonb_set(payload,'{photos,front}',to_jsonb(front_url));
   when 'nonstring_url' then payload:=jsonb_set(payload,'{photos,front}','[42]'::jsonb);
   else gallery:=array[legacy_url];payload:=jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(legacy_url)),'photo',legacy_url);
  end case;
  blocked:=false;
  begin
   insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
   values(test_owner,'CA_PHOTO_GATE_TEST',case_name,2020,100,'gozlemede',gallery,payload);
  exception when check_violation then blocked:=true;end;
  if not blocked then raise exception 'Unapproved listing accepted: %',case_name;end if;
 end loop;

 -- Legacy exception is restricted to the original row and category.
 update public.elanlar set qiymet=125 where id=legacy_id;
 get diagnostics affected=row_count;
 if affected<>1 then raise exception 'Unchanged legacy photo prevented edit';end if;
 blocked:=false;
 begin update public.elanlar set ca_data=jsonb_build_object('photos',jsonb_build_object('rear',jsonb_build_array(legacy_url)),'photo',legacy_url) where id=legacy_id;
 exception when check_violation then blocked:=true;end;
 if not blocked then raise exception 'Legacy front moved to rear without review';end if;
 update public.elanlar set sekiller=array[legacy_url,rear_url],ca_data=jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(legacy_url),'rear',jsonb_build_array(rear_url)),'photo',legacy_url)
 where id=legacy_id;
 get diagnostics affected=row_count;
 if affected<>1 then raise exception 'Retained legacy category plus reviewed addition rejected';end if;

 perform set_config('request.jwt.claim.sub',other_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',other_id,'role','authenticated')::text,true);
 blocked:=false;
 begin
  insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
  values(other_id,'CA_PHOTO_GATE_TEST','Other owner proof reuse',2020,100,'gozlemede',array[front_url],jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(front_url)),'photo',front_url));
 exception when check_violation then blocked:=true;end;
 if not blocked then raise exception 'Other account reused photo proof';end if;
 perform set_config('role','none',true);

 -- Anonymous SQL identity cannot access proof/config/service operations either.
 perform set_config('role','anon',true);
 foreach case_name in array array['proof_read','config_read','reserve_call','status_call'] loop
  blocked:=false;
  begin
   case case_name
    when 'proof_read' then perform id from ca_private.photo_reviews limit 1;
    when 'config_read' then perform enabled from ca_private.photo_review_config;
    when 'reserve_call' then perform public.ca_photo_review_reserve(test_owner);
    else perform public.ca_photo_review_service_status();
   end case;
  exception when insufficient_privilege then blocked:=true;end;
  if not blocked then raise exception 'Anonymous private operation permitted: %',case_name;end if;
 end loop;
 perform set_config('role','none',true);

 -- All reservations, including unsuccessful classifications, consume the quota.
 select count(*) into existing_recent from ca_private.photo_reviews where owner_id=test_owner and created_at>clock_timestamp()-interval '10 minutes';
 if existing_recent>120 then raise exception 'Test owner already exceeds review quota';end if;
 for i in existing_recent+1..120 loop reserved:=public.ca_photo_review_reserve(test_owner);end loop;
 blocked:=false;
 begin perform public.ca_photo_review_reserve(test_owner);
 exception when raise_exception then blocked:=sqlerrm='CA_PHOTO_REVIEW_RATE_LIMIT';end;
 if not blocked then raise exception '121st review reservation not rate limited';end if;
 if (select count(*) from ca_private.photo_reviews where owner_id=test_owner and created_at>clock_timestamp()-interval '10 minutes')<>120 then raise exception 'Reservation quota count mismatch';end if;
 if not exists(select 1 from storage.objects where bucket_id='elan-sekilleri' and name=front_path and metadata->>'size'='100') then raise exception 'Checked object metadata mutated';end if;
 if (select count(*) from public.paket_sorgulari)<>before_packages then raise exception 'Photo tests altered package requests';end if;
end $test$;
rollback;
select true as disabled_mode_preserves_existing_flow,
 true as service_proofs_and_configuration_private,
 true as strict_approved_verdict_and_object_required,
 true as reviewed_namespace_immutable_to_clients,
 true as owner_category_gallery_and_cover_bound,
 true as legacy_exception_row_and_category_scoped,
 true as reservation_rate_limit_enforced,
 true as packages_unchanged,
 true as synthetic_fixtures_rolled_back;
