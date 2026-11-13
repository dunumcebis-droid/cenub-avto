-- Admin-only real-provider trial boundary. Fixtures and flags always ROLLBACK.
begin;
do $test$
declare admin_id uuid; owner_id uuid; held_id uuid; blocked boolean;
 picture constant text:='https://fixture.invalid/cohort-unreviewed.jpg';
begin
 select a.istifadeci_id into admin_id from public.adminler a join auth.users u on u.id=a.istifadeci_id limit 1;
 select u.id into owner_id from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) limit 1;
 if admin_id is null or owner_id is null then raise exception 'Missing existing test identities';end if;
 update ca_private.photo_review_config set enabled=false,admin_preview=false where singleton;
 if ca_private.photo_review_allowed(admin_id) or ca_private.photo_review_allowed(owner_id) then raise exception 'Disabled cohort allowed';end if;
 update ca_private.photo_review_config set admin_preview=true where singleton;
 if not ca_private.photo_review_allowed(admin_id) or ca_private.photo_review_allowed(owner_id) then raise exception 'Preview cohort authorization mismatch';end if;
 if public.ca_photo_review_service_status() is distinct from '{"enabled":false,"admin_preview":true}'::jsonb then raise exception 'Preview status mismatch';end if;
 perform public.ca_photo_review_reserve(admin_id);
 blocked:=false;
 begin perform public.ca_photo_review_reserve(owner_id);exception when raise_exception then blocked:=sqlerrm='CA_PHOTO_REVIEW_DISABLED';end;
 if not blocked then raise exception 'Nonadmin preview reservation allowed';end if;
 perform set_config('request.jwt.claim.sub',owner_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',owner_id,'role','authenticated')::text,true);
 perform set_config('role','authenticated',true);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
 values(owner_id,'CA_COHORT_ROLLBACK','Ordinary manual flow',2020,100,'gozlemede',array[picture],jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(picture)),'photo',picture)) returning id into held_id;
 if held_id is null then raise exception 'Ordinary manual flow broken';end if;
 perform set_config('role','none',true);
 perform set_config('request.jwt.claim.sub',admin_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',admin_id,'role','authenticated')::text,true);
 perform set_config('role','authenticated',true);
 blocked:=false;
 begin
  insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data)
  values(admin_id,'CA_COHORT_ROLLBACK','Admin review required',2020,100,'gozlemede',array[picture],jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(picture)),'photo',picture));
 exception when check_violation then blocked:=true;end;
 if not blocked then raise exception 'Admin cohort bypassed review';end if;
 if not public.cenub_admin_yoxla() then raise exception 'Existing user-token admin RPC failed';end if;
 perform set_config('role','none',true);
 update ca_private.photo_review_config set enabled=true,admin_preview=false where singleton;
 if not ca_private.photo_review_allowed(owner_id) then raise exception 'Global mode failed';end if;
 if has_function_privilege('authenticated','ca_private.photo_review_allowed(uuid)','execute') or has_function_privilege('anon','ca_private.photo_review_allowed(uuid)','execute') then raise exception 'Cohort helper exposed';end if;
end $test$;
rollback;
select true as disabled_preserved,true as admin_preview_scoped,true as ordinary_uploads_preserved,
 true as admin_review_required,true as real_user_admin_rpc_used,true as global_mode_preserved,
 true as private_helper_unexposed,true as fixtures_rolled_back;
