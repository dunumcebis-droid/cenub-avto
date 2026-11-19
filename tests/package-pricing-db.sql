-- Package pricing: VIP 10 AZN/15 days, Premium 5 AZN/10 days, no new Standart.
-- Run after database/package-pricing.sql. All synthetic changes ROLLBACK.
-- No account API, email, payment provider, HTTP call, live trigger disabling,
-- privilege widening, or persistent data modification is performed.
begin;
create temporary table ca_pricing_results(name text primary key);
create temporary table ca_pricing_original_listings as select id,to_jsonb(e) row_data from public.elanlar e;
create temporary table ca_pricing_original_packages as select id,to_jsonb(p) row_data from public.paket_sorgulari p;
do $$begin
 execute format('grant usage on schema %I to anon,authenticated',(select nspname from pg_namespace where oid=pg_my_temp_schema()));
end$$;
grant select,insert on ca_pricing_results to anon,authenticated;
create function pg_temp.ca_pricing_check(p_name text,p_ok boolean)
returns void language plpgsql security invoker set search_path='' as $$
begin
 if p_ok is distinct from true then raise exception 'FAILED: %',p_name;end if;
 insert into pg_temp.ca_pricing_results values(p_name);
end$$;
create function pg_temp.ca_pricing_error(p_name text,p_sql text,p_state text)
returns void language plpgsql security invoker set search_path='' as $$
declare blocked boolean:=false;actual text;
begin
 begin execute p_sql;exception when others then get stacked diagnostics actual=returned_sqlstate;blocked:=actual=p_state;end;
 perform pg_temp.ca_pricing_check(p_name,blocked);
end$$;
create function pg_temp.ca_pricing_as(p_role text,p_uid uuid)
returns void language plpgsql security invoker set search_path='' as $$
begin
 perform set_config('role','none',true);
 perform set_config('request.jwt.claim.sub',coalesce(p_uid::text,''),true);
 perform set_config('request.jwt.claims',case when p_uid is null then jsonb_build_object('role',p_role)::text else jsonb_build_object('sub',p_uid,'role',p_role)::text end,true);
 perform set_config('role',p_role,true);
end$$;
grant execute on function pg_temp.ca_pricing_check(text,boolean),pg_temp.ca_pricing_error(text,text,text),pg_temp.ca_pricing_as(text,uuid) to anon,authenticated;

-- The approval-date trigger prevents historical timestamps on the real table.
-- Use exact function-body clones bound only to a temporary no-trigger table for
-- fallback date boundaries. Public lifecycle/authorization tests below use the
-- actual RPCs and actual RLS. Production functions/triggers remain untouched.
create temporary table ca_pricing_historical (like public.elanlar including defaults);
do $clone$
declare definition text;
begin
 definition:=pg_get_functiondef('public.ca_browse_listings(jsonb,integer,integer)'::regprocedure);
 execute replace(replace(definition,'public.ca_browse_listings(','pg_temp.ca_pricing_history_browse('),'public.elanlar','pg_temp.ca_pricing_historical');
 definition:=pg_get_functiondef('ca_private.search_matches(uuid,jsonb)'::regprocedure);
 execute replace(replace(definition,'ca_private.search_matches(','pg_temp.ca_pricing_history_matches('),'public.elanlar','pg_temp.ca_pricing_historical');
