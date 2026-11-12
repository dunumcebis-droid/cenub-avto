-- Synthetic owner writes; every fixture is rolled back. Do not change ROLLBACK.
begin;
do $test$
declare
 owner_id uuid; other_id uuid; fixture_id uuid; marker text:=gen_random_uuid()::text;
 second_key text:=gen_random_uuid()::text; blocked boolean:=false; actual_key text;
 before_requests bigint;
begin
 select u.id into owner_id from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) order by u.id limit 1;
 select u.id into other_id from auth.users u where u.id<>owner_id order by u.id limit 1;
 if owner_id is null or other_id is null then raise exception 'Existing test identities unavailable';end if;
 if not exists(select 1 from pg_index where indexrelid=to_regclass('public.ca_elanlar_submission_once') and indisunique and indisvalid) then raise exception 'Unique submission index missing';end if;
 if has_function_privilege('anon','ca_private.preserve_submission_key()','execute') or has_function_privilege('authenticated','ca_private.preserve_submission_key()','execute') then raise exception 'Private trigger exposed';end if;
 select count(*) into before_requests from public.paket_sorgulari;
 perform set_config('request.jwt.claim.sub',owner_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',owner_id,'role','authenticated')::text,true);
 perform set_config('role','authenticated',true);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,ca_data)
 values(owner_id,'CA_SYNTHETIC_RETRY','Rollback only',2020,100,'gozlemede',jsonb_build_object('_submission_id',marker,'price',100)) returning id into fixture_id;
 begin
  insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,ca_data)
  values(owner_id,'CA_SYNTHETIC_RETRY','Rollback duplicate',2020,100,'gozlemede',jsonb_build_object('_submission_id',marker));
 exception when unique_violation then blocked:=true;end;
 if not blocked then raise exception 'Duplicate owner request accepted';end if;
 update public.elanlar set ca_data=jsonb_build_object('price',125),qiymet=125 where id=fixture_id;
 select ca_data->>'_submission_id' into actual_key from public.elanlar where id=fixture_id;
 if actual_key is distinct from marker then raise exception 'Omitted key was not preserved';end if;
 update public.elanlar set ca_data=jsonb_build_object('_submission_id',second_key,'price',150),qiymet=150 where id=fixture_id;
 select ca_data->>'_submission_id' into actual_key from public.elanlar where id=fixture_id;
 if actual_key is distinct from marker then raise exception 'Changed key was not preserved';end if;
 perform set_config('request.jwt.claim.sub',other_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',other_id,'role','authenticated')::text,true);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,ca_data)
 values(other_id,'CA_SYNTHETIC_RETRY','Other owner',2020,100,'gozlemede',jsonb_build_object('_submission_id',marker));
 perform set_config('role','none',true);
 if (select count(*) from public.elanlar where ca_data->>'_submission_id'=marker)<>2 then raise exception 'Owner-scoped key count mismatch';end if;
 if (select count(*) from public.paket_sorgulari)<>before_requests then raise exception 'Unexpected package request';end if;
 perform set_config('request.jwt.claim.sub',owner_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',owner_id,'role','authenticated')::text,true);
 perform set_config('role','authenticated',true);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,ca_data)
 values(owner_id,'CA_SYNTHETIC_RETRY','VIP rollback',2020,100,'gozlemede',jsonb_build_object('_submission_id',second_key,'requestedPackage','VIP — 15 AZN')) returning id into fixture_id;
 blocked:=false;
 begin
  insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,ca_data)
  values(owner_id,'CA_SYNTHETIC_RETRY','Duplicate VIP rollback',2020,100,'gozlemede',jsonb_build_object('_submission_id',second_key,'requestedPackage','VIP — 15 AZN'));
 exception when unique_violation then blocked:=true;end;
 if not blocked then raise exception 'Duplicate VIP listing accepted';end if;
 perform set_config('role','none',true);
 if (select count(*) from public.paket_sorgulari where elan_id=fixture_id and paket_adi='VIP')<>1 or (select count(*) from public.paket_sorgulari)<>before_requests+1 then raise exception 'VIP request count mismatch';end if;
end $test$;
rollback;
select true as unique_index_present,true as private_helper_unexposed,true as duplicate_owner_request_blocked,
 true as omitted_key_preserved,true as changed_key_preserved,true as same_key_different_owner_allowed,
 true as no_extra_free_package_request,true as duplicate_vip_blocked,true as exactly_one_vip_request,true as fixtures_rolled_back;
