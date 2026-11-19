-- Təcili manual-payment, publication, until-sold, filtering and privacy regressions.
-- Run after database/urgent-listings.sql. Fixtures are transaction-local only.
-- One optional .invalid Auth identity is inserted directly; no account API,
-- HTTP, email, payment provider or stored-image upload is used. Never COMMIT.
begin;
create temporary table ca_urgent_results(name text primary key);
create temporary table ca_urgent_original_listings as select id,to_jsonb(e) row_data from public.elanlar e;
create temporary table ca_urgent_original_packages as select id,to_jsonb(p) row_data from public.paket_sorgulari p;
do $$begin
 execute format('grant usage on schema %I to anon,authenticated',(select nspname from pg_namespace where oid=pg_my_temp_schema()));
end$$;
grant select,insert on ca_urgent_results to anon,authenticated;
create function pg_temp.ca_urgent_check(p_name text,p_ok boolean)
returns void language plpgsql security invoker set search_path='' as $$
begin
 if p_ok is distinct from true then raise exception 'FAILED: %',p_name;end if;
 insert into pg_temp.ca_urgent_results values(p_name);
end$$;
create function pg_temp.ca_urgent_error(p_name text,p_sql text,p_state text)
returns void language plpgsql security invoker set search_path='' as $$
declare blocked boolean:=false;actual text;
begin
 begin execute p_sql;exception when others then get stacked diagnostics actual=returned_sqlstate;blocked:=actual=p_state;end;
 perform pg_temp.ca_urgent_check(p_name,blocked);
end$$;
create function pg_temp.ca_urgent_as(p_role text,p_uid uuid)
returns void language plpgsql security invoker set search_path='' as $$
begin
 perform set_config('role','none',true);
 perform set_config('request.jwt.claim.sub',coalesce(p_uid::text,''),true);
 perform set_config('request.jwt.claims',case when p_uid is null then jsonb_build_object('role',p_role)::text else jsonb_build_object('sub',p_uid,'role',p_role)::text end,true);
 perform set_config('role',p_role,true);
end$$;
grant execute on function pg_temp.ca_urgent_check(text,boolean),pg_temp.ca_urgent_error(text,text,text),pg_temp.ca_urgent_as(text,uuid) to anon,authenticated;

do $test$
declare
 admin_id uuid;owner_a uuid;owner_b uuid;owners uuid[];
 marker text:='CA_URGENT_ROLLBACK_'||replace(gen_random_uuid()::text,'-','');
 urgent_id uuid:=gen_random_uuid();spoof_id uuid:=gen_random_uuid();bad_label_id uuid:=gen_random_uuid();
 urgent_credit uuid:=gen_random_uuid();urgent_barter uuid:=gen_random_uuid();urgent_old uuid:=gen_random_uuid();
 vip_id uuid:=gen_random_uuid();premium_id uuid:=gen_random_uuid();standard_id uuid:=gen_random_uuid();free_id uuid:=gen_random_uuid();expired_vip uuid:=gen_random_uuid();
 pending_id uuid:=gen_random_uuid();rejected_id uuid:=gen_random_uuid();deleted_id uuid:=gen_random_uuid();
 notify_urgent uuid:=gen_random_uuid();notify_free uuid:=gen_random_uuid();notify_wrong uuid:=gen_random_uuid();
 request_id uuid;notify_request uuid;search_urgent uuid;search_all uuid;fixture_id uuid;
 before_auth bigint;synthetic_owner boolean:=false;photo_flags jsonb;original_start timestamptz;last_seq bigint;
 n integer;i integer;j integer;affected integer;r jsonb;item jsonb;f jsonb;filters jsonb[];
 expired_ok boolean:=false;urgent_ok boolean:=false;originals_ok boolean:=false;
 picture constant text:='https://fixture.invalid/urgent-front.jpg';
 label constant text:='Təcili — 1 AZN / satılanadək';