end $clone$;
do $test$
declare
 admin_id uuid;owner_id uuid;
 marker text:='CA_PRICING_ROLLBACK_'||replace(gen_random_uuid()::text,'-','');
 vip_new uuid;premium_new uuid;urgent_new uuid;free_new uuid;
 legacy_standard uuid:=gen_random_uuid();legacy_vip uuid:=gen_random_uuid();legacy_rejected uuid:=gen_random_uuid();
 old_premium uuid:=gen_random_uuid();old_standard uuid:=gen_random_uuid();old_vip uuid:=gen_random_uuid();
 request_vip uuid;request_premium uuid;request_urgent uuid;request_standard uuid:=gen_random_uuid();request_legacy_vip uuid:=gen_random_uuid();
 fixture_id uuid;historical_ids uuid[];f jsonb;filters jsonb[];r jsonb;item jsonb;
 n integer;i integer;j integer;before_auth bigint;photo_flags jsonb;
 old_start timestamptz:=now()-interval '1 day';old_premium_end timestamptz:=now()+interval '4 days';old_standard_end timestamptz:=now()+interval '2 days';old_vip_end timestamptz:=now()+interval '14 days';
 picture constant text:='https://fixture.invalid/pricing-front.jpg';
 vip_label constant text:='Önə çıxarılan — 10 AZN / 15 gün';
 premium_label constant text:='Üstün — 5 AZN / 10 gün';
 old_vip_label constant text:='Önə çıxarılan — 15 AZN / 15 gün';
 standard_label constant text:='Sərfəli seçim — 3 AZN';
begin
 select count(*) into before_auth from auth.users;
 select a.istifadeci_id into admin_id from public.adminler a join auth.users u on u.id=a.istifadeci_id order by u.created_at,u.id limit 1;
 select u.id into owner_id from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) order by u.created_at,u.id limit 1;
 if admin_id is null or owner_id is null then raise exception 'SETUP: an existing admin and nonadmin identity are required';end if;
 select to_jsonb(c) into photo_flags from ca_private.photo_review_config c where singleton;
 update ca_private.photo_review_config set enabled=false,admin_preview=false where singleton;
 perform pg_temp.ca_pricing_check('browse_remains_stable_invoker',(select not prosecdef and provolatile='s' from pg_proc where oid='public.ca_browse_listings(jsonb,integer,integer)'::regprocedure));
 perform pg_temp.ca_pricing_check('search_match_stays_private',not has_function_privilege('anon','ca_private.search_matches(uuid,jsonb)','EXECUTE') and not has_function_privilege('authenticated','ca_private.search_matches(uuid,jsonb)','EXECUTE'));

 -- Insert under the actual owner role. Protected IDs come from the DB default.
 perform pg_temp.ca_pricing_as('authenticated',owner_id);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,sekiller,ca_data)
 values(owner_id,marker,'VIP new10',2020,10000,array[picture],jsonb_build_object('requestedPackage',vip_label)) returning id into vip_new;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,sekiller,ca_data)
 values(owner_id,marker,'Premium new10days',2020,20000,array[picture],jsonb_build_object('requestedPackage',premium_label,'saleOptions',jsonb_build_array('credit'))) returning id into premium_new;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,sekiller,ca_data)
 values(owner_id,marker,'Urgent unchanged',2020,30000,array[picture],'{"requestedPackage":"Təcili — 1 AZN / satılanadək"}') returning id into urgent_new;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data)
 values(owner_id,marker,'Free for RPC guard',2020,40000,'{}') returning id into free_new;
 request_vip:=public.ca_paket_sorgusu_yarat(vip_new,'VIP');
 request_premium:=public.ca_paket_sorgusu_yarat(premium_new,'Premium');
 request_urgent:=public.ca_paket_sorgusu_yarat(urgent_new,'Tecili');
 perform pg_temp.ca_pricing_check('vip10_request_retry_is_idempotent',public.ca_paket_sorgusu_yarat(vip_new,'VIP')=request_vip);
 perform pg_temp.ca_pricing_error('new_standard_direct_purchase_denied',format('select public.ca_paket_sorgusu_yarat(%L,''Standart'')',free_new),'22023');
 perform pg_temp.ca_pricing_error('new_standard_old_label_purchase_denied',format('insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data) values(%L,%L,''Blocked old standard'',2020,100,%L::jsonb)',owner_id,marker,jsonb_build_object('requestedPackage',standard_label)::text),'22023');
 perform pg_temp.ca_pricing_error('new_old_vip15_label_purchase_denied',format('insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data) values(%L,%L,''Blocked old VIP15'',2020,100,%L::jsonb)',owner_id,marker,jsonb_build_object('requestedPackage',old_vip_label)::text),'22023');
 perform pg_temp.ca_pricing_error('owner_cannot_self_publish_new_vip',format('select public.ca_admin_status(%L,''aktiv'')',vip_new),'42501');
 perform pg_temp.ca_pricing_as('none',null);
 perform pg_temp.ca_pricing_check('vip10_label_creates_only_vip_not_urgent',(select count(*)=1 and bool_and(paket_adi='VIP' and odenis_veziyyeti='gozlemede') from public.paket_sorgulari where elan_id=vip_new));
 perform pg_temp.ca_pricing_check('premium5_label_creates_premium',(select count(*)=1 and bool_and(paket_adi='Premium' and odenis_veziyyeti='gozlemede') from public.paket_sorgulari where elan_id=premium_new));
 perform pg_temp.ca_pricing_check('urgent1_label_remains_urgent',(select count(*)=1 and bool_and(paket_adi='Tecili' and odenis_veziyyeti='gozlemede') from public.paket_sorgulari where elan_id=urgent_new));
 perform pg_temp.ca_pricing_check('requests_alone_do_not_publish_or_activate',not exists(select 1 from public.elanlar where id in(vip_new,premium_new,urgent_new) and (veziyyet<>'gozlemede' or paket_adi<>'Pulsuz' or paket_baslayir is not null or paket_bitir is not null)));

 perform pg_temp.ca_pricing_as('authenticated',admin_id);
 r:=public.ca_admin_browse_listings('all',marker,1,48);
 select x into item from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=vip_new;
 perform pg_temp.ca_pricing_check('admin_metadata_recognizes_new_vip10_label',item->>'requested_package'='VIP' and item->>'package_status'='pending');
 perform pg_temp.ca_pricing_error('new_premium_cannot_publish_before_payment',format('select public.ca_admin_status(%L,''aktiv'')',premium_new),'22023');
 perform public.ca_admin_paket_tesdiq(request_vip);perform public.ca_admin_paket_tesdiq(request_premium);perform public.ca_admin_paket_tesdiq(request_urgent);
 perform pg_temp.ca_pricing_as('none',null);
 perform pg_temp.ca_pricing_check('payment_confirmation_keeps_all_three_pending',not exists(select 1 from public.elanlar where id in(vip_new,premium_new,urgent_new) and (veziyyet<>'gozlemede' or paket_baslayir is not null or paket_bitir is not null)));
 perform pg_temp.ca_pricing_as('authenticated',admin_id);
 perform public.ca_admin_status(vip_new,'aktiv');perform public.ca_admin_status(premium_new,'aktiv');perform public.ca_admin_status(urgent_new,'aktiv');
 perform pg_temp.ca_pricing_as('none',null);
 perform pg_temp.ca_pricing_check('new_vip_activates_for_exactly15days',exists(select 1 from public.elanlar where id=vip_new and paket_adi='VIP' and paket_baslayir is not null and paket_bitir-paket_baslayir=interval '15 days'));
 perform pg_temp.ca_pricing_check('new_premium_activates_for_exactly10days',exists(select 1 from public.elanlar where id=premium_new and paket_adi='Premium' and paket_baslayir is not null and paket_bitir-paket_baslayir=interval '10 days'));
 perform pg_temp.ca_pricing_check('urgent_still_has_no_calendar_expiry',exists(select 1 from public.elanlar where id=urgent_new and paket_adi='Tecili' and paket_baslayir is not null and paket_bitir is null));

 -- Historical requests are seeded without purchase intent, then edited using
 -- the real owner role after their corresponding request history exists.
 insert into public.elanlar(id,satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data,paket_adi,paket_baslayir,paket_bitir)
 values(legacy_standard,owner_id,marker,'Legacy pending standard',2020,100,'gozlemede',array[picture],'{}','Pulsuz',null,null),
 (legacy_vip,owner_id,marker,'Legacy pending VIP15',2020,100,'gozlemede',array[picture],'{}','Pulsuz',null,null),
 (legacy_rejected,owner_id,marker,'Legacy rejected VIP15',2020,100,'gozlemede',array[picture],'{}','Pulsuz',null,null),
 (old_premium,owner_id,marker,'Approved old Premium5days',2020,100,'aktiv',array[picture],'{}','Premium',old_start,old_premium_end),
 (old_standard,owner_id,marker,'Approved old Standart3days',2020,100,'aktiv',array[picture],'{}','Standart',old_start,old_standard_end),
 (old_vip,owner_id,marker,'Approved old VIP15days',2020,100,'aktiv',array[picture],'{}','VIP',old_start,old_vip_end);
 insert into public.paket_sorgulari(id,elan_id,satici_id,paket_adi,odenis_veziyyeti,yaradilib)
 values(request_standard,legacy_standard,owner_id,'Standart','gozlemede',now()-interval '1 day'),
 (request_legacy_vip,legacy_vip,owner_id,'VIP','gozlemede',now()-interval '1 day'),
 (gen_random_uuid(),legacy_rejected,owner_id,'VIP','reddedildi',now()-interval '1 day');
 insert into public.paket_sorgulari(elan_id,satici_id,paket_adi,odenis_veziyyeti,yaradilib,tesdiqlenib)
 values(old_premium,owner_id,'Premium','tesdiqlendi',old_start,old_start),
 (old_standard,owner_id,'Standart','tesdiqlendi',old_start,old_start),
 (old_vip,owner_id,'VIP','tesdiqlendi',old_start,old_start);
 perform pg_temp.ca_pricing_as('authenticated',owner_id);
 perform pg_temp.ca_pricing_check('existing_pending_standard_request_retries_without_new_purchase',public.ca_paket_sorgusu_yarat(legacy_standard,'Standart')=request_standard);
 update public.elanlar set ca_data=jsonb_build_object('requestedPackage',standard_label) where id=legacy_standard;
 update public.elanlar set ca_data=jsonb_build_object('requestedPackage',old_vip_label) where id=legacy_vip;
 update public.elanlar set ca_data=jsonb_build_object('requestedPackage',old_vip_label) where id=legacy_rejected;
 update public.elanlar set veziyyet='gozlemede',ca_data=jsonb_build_object('requestedPackage','Üstün — 5 AZN','description','Legacy edit') where id=old_premium;
 update public.elanlar set veziyyet='gozlemede',ca_data=jsonb_build_object('requestedPackage',standard_label,'description','Legacy edit') where id=old_standard;
 update public.elanlar set veziyyet='gozlemede',ca_data=jsonb_build_object('requestedPackage',old_vip_label,'description','Legacy edit') where id=old_vip;
 perform pg_temp.ca_pricing_as('none',null);
 perform pg_temp.ca_pricing_check('legacy_label_edits_do_not_create_second_requests',not exists(select 1 from public.paket_sorgulari where elan_id in(legacy_standard,legacy_vip,legacy_rejected,old_premium,old_standard,old_vip) group by elan_id having count(*)<>1));
 perform pg_temp.ca_pricing_check('rejected_legacy_request_stays_rejected',exists(select 1 from public.paket_sorgulari where elan_id=legacy_rejected and odenis_veziyyeti='reddedildi'));
 perform pg_temp.ca_pricing_as('authenticated',admin_id);
 perform public.ca_admin_paket_tesdiq(request_standard);perform public.ca_admin_status(legacy_standard,'aktiv');
 perform public.ca_admin_paket_tesdiq(request_legacy_vip);perform public.ca_admin_status(legacy_vip,'aktiv');
 perform public.ca_admin_status(old_premium,'aktiv');perform public.ca_admin_status(old_standard,'aktiv');perform public.ca_admin_status(old_vip,'aktiv');
 perform pg_temp.ca_pricing_error('rejected_legacy_request_cannot_publish',format('select public.ca_admin_status(%L,''aktiv'')',legacy_rejected),'22023');
 perform pg_temp.ca_pricing_as('none',null);
 perform pg_temp.ca_pricing_check('existing_pending_standard_is_fulfilled_for3days',exists(select 1 from public.elanlar where id=legacy_standard and paket_adi='Standart' and veziyyet='aktiv' and paket_bitir-paket_baslayir=interval '3 days'));
 perform pg_temp.ca_pricing_check('existing_pending_legacy_vip_is_fulfilled_for15days',exists(select 1 from public.elanlar where id=legacy_vip and paket_adi='VIP' and veziyyet='aktiv' and paket_bitir-paket_baslayir=interval '15 days'));
 perform pg_temp.ca_pricing_check('old_explicit_premium5day_dates_are_not_extended',exists(select 1 from public.elanlar where id=old_premium and paket_adi='Premium' and paket_baslayir=old_start and paket_bitir=old_premium_end));
 perform pg_temp.ca_pricing_check('old_explicit_standard3day_dates_are_preserved',exists(select 1 from public.elanlar where id=old_standard and paket_adi='Standart' and paket_baslayir=old_start and paket_bitir=old_standard_end));
 perform pg_temp.ca_pricing_check('old_explicit_vip15day_dates_are_preserved',exists(select 1 from public.elanlar where id=old_vip and paket_adi='VIP' and paket_baslayir=old_start and paket_bitir=old_vip_end));

 -- Boundary fixtures read the current exact browse/matcher SQL in pg_temp;
 -- only its table binding changes, because production approval dates are guarded.
 insert into pg_temp.ca_pricing_historical(satici_id,marka,model,il,qiymet,veziyyet,ca_data,paket_adi,tesdiq_tarixi,paket_bitir)
 values(owner_id,marker||'_HISTORY','Premium8',2020,100,'aktiv','{"saleOptions":["credit"]}','Premium',now()-interval '8 days',null),
 (owner_id,marker||'_HISTORY','Premium11',2020,200,'aktiv','{}','Premium',now()-interval '11 days',null),
 (owner_id,marker||'_HISTORY','VIP14',2020,300,'aktiv','{}','VIP',now()-interval '14 days',null),
 (owner_id,marker||'_HISTORY','VIP16',2020,400,'aktiv','{}','VIP',now()-interval '16 days',null),
 (owner_id,marker||'_HISTORY','Standart2',2020,500,'aktiv','{}','Standart',now()-interval '2 days',null),
 (owner_id,marker||'_HISTORY','Standart4',2020,600,'aktiv','{}','Standart',now()-interval '4 days',null),
 (owner_id,marker||'_HISTORY','PremiumExplicitFuture',2020,700,'aktiv','{}','Premium',now()-interval '1 year',now()+interval '1 day'),
 (owner_id,marker||'_HISTORY','PremiumExplicitPast',2020,800,'aktiv','{}','Premium',now()-interval '2 days',now()-interval '1 day'),
 (owner_id,marker||'_HISTORY','UrgentOld',2020,900,'aktiv','{}','Tecili',now()-interval '1 year',null);
 select array_agg(id order by id) into historical_ids from pg_temp.ca_pricing_historical;
 r:=pg_temp.ca_pricing_history_browse(jsonb_build_object('make',marker||'_HISTORY','pack','Premium'),1,48);
 perform pg_temp.ca_pricing_check('fallback_premium8days_stays_premium',exists(select 1 from jsonb_array_elements(r->'items') x where x->>'model'='Premium8'));
 perform pg_temp.ca_pricing_check('fallback_premium11days_expires',not exists(select 1 from jsonb_array_elements(r->'items') x where x->>'model'='Premium11'));
 perform pg_temp.ca_pricing_check('explicit_future_end_overrides_old_approval_fallback',exists(select 1 from jsonb_array_elements(r->'items') x where x->>'model'='PremiumExplicitFuture'));
 perform pg_temp.ca_pricing_check('explicit_past_end_is_not_extended_to10days',not exists(select 1 from jsonb_array_elements(r->'items') x where x->>'model'='PremiumExplicitPast'));
 r:=pg_temp.ca_pricing_history_browse(jsonb_build_object('make',marker||'_HISTORY','pack','VIP'),1,48);
 perform pg_temp.ca_pricing_check('fallback_vip_duration_stays15days',(r->>'total')::int=1 and r->'items'->0->>'model'='VIP14');
 r:=pg_temp.ca_pricing_history_browse(jsonb_build_object('make',marker||'_HISTORY','pack','Standart'),1,48);
 perform pg_temp.ca_pricing_check('fallback_legacy_standard_stays3days',(r->>'total')::int=1 and r->'items'->0->>'model'='Standart2');
 r:=pg_temp.ca_pricing_history_browse(jsonb_build_object('make',marker||'_HISTORY','urgent',true),1,48);
 perform pg_temp.ca_pricing_check('fallback_urgent_remains_until_sold',(r->>'total')::int=1 and r->'items'->0->>'model'='UrgentOld');
 filters:=array[jsonb_build_object('make',marker||'_HISTORY','pack','Premium'),jsonb_build_object('make',marker||'_HISTORY','pack','VIP'),jsonb_build_object('make',marker||'_HISTORY','pack','Standart'),jsonb_build_object('make',marker||'_HISTORY','pack','Pulsuz'),jsonb_build_object('make',marker||'_HISTORY','urgent',true),jsonb_build_object('make',marker||'_HISTORY','pack','Premium','saleType','credit')];
 i:=0;
 foreach f in array filters loop
  i:=i+1;r:=pg_temp.ca_pricing_history_browse(f,1,48);j:=0;
  foreach fixture_id in array historical_ids loop
   j:=j+1;perform pg_temp.ca_pricing_check('fallback_notification_matcher_parity_'||i||'_'||j,pg_temp.ca_pricing_history_matches(fixture_id,f)=exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=fixture_id));
  end loop;
 end loop;
 -- Real RPC parity on current approved fixtures remains independently covered.
 f:=jsonb_build_object('make',marker,'pack','Premium','saleType','credit');r:=public.ca_browse_listings(f,1,48);j:=0;
 foreach fixture_id in array array[vip_new,premium_new,urgent_new,legacy_standard,legacy_vip,old_premium,old_standard,old_vip] loop
  j:=j+1;perform pg_temp.ca_pricing_check('actual_notification_matcher_parity_'||j,ca_private.search_matches(fixture_id,f)=exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=fixture_id));
 end loop;
 perform pg_temp.ca_pricing_check('original_listings_photos_packages_dates_unchanged',not exists(select 1 from pg_temp.ca_pricing_original_listings b left join public.elanlar e on e.id=b.id where e.id is null or to_jsonb(e) is distinct from b.row_data));
 perform pg_temp.ca_pricing_check('original_payment_history_unchanged',not exists(select 1 from pg_temp.ca_pricing_original_packages b left join public.paket_sorgulari p on p.id=b.id where p.id is null or to_jsonb(p) is distinct from b.row_data));
 perform pg_temp.ca_pricing_check('no_auth_identity_created',(select count(*)=before_auth from auth.users));
 update ca_private.photo_review_config set enabled=(photo_flags->>'enabled')::boolean,admin_preview=(photo_flags->>'admin_preview')::boolean where singleton;
 perform pg_temp.ca_pricing_check('photo_review_flags_restored',(select to_jsonb(c)=photo_flags from ca_private.photo_review_config c where singleton));
end $test$;
select count(*) passed_count,array_agg(name order by name) passed_tests from pg_temp.ca_pricing_results;
rollback;