begin
 select count(*) into before_auth from auth.users;
 select a.istifadeci_id into admin_id from public.adminler a join auth.users u on u.id=a.istifadeci_id order by u.created_at,u.id limit 1;
 select array_agg(id order by created_at,id) into owners from(select u.id,u.created_at from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) order by u.created_at,u.id limit 2)t;
 owner_a:=owners[1];owner_b:=owners[2];
 if admin_id is null or owner_a is null then raise exception 'SETUP: an existing admin and nonadmin identity are required';end if;
 if owner_b is null then
  owner_b:=gen_random_uuid();synthetic_owner:=true;
  insert into auth.users(id,email,aud,role,raw_app_meta_data,raw_user_meta_data,created_at,updated_at)
  values(owner_b,'ca-urgent-rollback-'||owner_b::text||'@fixture.invalid','authenticated','authenticated','{}','{}',now(),now());
 end if;
 select to_jsonb(c) into photo_flags from ca_private.photo_review_config c where singleton;
 update ca_private.photo_review_config set enabled=false,admin_preview=false where singleton;
 perform pg_temp.ca_urgent_check('browse_remains_stable_invoker',(select not prosecdef and provolatile='s' from pg_proc where oid='public.ca_browse_listings(jsonb,integer,integer)'::regprocedure));
 perform pg_temp.ca_urgent_check('search_match_stays_private',not has_function_privilege('anon','ca_private.search_matches(uuid,jsonb)','EXECUTE') and not has_function_privilege('authenticated','ca_private.search_matches(uuid,jsonb)','EXECUTE'));
 perform pg_temp.ca_urgent_check('saved_filter_cleaner_stays_private',not has_function_privilege('anon','ca_private.clean_saved_filters(jsonb)','EXECUTE') and not has_function_privilege('authenticated','ca_private.clean_saved_filters(jsonb)','EXECUTE'));

 -- Use the real owner role and automatic-request trigger, including its retry.
 perform pg_temp.ca_urgent_as('authenticated',owner_a);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,seher,sekiller,ca_data)
 values(owner_a,marker,'Paid urgent',2020,10000,'Bakı',array[picture,'https://fixture.invalid/urgent-rear.jpg'],jsonb_build_object('requestedPackage',label,'pack','Pulsuz','saleOptions',jsonb_build_array('credit','barter')))
 returning id into urgent_id;
 request_id:=public.ca_paket_sorgusu_yarat(urgent_id,'Tecili');
 perform pg_temp.ca_urgent_check('urgent_request_retry_is_idempotent',public.ca_paket_sorgusu_yarat(urgent_id,'Tecili')=request_id);
 perform pg_temp.ca_urgent_error('pending_urgent_cannot_switch_request_package',format('select public.ca_paket_sorgusu_yarat(%L,''VIP'')',urgent_id),'22023');
 perform pg_temp.ca_urgent_error('unknown_paid_request_package_denied',format('select public.ca_paket_sorgusu_yarat(%L,''urgent'')',urgent_id),'22023');
 perform pg_temp.ca_urgent_error('owner_cannot_self_approve_payment',format('select public.ca_admin_paket_tesdiq(%L)',request_id),'P0001');
 perform pg_temp.ca_urgent_error('owner_cannot_self_publish',format('select public.ca_admin_status(%L,''aktiv'')',urgent_id),'42501');
 perform pg_temp.ca_urgent_error('owner_cannot_set_canonical_paid_package',format('update public.elanlar set paket_adi=''Tecili'' where id=%L',urgent_id),'42501');
 insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data)
 values(owner_a,marker,'Forged client pack',2020,100,jsonb_build_object('pack','Tecili','requestedPackage',''))
 returning id into spoof_id;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data)
 values(owner_a,marker,'Wrong price label',2020,100,jsonb_build_object('requestedPackage','Təcili — 11 AZN / satılanadək'))
 returning id into bad_label_id;
 perform pg_temp.ca_urgent_as('none',null);
 perform pg_temp.ca_urgent_check('automatic_urgent_request_is_pending_and_single',(select count(*)=1 and bool_and(paket_adi='Tecili' and odenis_veziyyeti='gozlemede' and tesdiqlenib is null) from public.paket_sorgulari where elan_id=urgent_id));
 perform pg_temp.ca_urgent_check('request_does_not_activate_paid_package',exists(select 1 from public.elanlar where id=urgent_id and veziyyet='gozlemede' and paket_adi='Pulsuz' and paket_baslayir is null and paket_bitir is null));
 perform pg_temp.ca_urgent_check('client_pack_cannot_grant_urgent',exists(select 1 from public.elanlar where id=spoof_id and paket_adi='Pulsuz') and not exists(select 1 from public.paket_sorgulari where elan_id=spoof_id));
 perform pg_temp.ca_urgent_check('eleven_azn_does_not_parse_as_one_azn',not exists(select 1 from public.paket_sorgulari where elan_id=bad_label_id));
 perform pg_temp.ca_urgent_as('authenticated',owner_b);
 perform pg_temp.ca_urgent_error('other_owner_cannot_request_urgent',format('select public.ca_paket_sorgusu_yarat(%L,''Tecili'')',urgent_id),'42501');
 perform pg_temp.ca_urgent_as('anon',null);
 perform pg_temp.ca_urgent_check('pending_urgent_not_public',not exists(select 1 from public.elanlar where id=urgent_id) and (public.ca_browse_listings(jsonb_build_object('make',marker,'urgent',true),1,48)->>'total')::int=0);
 perform pg_temp.ca_urgent_error('anonymous_urgent_request_denied',format('select public.ca_paket_sorgusu_yarat(%L,''Tecili'')',urgent_id),'42501');

 perform pg_temp.ca_urgent_as('authenticated',admin_id);
 r:=public.ca_admin_browse_listings('all',marker,1,48);
 select x into item from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=urgent_id;
 perform pg_temp.ca_urgent_check('admin_sees_requested_urgent_before_approval',item->>'requested_package'='Tecili' and item->>'package_status'='pending' and item->>'approved_package'='Pulsuz' and (item->>'package_request_id')::uuid=request_id);
 -- Payment search accepts the display name and keeps exact UUID priority.
 foreach f in array array[to_jsonb('Təcili'::text),to_jsonb('TƏCİLİ'::text),to_jsonb('tecili'::text)] loop
  r:=public.ca_admin_browse_payments('all',f#>>'{}',1,48);
  perform pg_temp.ca_urgent_check('payment_search_urgent_name_'||(f#>>'{}'),exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=request_id));
 end loop;
 r:=public.ca_admin_browse_payments('all',request_id::text,1,48);
 perform pg_temp.ca_urgent_check('payment_search_exact_request_uuid_still_pinned',(r->>'total')::int=1 and (r->'items'->0->>'id')::uuid=request_id);
 r:=public.ca_admin_browse_payments('all',urgent_id::text,1,48);
 perform pg_temp.ca_urgent_check('payment_search_exact_listing_uuid_still_pinned',(r->>'total')::int=1 and (r->'items'->0->>'id')::uuid=request_id);
 r:=public.ca_admin_browse_payments('tesdiqlendi','Təcili',1,48);
 perform pg_temp.ca_urgent_check('payment_search_name_respects_payment_status',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=request_id));
 perform pg_temp.ca_urgent_error('publication_requires_payment_confirmation',format('select public.ca_admin_status(%L,''aktiv'')',urgent_id),'22023');
 perform public.ca_admin_paket_tesdiq(request_id);
 perform pg_temp.ca_urgent_error('payment_cannot_be_confirmed_twice',format('select public.ca_admin_paket_tesdiq(%L)',request_id),'P0001');
 perform pg_temp.ca_urgent_as('none',null);
 perform pg_temp.ca_urgent_check('payment_confirmation_keeps_listing_pending',exists(select 1 from public.elanlar where id=urgent_id and veziyyet='gozlemede' and paket_adi='Tecili' and paket_baslayir is null and paket_bitir is null));
 perform pg_temp.ca_urgent_check('manual_payment_confirmation_records_request',exists(select 1 from public.paket_sorgulari where id=request_id and odenis_veziyyeti='tesdiqlendi' and tesdiqlenib is not null));
 perform pg_temp.ca_urgent_as('authenticated',admin_id);
 perform public.ca_admin_status(urgent_id,'aktiv');
 perform pg_temp.ca_urgent_as('none',null);
 select paket_baslayir into original_start from public.elanlar where id=urgent_id;
 perform pg_temp.ca_urgent_check('first_publication_starts_urgent_without_expiry',original_start is not null and exists(select 1 from public.elanlar where id=urgent_id and veziyyet='aktiv' and paket_adi='Tecili' and paket_bitir is null));
 perform pg_temp.ca_urgent_as('authenticated',owner_a);
 update public.elanlar set veziyyet='gozlemede',ca_data=jsonb_build_object('pack','Pulsuz','requestedPackage','','saleOptions',jsonb_build_array('credit','barter')) where id=urgent_id;
 perform pg_temp.ca_urgent_as('authenticated',admin_id);
 perform public.ca_admin_status(urgent_id,'aktiv');
 perform pg_temp.ca_urgent_as('none',null);
 perform pg_temp.ca_urgent_check('edit_republication_keeps_original_urgent_activation',exists(select 1 from public.elanlar where id=urgent_id and paket_adi='Tecili' and paket_baslayir=original_start and paket_bitir is null));
 perform pg_temp.ca_urgent_check('edit_republication_does_not_create_second_charge',(select count(*)=1 from public.paket_sorgulari where elan_id=urgent_id));

 -- Administrative fixture seeding covers ranking, legacy dates, and hidden states.
 -- No live trigger is disabled and no client receives package-write privileges.
 insert into public.elanlar(id,satici_id,marka,model,il,qiymet,seher,veziyyet,sekiller,ca_data,paket_adi,paket_baslayir,paket_bitir)
 values(urgent_credit,owner_b,marker,'Urgent credit',2021,20000,'Bakı','aktiv',array[picture],'{"saleOptions":["credit"]}','Tecili',now()-interval '1 day',null),
 (urgent_barter,owner_b,marker,'Urgent barter',2022,30000,'Lənkəran','aktiv',array[picture],'{"saleOptions":["barter"]}','Tecili',now()-interval '1 day',null),
 (urgent_old,owner_b,marker,'Urgent old legacy end',2023,40000,'Bakı','aktiv',array[picture],'{}','Tecili',now()-interval '1 year',now()-interval '1 day'),
 (vip_id,owner_b,marker,'VIP',2020,50000,'Bakı','aktiv',array[picture],'{}','VIP',now()-interval '1 day',now()+interval '14 days'),
 (premium_id,owner_b,marker,'Premium',2020,60000,'Bakı','aktiv',array[picture],'{}','Premium',now()-interval '1 day',now()+interval '4 days'),
 (standard_id,owner_b,marker,'Standart',2020,70000,'Bakı','aktiv',array[picture],'{}','Standart',now()-interval '1 day',now()+interval '2 days'),
 (free_id,owner_b,marker,'Free',2020,80000,'Bakı','aktiv',array[picture],'{}','Pulsuz',null,null),
 (expired_vip,owner_b,marker,'Expired VIP',2020,90000,'Bakı','aktiv',array[picture],'{}','VIP',now()-interval '30 days',now()-interval '15 days'),
 (pending_id,owner_b,marker,'Pending urgent',2020,100,'Bakı','gozlemede',array[picture],'{}','Tecili',null,null),
 (rejected_id,owner_b,marker,'Rejected urgent',2020,100,'Bakı','reddedildi',array[picture],'{}','Tecili',now(),null),
 (deleted_id,owner_b,marker,'Archived urgent',2020,100,'Bakı','silindi',array[picture],'{}','Tecili',now(),null);
 perform pg_temp.ca_urgent_as('anon',null);
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'urgent',true,'sort','priceAsc'),1,48);
 perform pg_temp.ca_urgent_check('urgent_filter_contains_only_four_effective_urgent_listings',(r->>'total')::int=4 and (select array_agg((x->>'id')::uuid order by ord) from jsonb_array_elements(r->'items') with ordinality q(x,ord))=array[urgent_id,urgent_credit,urgent_barter,urgent_old]);
 perform pg_temp.ca_urgent_check('urgent_filter_has_no_featured_vip_items',r->'vip_items'='[]');
 perform pg_temp.ca_urgent_check('urgent_public_projection_keeps29_columns',not exists(select 1 from jsonb_array_elements(r->'items') x where (select count(*) from jsonb_object_keys(x))<>29 or x?'paket_tesdiq_qeydi' or x?'is_sold'));
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'urgent',true,'pack','VIP'),1,48);
 perform pg_temp.ca_urgent_check('urgent_vip_filters_intersect_to_empty',(r->>'total')::int=0 and r->'items'='[]' and r->'vip_items'='[]');
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'pack','Tecili'),1,48);
 perform pg_temp.ca_urgent_check('canonical_package_filter_selects_urgent',(r->>'total')::int=4);
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'urgent',true,'saleType','credit','priceMin',15000),1,48);
 perform pg_temp.ca_urgent_check('urgent_combines_with_credit_and_price',(r->>'total')::int=1 and (r->'items'->0->>'id')::uuid=urgent_credit);
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'urgent',true,'saleType','barter','city','Lənkəran'),1,48);
 perform pg_temp.ca_urgent_check('urgent_combines_with_barter_and_city',(r->>'total')::int=1 and (r->'items'->0->>'id')::uuid=urgent_barter);
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'sort','priceAsc'),1,48);
 perform pg_temp.ca_urgent_check('default_rank_preserves_vip_premium_standard_before_urgent',(select array_agg((x->>'id')::uuid order by ord) from jsonb_array_elements(r->'items') with ordinality q(x,ord))=array[vip_id,premium_id,standard_id,urgent_id,urgent_credit,urgent_barter,urgent_old,free_id,expired_vip]);
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'urgent',false),1,48);
 perform pg_temp.ca_urgent_check('false_urgent_filter_means_all',(r->>'total')::int=9);
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'urgent',null),1,48);
 perform pg_temp.ca_urgent_check('null_urgent_filter_means_all',(r->>'total')::int=9);
 i:=0;
 for f in select value from jsonb_array_elements('[{"urgent":"true"},{"urgent":1},{"urgent":[]},{"urgent":{}},{"urgent":""}]') loop
  i:=i+1;perform pg_temp.ca_urgent_error('invalid_urgent_filter_denied_'||i,format('select public.ca_browse_listings(%L,1,24)',f::text),'22023');
 end loop;
 perform pg_temp.ca_urgent_as('none',null);

 -- Roll back only the expiry call's subtransaction, including any existing
 -- expired paid rows, before continuing. No business row is ever retained changed.
 perform pg_temp.ca_urgent_as('authenticated',admin_id);
 begin
  n:=public.ca_paket_muddet_yenile();
  perform pg_temp.ca_urgent_as('none',null);
  expired_ok:=exists(select 1 from public.elanlar where id=expired_vip and paket_adi='Pulsuz' and paket_baslayir is null and paket_bitir is null);
  urgent_ok:=exists(select 1 from public.elanlar where id=urgent_old and paket_adi='Tecili' and paket_bitir=now()-interval '1 day') and exists(select 1 from public.elanlar where id=urgent_id and paket_adi='Tecili' and paket_bitir is null);
  raise exception using errcode='ZX001',message='rollback expiry probe';
 exception when sqlstate 'ZX001' then null;
 end;
 perform pg_temp.ca_urgent_as('none',null);
 perform pg_temp.ca_urgent_check('finite_vip_still_expires',expired_ok);
 perform pg_temp.ca_urgent_check('urgent_does_not_expire_by_calendar',urgent_ok);

 filters:=array[jsonb_build_object('make',marker,'urgent',true),jsonb_build_object('make',marker,'urgent',false),jsonb_build_object('make',marker,'urgent',true,'saleType','credit'),jsonb_build_object('make',marker,'urgent',true,'pack','VIP')];
 i:=0;
 foreach f in array filters loop
  i:=i+1;r:=public.ca_browse_listings(f,1,48);j:=0;
  foreach fixture_id in array array[urgent_id,urgent_credit,urgent_barter,urgent_old,vip_id,premium_id,standard_id,free_id,expired_vip,pending_id,rejected_id,deleted_id,spoof_id] loop
   j:=j+1;perform pg_temp.ca_urgent_check('notification_matcher_parity_'||i||'_'||j,ca_private.search_matches(fixture_id,f)=exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=fixture_id));
  end loop;
 end loop;
 perform pg_temp.ca_urgent_check('saved_cleaner_preserves_true_urgent',ca_private.clean_saved_filters('{"urgent":true,"saleType":"credit"}')='{"urgent":true,"saleType":"credit"}');
 perform pg_temp.ca_urgent_check('saved_cleaner_omits_false_urgent',ca_private.clean_saved_filters('{"urgent":false}')='{}');
 perform pg_temp.ca_urgent_check('saved_cleaner_omits_null_urgent',ca_private.clean_saved_filters('{"urgent":null}')='{}');

 perform pg_temp.ca_urgent_as('authenticated',owner_a);
 perform pg_temp.ca_urgent_check('mark_urgent_sold_is_idempotent',public.ca_mark_listing_sold(urgent_id)=urgent_id and public.ca_mark_listing_sold(urgent_id)=urgent_id);
 perform pg_temp.ca_urgent_error('owner_cannot_unset_sold',format('update public.elanlar set is_sold=false where id=%L',urgent_id),'42501');
 perform pg_temp.ca_urgent_as('none',null);
 perform pg_temp.ca_urgent_check('sold_retains_urgent_history_and_original_photos',exists(select 1 from public.elanlar where id=urgent_id and is_sold and paket_adi='Tecili' and paket_baslayir=original_start and paket_bitir is null and sekiller=array[picture,'https://fixture.invalid/urgent-rear.jpg']) and exists(select 1 from public.paket_sorgulari where id=request_id and odenis_veziyyeti='tesdiqlendi'));
 perform pg_temp.ca_urgent_check('sold_not_notification_match',not ca_private.search_matches(urgent_id,jsonb_build_object('urgent',true)));
 perform pg_temp.ca_urgent_as('authenticated',admin_id);
 perform pg_temp.ca_urgent_error('sold_urgent_cannot_be_republished',format('select public.ca_admin_status(%L,''aktiv'')',urgent_id),'22023');
 perform pg_temp.ca_urgent_as('anon',null);
 perform pg_temp.ca_urgent_check('sold_urgent_hidden_from_public_table',not exists(select 1 from public.elanlar where id=urgent_id));
 perform pg_temp.ca_urgent_check('sold_urgent_removed_from_urgent_browse',(public.ca_browse_listings(jsonb_build_object('make',marker,'urgent',true),1,48)->>'total')::int=3);
 perform pg_temp.ca_urgent_as('none',null);

 -- Verify persisted saved filters and actual approval-event notifications.
 select count(*) into n from ca_private.saved_searches where owner_id=owner_a;
 if n>18 then raise exception 'SETUP: fixture owner needs two spare saved-search slots';end if;
 select coalesce(max(seq),0) into last_seq from ca_private.approved_listing_events;
 insert into ca_private.notification_progress(owner_id,cursor_seq) values(owner_a,last_seq) on conflict(owner_id) do update set cursor_seq=excluded.cursor_seq;
 perform pg_temp.ca_urgent_as('authenticated',owner_a);
 search_urgent:=public.ca_save_search('Urgent fixture',jsonb_build_object('make',marker||'_NOTIFY','urgent',true,'saleType','credit'));
 search_all:=public.ca_save_search('All fixture',jsonb_build_object('make',marker||'_NOTIFY','urgent',false));
 perform pg_temp.ca_urgent_check('false_and_null_saved_urgent_deduplicate',public.ca_save_search('All renamed',jsonb_build_object('make',marker||'_NOTIFY','urgent',null))=search_all);
 r:=public.ca_list_saved_searches();
 perform pg_temp.ca_urgent_check('saved_search_keeps_true_urgent_and_sale_type',exists(select 1 from jsonb_array_elements(r) x where (x->>'id')::uuid=search_urgent and x->'filters'->'urgent'='true' and x->'filters'->>'saleType'='credit'));
 perform pg_temp.ca_urgent_check('saved_search_omits_false_urgent',exists(select 1 from jsonb_array_elements(r) x where (x->>'id')::uuid=search_all and not(x->'filters'?'urgent')));
 i:=0;
 for f in select value from jsonb_array_elements('[{"urgent":"true"},{"urgent":1},{"urgent":[]},{"urgent":{}},{"urgent":""}]') loop
  i:=i+1;perform pg_temp.ca_urgent_error('invalid_saved_urgent_filter_denied_'||i,format('select public.ca_save_search(''Invalid'',%L)',f::text),'22023');
 end loop;
 r:=public.ca_list_notifications(1,24);
 perform pg_temp.ca_urgent_check('urgent_saved_search_does_not_backfill_history',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'search_id')::uuid in(search_urgent,search_all)));
 perform pg_temp.ca_urgent_as('authenticated',owner_b);
 insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data)
 values(owner_b,marker||'_NOTIFY','Fresh urgent credit',2020,100,jsonb_build_object('requestedPackage',label,'saleOptions',jsonb_build_array('credit')))
 returning id into notify_urgent;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data)
 values(owner_b,marker||'_NOTIFY','Fresh free credit',2020,200,'{"saleOptions":["credit"]}')
 returning id into notify_free;
 insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data)
 values(owner_b,marker||'_OTHER','Wrong make urgent credit',2020,300,jsonb_build_object('requestedPackage',label,'saleOptions',jsonb_build_array('credit')))
 returning id into notify_wrong;
 notify_request:=public.ca_paket_sorgusu_yarat(notify_urgent,'Tecili');
 perform pg_temp.ca_urgent_as('none',null);
 select id into request_id from public.paket_sorgulari where elan_id=notify_wrong and odenis_veziyyeti='gozlemede';
 perform pg_temp.ca_urgent_as('authenticated',admin_id);
 perform public.ca_admin_paket_tesdiq(notify_request);perform public.ca_admin_status(notify_urgent,'aktiv');
 perform public.ca_admin_status(notify_free,'aktiv');
 perform public.ca_admin_paket_tesdiq(request_id);perform public.ca_admin_status(notify_wrong,'aktiv');
 perform pg_temp.ca_urgent_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,24);
 perform pg_temp.ca_urgent_as('none',null);
 perform pg_temp.ca_urgent_check('urgent_saved_search_notifies_only_matching_urgent',(select array_agg(elan_id) from ca_private.search_notifications where search_id=search_urgent)=array[notify_urgent]);
 perform pg_temp.ca_urgent_check('default_saved_search_still_notifies_free_and_urgent',(select array_agg(elan_id order by elan_id) from ca_private.search_notifications where search_id=search_all)=(select array_agg(id order by id) from unnest(array[notify_urgent,notify_free]) id));
 perform pg_temp.ca_urgent_check('wrong_make_urgent_never_notifies',not exists(select 1 from ca_private.search_notifications where search_id in(search_urgent,search_all) and elan_id=notify_wrong));

 perform pg_temp.ca_urgent_check('original_business_listings_and_photos_unchanged',not exists(select 1 from pg_temp.ca_urgent_original_listings b left join public.elanlar e on e.id=b.id where e.id is null or to_jsonb(e) is distinct from b.row_data));
 perform pg_temp.ca_urgent_check('original_payment_rows_unchanged',not exists(select 1 from pg_temp.ca_urgent_original_packages b left join public.paket_sorgulari p on p.id=b.id where p.id is null or to_jsonb(p) is distinct from b.row_data));
 perform pg_temp.ca_urgent_check('only_optional_transactional_auth_fixture_created',(select count(*)=before_auth+synthetic_owner::int from auth.users));
 update ca_private.photo_review_config set enabled=(photo_flags->>'enabled')::boolean,admin_preview=(photo_flags->>'admin_preview')::boolean where singleton;
 perform pg_temp.ca_urgent_check('photo_review_flags_restored',(select to_jsonb(c)=photo_flags from ca_private.photo_review_config c where singleton));
end $test$;
select count(*) passed_count,array_agg(name order by name) passed_tests from pg_temp.ca_urgent_results;
rollback;
