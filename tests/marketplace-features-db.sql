-- Marketplace authorization/lifecycle regressions. Run AFTER marketplace-features.sql.
-- Uses existing admin/owner; if needed creates one random fixture.invalid Auth row
-- ONLY inside this transaction. No account API, email, HTTP or storage writes.
-- All fixtures, temporary photo-review flags and queue progress ROLLBACK.
-- Never replace ROLLBACK with COMMIT. No user IDs or private business data output.
begin;
create temporary table ca_market_results(name text primary key);
create temporary table ca_market_existing_listings as select id,to_jsonb(e) row_data from public.elanlar e;
create temporary table ca_market_existing_packages as select id,to_jsonb(p) row_data from public.paket_sorgulari p;
do $$ begin
 execute format('grant usage on schema %I to anon,authenticated',(select nspname from pg_namespace where oid=pg_my_temp_schema()));
end $$;
grant select,insert on ca_market_results to anon,authenticated;
create function pg_temp.ca_market_check(p_name text,p_ok boolean)
returns void language plpgsql security invoker set search_path='' as $$
begin
 if p_ok is distinct from true then raise exception 'FAILED: %',p_name;end if;
 insert into pg_temp.ca_market_results values(p_name);
end $$;
create function pg_temp.ca_market_error(p_name text,p_sql text,p_state text)
returns void language plpgsql security invoker set search_path='' as $$
declare blocked boolean:=false;actual text;
begin
 begin execute p_sql;exception when others then get stacked diagnostics actual=returned_sqlstate;blocked:=actual=p_state;end;
 perform pg_temp.ca_market_check(p_name,blocked);
end $$;
create function pg_temp.ca_market_as(p_role text,p_uid uuid)
returns void language plpgsql security invoker set search_path='' as $$
begin
 perform set_config('role','none',true);
 perform set_config('request.jwt.claim.sub',coalesce(p_uid::text,''),true);
 perform set_config('request.jwt.claims',case when p_uid is null then jsonb_build_object('role',p_role)::text else jsonb_build_object('sub',p_uid,'role',p_role)::text end,true);
 perform set_config('role',p_role,true);
end $$;
grant execute on function pg_temp.ca_market_check(text,boolean),pg_temp.ca_market_error(text,text,text),pg_temp.ca_market_as(text,uuid) to anon,authenticated;

do $test$
declare
 admin_id uuid;owner_a uuid;owner_b uuid;ids uuid[];
 marker text:='CA_MARKET_ROLLBACK_'||replace(gen_random_uuid()::text,'-','');
 sold_id uuid:=gen_random_uuid();other_id uuid:=gen_random_uuid();pending_id uuid:=gen_random_uuid();
 history_id uuid:=gen_random_uuid();fresh_id uuid:=gen_random_uuid();wrong_id uuid:=gen_random_uuid();own_id uuid:=gen_random_uuid();zero_id uuid:=gen_random_uuid();
 visitor uuid:=gen_random_uuid();visitor_limit uuid:=gen_random_uuid();report_id uuid;search_a uuid;search_b uuid;wrong_search uuid;notification_a uuid;notification_b uuid;fixture_id uuid;
 r jsonb;r2 jsonb;f jsonb;filters jsonb[];field text;fn text;table_name text;i integer;n integer;before_n bigint;cursor_before bigint;last_seq bigint;
 picture constant text:='https://fixture.invalid/market-front.jpg';
 package_start timestamptz:=now()-interval '1 day';package_end timestamptz:=now()+interval '14 days';
 photo_flags jsonb;existing_search_a integer;existing_search_b integer;
 before_auth_users bigint;synthetic_owner boolean:=false;
begin
 select count(*) into before_auth_users from auth.users;
 select a.istifadeci_id into admin_id from public.adminler a join auth.users u on u.id=a.istifadeci_id order by u.created_at,u.id limit 1;
 select array_agg(id order by created_at,id) into ids from(select u.id,u.created_at from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) order by u.created_at,u.id limit 2)t;
 owner_a:=ids[1];owner_b:=ids[2];
 if admin_id is null or owner_a is null then raise exception 'SETUP: existing admin and nonadmin identities are required';end if;
 if owner_b is null then
  owner_b:=gen_random_uuid();synthetic_owner:=true;
  insert into auth.users(id,email,aud,role,raw_app_meta_data,raw_user_meta_data,created_at,updated_at)
  values(owner_b,'ca-market-rollback-'||owner_b::text||'@fixture.invalid','authenticated','authenticated','{}','{}',now(),now());
 end if;
 select to_jsonb(c) into photo_flags from ca_private.photo_review_config c where singleton;
 update ca_private.photo_review_config set enabled=false,admin_preview=false where singleton;

 -- Existing data is never an assertion fixture; these rows have unique makes.
 insert into public.elanlar(id,satici_id,marka,model,il,qiymet,yurus,seher,veziyyet,sekiller,ca_data,paket_adi,paket_baslayir,paket_bitir)
 values(sold_id,owner_a,marker||'_SOLD','Sold VIP',2020,10000,100,'Bakı','aktiv',array[picture,'https://fixture.invalid/market-rear.jpg'],jsonb_build_object('photos',jsonb_build_object('front',jsonb_build_array(picture)),'photo',picture),'VIP',package_start,package_end),
 (other_id,owner_b,marker||'_OTHER','Public',2021,20000,200,'Bakı','aktiv',array[picture],'{}','Pulsuz',null,null),
 (pending_id,owner_b,marker||'_PENDING','Private pending',2022,30000,300,'Bakı','gozlemede',array[picture],'{}','Pulsuz',null,null),
 (history_id,owner_b,marker||'_MATCH','Historical',2020,10000,10000,'Bakı','aktiv',array[picture],'{}','Pulsuz',null,null),
 (zero_id,owner_a,marker||'_ZERO','No events',2020,5000,0,'Bakı','gozlemede',array[picture],'{}','Pulsuz',null,null);

 -- Explicit grants, RLS and helper visibility are independent checks.
 foreach table_name in array array['listing_stats','listing_events','listing_reports','saved_searches','approved_listing_events','notification_progress','search_notifications'] loop
  perform pg_temp.ca_market_check('private_rls_'||table_name,(select relrowsecurity from pg_class where oid=('ca_private.'||table_name)::regclass));
  perform pg_temp.ca_market_check('private_acl_'||table_name,not has_table_privilege('anon','ca_private.'||table_name,'SELECT,INSERT,UPDATE,DELETE') and not has_table_privilege('authenticated','ca_private.'||table_name,'SELECT,INSERT,UPDATE,DELETE'));
 end loop;
 foreach fn in array array['search_matches(uuid,jsonb)','clean_saved_filters(jsonb)','enqueue_approved_listing()','photo_review_allowed(uuid)','check_listing_photo_reviews()','require_admin()','export_resource_sql(text)','preserve_submission_key()'] loop
  perform pg_temp.ca_market_check('helper_denied_'||fn,not has_function_privilege('anon','ca_private.'||fn,'EXECUTE') and not has_function_privilege('authenticated','ca_private.'||fn,'EXECUTE'));
 end loop;
 foreach fn in array array['ca_photo_review_service_status()','ca_photo_review_reserve(uuid)','ca_photo_review_complete(uuid,uuid,text,text,text,jsonb)'] loop
  perform pg_temp.ca_market_check('photo_proof_service_only_'||fn,not has_function_privilege('anon','public.'||fn,'EXECUTE') and not has_function_privilege('authenticated','public.'||fn,'EXECUTE'));
 end loop;
 foreach fn in array array['ca_mark_listing_sold(uuid)','ca_record_listing_event(uuid,text,uuid)','ca_my_listing_stats(uuid[])','ca_report_listing(uuid,text,text)','ca_admin_browse_reports(text,integer,integer)','ca_admin_resolve_report(uuid,text,text)','ca_save_search(text,jsonb)','ca_list_saved_searches()','ca_delete_saved_search(uuid)','ca_list_notifications(integer,integer)','ca_mark_notification_read(uuid)'] loop
  perform pg_temp.ca_market_check('public_invoker_'||fn,(select not prosecdef from pg_proc where oid=('public.'||fn)::regprocedure));
 end loop;
 perform pg_temp.ca_market_check('is_sold_not_client_writable',not has_column_privilege('authenticated','public.elanlar','is_sold','UPDATE') and not has_column_privilege('authenticated','public.elanlar','is_sold','INSERT'));

 perform pg_temp.ca_market_as('anon',null);
 perform pg_temp.ca_market_check('anonymous_active_view_recorded',public.ca_record_listing_event(other_id,'view',visitor));
 perform pg_temp.ca_market_check('anonymous_view_daily_dedup',not public.ca_record_listing_event(other_id,'view',visitor));
 perform pg_temp.ca_market_check('contact_has_independent_dedup_key',public.ca_record_listing_event(other_id,'contact',visitor) and not public.ca_record_listing_event(other_id,'contact',visitor));
 perform pg_temp.ca_market_check('invalid_event_kind_rejected',not public.ca_record_listing_event(other_id,'payment',visitor) and not public.ca_record_listing_event(other_id,null,visitor));
 perform pg_temp.ca_market_check('null_visitor_rejected',not public.ca_record_listing_event(other_id,'view',null));
 perform pg_temp.ca_market_check('pending_event_does_not_leak_or_count',not public.ca_record_listing_event(pending_id,'view',visitor));
 perform pg_temp.ca_market_error('anon_saved_search_denied','select public.ca_list_saved_searches()','42501');
 perform pg_temp.ca_market_error('anon_sold_rpc_denied',format('select public.ca_mark_listing_sold(%L)',sold_id),'42501');
 perform pg_temp.ca_market_error('anon_report_denied',format('select public.ca_report_listing(%L,''fraud'',''fixture'')',other_id),'42501');
 perform pg_temp.ca_market_error('anon_stats_denied',format('select public.ca_my_listing_stats(array[%L::uuid])',other_id),'42501');
 foreach table_name in array array['listing_stats','listing_events','listing_reports','saved_searches','approved_listing_events','notification_progress','search_notifications'] loop
  perform pg_temp.ca_market_error('anon_table_select_denied_'||table_name,format('select * from ca_private.%I limit 1',table_name),'42501');
 end loop;

 perform pg_temp.ca_market_as('authenticated',owner_a);
 perform pg_temp.ca_market_check('chosen_owner_is_not_admin',not public.cenub_admin_yoxla());
 perform pg_temp.ca_market_check('owner_self_events_excluded',not public.ca_record_listing_event(sold_id,'view',visitor) and not public.ca_record_listing_event(sold_id,'contact',visitor));
 r:=public.ca_my_listing_stats(array[sold_id,zero_id,other_id]);
 perform pg_temp.ca_market_check('private_counts_owner_only_with_zero_defaults',jsonb_array_length(r)=2 and not exists(select 1 from jsonb_array_elements(r) x where (x->>'id')::uuid=other_id or (x->>'views')::bigint<>0 or (x->>'contact_clicks')::bigint<>0));
 perform pg_temp.ca_market_error('stats_over100_ids_denied','select public.ca_my_listing_stats(array_fill(gen_random_uuid(),array[101]))','22023');
 perform pg_temp.ca_market_error('cannot_mark_other_owner_sold',format('select public.ca_mark_listing_sold(%L)',other_id),'42501');
 perform pg_temp.ca_market_error('report_own_active_listing_denied',format('select public.ca_report_listing(%L,''fraud'','''')',sold_id),'22023');
 perform pg_temp.ca_market_check('mark_own_sold_idempotent',public.ca_mark_listing_sold(sold_id)=sold_id and public.ca_mark_listing_sold(sold_id)=sold_id);
 perform pg_temp.ca_market_check('sold_remains_owner_visible_with_photos_and_vip_dates',exists(select 1 from public.elanlar where id=sold_id and is_sold and veziyyet='aktiv' and sekiller=array[picture,'https://fixture.invalid/market-rear.jpg'] and ca_data->>'photo'=picture and paket_adi='VIP' and paket_baslayir=package_start and paket_bitir=package_end));
 perform pg_temp.ca_market_error('owner_cannot_unset_sold',format('update public.elanlar set is_sold=false where id=%L',sold_id),'42501');
 perform pg_temp.ca_market_check('sold_owner_stats_still_accessible',jsonb_array_length(public.ca_my_listing_stats(array[sold_id]))=1);
 perform pg_temp.ca_market_error('nonadmin_report_queue_denied','select public.ca_admin_browse_reports(''all'',1,24)','42501');
 perform pg_temp.ca_market_error('report_own_listing_denied',format('select public.ca_report_listing(%L,''fraud'','''')',sold_id),'22023');
 perform pg_temp.ca_market_error('report_pending_listing_denied',format('select public.ca_report_listing(%L,''fraud'','''')',pending_id),'22023');
 perform pg_temp.ca_market_error('invalid_report_reason_denied',format('select public.ca_report_listing(%L,''invalid'','''')',other_id),'22023');
 perform pg_temp.ca_market_error('oversized_report_denied',format('select public.ca_report_listing(%L,''fraud'',repeat(''x'',1001))',other_id),'22023');
 report_id:=public.ca_report_listing(other_id,'wrong_info','<script>private fixture</script>');
 perform pg_temp.ca_market_check('open_report_retry_idempotent',public.ca_report_listing(other_id,'fraud','replacement')=report_id);
 perform pg_temp.ca_market_error('nonadmin_report_resolve_denied',format('select public.ca_admin_resolve_report(%L,''resolved'',''private'')',report_id),'42501');
 foreach table_name in array array['listing_stats','listing_events','listing_reports','saved_searches','approved_listing_events','notification_progress','search_notifications'] loop
  perform pg_temp.ca_market_error('auth_table_select_denied_'||table_name,format('select * from ca_private.%I limit 1',table_name),'42501');
  perform pg_temp.ca_market_error('auth_table_insert_denied_'||table_name,format('insert into ca_private.%I default values',table_name),'42501');
  perform pg_temp.ca_market_error('auth_table_update_denied_'||table_name,format('update ca_private.%I set %I=%I where false',table_name,case when table_name in ('listing_stats','listing_events','approved_listing_events') then 'elan_id' when table_name='listing_reports' then 'reporter_id' else 'owner_id' end,case when table_name in ('listing_stats','listing_events','approved_listing_events') then 'elan_id' when table_name='listing_reports' then 'reporter_id' else 'owner_id' end),'42501');
 end loop;
 perform pg_temp.ca_market_error('auth_match_helper_execute_denied',format('select ca_private.search_matches(%L,''{}'')',other_id),'42501');
 perform pg_temp.ca_market_error('auth_filter_helper_execute_denied','select ca_private.clean_saved_filters(''{}'')','42501');

 perform pg_temp.ca_market_as('anon',null);
 perform pg_temp.ca_market_check('sold_unavailable_through_direct_public_select',not exists(select 1 from public.elanlar where id=sold_id));
 perform pg_temp.ca_market_check('sold_excluded_from_public_browse',(public.ca_browse_listings(jsonb_build_object('make',marker||'_SOLD'),1,24)->>'total')::int=0);
 perform pg_temp.ca_market_check('sold_event_rejected',not public.ca_record_listing_event(sold_id,'view',visitor));
 perform pg_temp.ca_market_as('authenticated',owner_b);
 perform pg_temp.ca_market_check('counts_are_only_owner_data',public.ca_my_listing_stats(array[other_id,sold_id])=jsonb_build_array(jsonb_build_object('id',other_id,'views',1,'contact_clicks',1)));
 perform pg_temp.ca_market_check('owner_cannot_see_other_sold_private_row',not exists(select 1 from public.elanlar where id=sold_id));
 perform pg_temp.ca_market_error('sold_report_denied',format('select public.ca_report_listing(%L,''other'','''')',sold_id),'22023');
 perform pg_temp.ca_market_as('authenticated',admin_id);
 perform pg_temp.ca_market_error('admin_cannot_resurrect_sold',format('select public.ca_admin_status(%L,''aktiv'')',sold_id),'22023');
 r:=public.ca_admin_browse_listings('satilib',marker,1,24);
 perform pg_temp.ca_market_check('admin_sold_status_filter',(r->>'total')::int=1 and r->'items'->0->>'veziyyet'='satilib');
 r:=public.ca_admin_browse_reports('open',1,48);
 perform pg_temp.ca_market_check('admin_sees_report_details_without_reporter_identity',exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=report_id and x->>'details'='<script>private fixture</script>' and not(x?'reporter_id') and not(x?'email')));
 perform pg_temp.ca_market_check('admin_resolves_report',public.ca_admin_resolve_report(report_id,'resolved','<b>private admin note</b>'));
 perform pg_temp.ca_market_error('admin_invalid_resolution_denied',format('select public.ca_admin_resolve_report(%L,''open'','''')',report_id),'22023');
 perform pg_temp.ca_market_as('none',null);
 perform pg_temp.ca_market_check('report_resolution_does_not_hide_listing',exists(select 1 from public.elanlar where id=other_id and veziyyet='aktiv' and not is_sold));
 perform pg_temp.ca_market_check('resolved_notes_only_in_private_table',exists(select 1 from ca_private.listing_reports where id=report_id and status='resolved' and admin_note='<b>private admin note</b>' and resolved_at is not null));

 -- Hit report and event ceilings with synthetic rows, independent of existing activity.
 select count(*) into n from ca_private.listing_reports where reporter_id=owner_a and created_at>now()-interval '1 day';
 for i in n+1..10 loop
  insert into ca_private.listing_reports(elan_id,reporter_id,reason,status) values(other_id,owner_a,'other','dismissed');
 end loop;
 for i in 1..100 loop
  insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet) values(owner_b,marker||'_RATE','Fixture',2020,100,'aktiv') returning id into fixture_id;
  insert into ca_private.listing_events values(fixture_id,'view',(now() at time zone 'Asia/Baku')::date,md5(visitor_limit::text||(now() at time zone 'Asia/Baku')::date::text)),(fixture_id,'contact',(now() at time zone 'Asia/Baku')::date,md5(visitor_limit::text||(now() at time zone 'Asia/Baku')::date::text));
 end loop;
 perform pg_temp.ca_market_as('authenticated',owner_a);
 perform pg_temp.ca_market_error('daily_report_limit_enforced',format('select public.ca_report_listing(%L,''other'',''one too many'')',other_id),'22023');
 perform pg_temp.ca_market_as('anon',null);
 perform pg_temp.ca_market_check('daily_visitor_event_limit_enforced',not public.ca_record_listing_event(other_id,'view',visitor_limit));
 perform pg_temp.ca_market_as('none',null);

 -- Full predicate helper parity, including legacy string-encoded ca_data.
 update public.elanlar set ca_data=to_jsonb(jsonb_build_object('vehicleType','Minik','vehicleState','İşlənmiş','body','Sedan','color','Ağ','market','Avropa','seats','5','engine',2.0,'horsepower',150,'equipment',jsonb_build_array('ABS','Kondisioner'))::text),neqliyyat_novu=null,ban_novu=null,reng=null,bazar_ucun=null,oturacaq_sayi=null,muherrik_hecmi=null,at_gucu=null,techizat=null where id=history_id;
 filters:=array[
 jsonb_build_object('make',marker||'_MATCH'),
 jsonb_build_object('make',marker||'_MATCH','yearMin',2019,'yearMax',2021,'priceMin',9000,'priceMax',11000,'kmMin',9000,'kmMax',11000),
 jsonb_build_object('make',marker||'_MATCH','vehicle','Minik','state','İşlənmiş','body','Sedan','color','Ağ','market','Avropa','seats','5','engineMin',1.5,'engineMax',2.5,'hpMin',140,'hpMax',160,'equipment',jsonb_build_array('ABS','Kondisioner')),
 jsonb_build_object('make',marker||'_MATCH','pack','VIP'),
 jsonb_build_object('make',marker||'_MATCH','equipment',jsonb_build_array('NONEXISTENT')),
 jsonb_build_object('make',marker||'_MATCH','priceMax',1),
 jsonb_build_object('make',marker||'_MATCH','engineMin',3),
 jsonb_build_object('make',marker||'_MATCH','vehicle','Bus')];
 for i in 1..array_length(filters,1) loop
  r:=public.ca_browse_listings(filters[i],1,48);
  perform pg_temp.ca_market_check('saved_predicate_matches_public_browse_'||i,ca_private.search_matches(history_id,filters[i])=exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=history_id));
 end loop;
 perform pg_temp.ca_market_check('predicate_pk_bound_no_other_row_match',not ca_private.search_matches(other_id,jsonb_build_object('make',marker||'_MATCH')));

 -- Skip preexisting queue data only inside this rollback transaction.
 select coalesce(max(seq),0) into last_seq from ca_private.approved_listing_events;
 insert into ca_private.notification_progress(owner_id,cursor_seq) values(owner_a,last_seq),(owner_b,last_seq) on conflict(owner_id) do update set cursor_seq=excluded.cursor_seq;
 select count(*) into existing_search_a from ca_private.saved_searches where owner_id=owner_a;
 select count(*) into existing_search_b from ca_private.saved_searches where owner_id=owner_b;
 if existing_search_a>17 or existing_search_b>19 then raise exception 'SETUP: fixture identities need spare saved-search capacity';end if;
 perform pg_temp.ca_market_as('authenticated',owner_a);
 search_a:=public.ca_save_search('  Matching fixture  ',jsonb_build_object('make','  '||marker||'_MATCH  ','priceMax','20000','equipment',jsonb_build_array('ABS','ABS'),'sort','priceAsc','owner_id',owner_b));
 perform pg_temp.ca_market_check('normalized_duplicate_search_reuses_id',public.ca_save_search('Matching renamed',jsonb_build_object('make',marker||'_MATCH','priceMax',20000,'equipment',jsonb_build_array('ABS'),'sort','priceAsc'))=search_a);
 wrong_search:=public.ca_save_search('Wrong filter',jsonb_build_object('make',marker||'_UNFINDABLE'));
 r:=public.ca_list_saved_searches();
 perform pg_temp.ca_market_check('saved_filters_allowlist_and_normalization',exists(select 1 from jsonb_array_elements(r) x where (x->>'id')::uuid=search_a and x->>'name'='Matching renamed' and x->'filters'=jsonb_build_object('make',marker||'_MATCH','priceMax',20000,'equipment',jsonb_build_array('ABS'),'sort','priceAsc') and not(x?'owner_id')));
 perform pg_temp.ca_market_error('saved_search_bad_name_denied','select public.ca_save_search('' '', ''{}'')','22023');
 perform pg_temp.ca_market_error('saved_search_bad_sort_denied','select public.ca_save_search(''bad'', ''{"sort":"new"}'')','22023');
 perform pg_temp.ca_market_error('saved_search_bad_number_denied','select public.ca_save_search(''bad'', ''{"priceMin":-1}'')','22023');
 perform pg_temp.ca_market_error('saved_search_nonobject_denied','select public.ca_save_search(''bad'', ''[]'')','22023');
 r:=public.ca_list_notifications(1,48);
 perform pg_temp.ca_market_check('search_does_not_backfill_historical_active_ads',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'search_id')::uuid=search_a));
 perform pg_temp.ca_market_as('authenticated',owner_b);
 search_b:=public.ca_save_search('Other owner',jsonb_build_object('make',marker||'_MATCH'));
 perform pg_temp.ca_market_check('saved_search_list_ownership',not exists(select 1 from jsonb_array_elements(public.ca_list_saved_searches()) x where (x->>'id')::uuid in(search_a,wrong_search)));
 perform pg_temp.ca_market_check('cannot_delete_other_search',not public.ca_delete_saved_search(search_a));
 perform pg_temp.ca_market_as('none',null);
 insert into public.elanlar(id,satici_id,marka,model,il,qiymet,veziyyet,techizat) values
 (fresh_id,owner_b,marker||'_MATCH','New matching',2020,10000,'gozlemede',array['ABS']),
 (own_id,owner_a,marker||'_MATCH','Own matching',2020,10000,'gozlemede',array['ABS']),
 (wrong_id,owner_b,marker||'_NEVERMATCH','Wrong make',2020,10000,'gozlemede',array['ABS']);
 perform pg_temp.ca_market_check('pending_insert_does_not_enqueue',not exists(select 1 from ca_private.approved_listing_events where elan_id in(fresh_id,own_id,wrong_id)));
 perform pg_temp.ca_market_as('authenticated',admin_id);
 perform public.ca_admin_status(fresh_id,'aktiv');perform public.ca_admin_status(own_id,'aktiv');perform public.ca_admin_status(wrong_id,'aktiv');
 perform pg_temp.ca_market_as('none',null);
 perform pg_temp.ca_market_check('approval_only_enqueues_not_eager_notifications',not exists(select 1 from ca_private.search_notifications where search_id in(search_a,search_b,wrong_search) and elan_id in(fresh_id,own_id,wrong_id)));
 perform pg_temp.ca_market_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,48);r2:=public.ca_list_notifications(1,48);
 perform pg_temp.ca_market_check('new_match_generates_one_own_notification',1=(select count(*) from jsonb_array_elements(r->'items') x where (x->>'search_id')::uuid=search_a and (x->>'elan_id')::uuid=fresh_id));
 perform pg_temp.ca_market_check('own_wrong_history_ads_do_not_notify',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'search_id')::uuid in(search_a,wrong_search) and (x->>'elan_id')::uuid in(own_id,wrong_id,history_id)));
 perform pg_temp.ca_market_check('notification_listing_idempotent',r->'items'=r2->'items');
 select (x->>'id')::uuid into notification_a from jsonb_array_elements(r->'items') x where (x->>'search_id')::uuid=search_a and (x->>'elan_id')::uuid=fresh_id;
 perform pg_temp.ca_market_as('authenticated',owner_b);
 r:=public.ca_list_notifications(1,48);
 select (x->>'id')::uuid into notification_b from jsonb_array_elements(r->'items') x where (x->>'search_id')::uuid=search_b and (x->>'elan_id')::uuid=own_id;
 perform pg_temp.ca_market_check('other_owner_gets_only_their_search_notification',notification_b is not null and not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=notification_a));
 perform pg_temp.ca_market_check('cannot_mark_other_notification_read',not public.ca_mark_notification_read(notification_a));
 perform pg_temp.ca_market_as('authenticated',owner_a);
 perform pg_temp.ca_market_check('can_mark_own_notification_read',public.ca_mark_notification_read(notification_a));
 r:=public.ca_list_notifications(1,48);
 perform pg_temp.ca_market_check('own_read_state_returned',exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=notification_a and (x->>'is_read')::boolean));

 -- Hidden listings must disappear even if a notification already exists.
 perform pg_temp.ca_market_as('authenticated',admin_id);
 perform public.ca_admin_status(fresh_id,'gozlemede');
 perform pg_temp.ca_market_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,48);
 perform pg_temp.ca_market_check('pending_notification_metadata_hidden',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'elan_id')::uuid=fresh_id));
 perform pg_temp.ca_market_as('authenticated',admin_id);
 perform public.ca_admin_status(fresh_id,'reddedildi');
 perform pg_temp.ca_market_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,48);
 perform pg_temp.ca_market_check('rejected_notification_metadata_hidden',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'elan_id')::uuid=fresh_id));
 perform pg_temp.ca_market_as('authenticated',admin_id);
 perform public.ca_admin_status(fresh_id,'aktiv');
 perform pg_temp.ca_market_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,48);
 perform pg_temp.ca_market_check('reapproval_does_not_duplicate_notification',1=(select count(*) from jsonb_array_elements(r->'items') x where (x->>'search_id')::uuid=search_a and (x->>'elan_id')::uuid=fresh_id));
 perform pg_temp.ca_market_as('authenticated',owner_b);
 perform public.ca_mark_listing_sold(fresh_id);
 perform pg_temp.ca_market_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,48);
 perform pg_temp.ca_market_check('sold_notification_metadata_hidden',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'elan_id')::uuid=fresh_id));

 -- Processing is capped at 100 new events per visit, independent of preference count.
 perform pg_temp.ca_market_as('none',null);
 select cursor_seq into cursor_before from ca_private.notification_progress where owner_id=owner_a;
 for i in 1..101 loop
  insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,techizat) values(owner_b,marker||'_MATCH','Bulk matching',2020,10000,'aktiv',array['ABS']);
 end loop;
 select max(seq) into last_seq from ca_private.approved_listing_events;
 perform pg_temp.ca_market_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,24);
 perform pg_temp.ca_market_check('notification_processing_exposes_more_work',(r->>'processing')::boolean and jsonb_array_length(r->'items')=24);
 perform pg_temp.ca_market_as('none',null);
 perform pg_temp.ca_market_check('notification_cursor_advances_exactly100_events',(select count(*)=100 from ca_private.approved_listing_events where seq>cursor_before and seq<=(select cursor_seq from ca_private.notification_progress where owner_id=owner_a)));
 perform pg_temp.ca_market_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,24);r2:=public.ca_list_notifications(2,24);
 perform pg_temp.ca_market_check('notification_processing_completes_next_visit',not(r->>'processing')::boolean and (r->>'total')::int>=101 and (r->>'total_pages')::int>=5 and (r2->>'page')::int=2);
 perform pg_temp.ca_market_check('notification_pages_have_no_duplicate_items',not exists(select 1 from jsonb_array_elements(r->'items') a join jsonb_array_elements(r2->'items') b on a->>'id'=b->>'id'));
 perform pg_temp.ca_market_check('mark_all_read_owned_rows',public.ca_mark_notification_read(null));
 r:=public.ca_list_notifications(1,24);
 perform pg_temp.ca_market_check('all_visible_own_notifications_are_read',(r->>'unread_count')::int=0);
 perform pg_temp.ca_market_check('delete_own_saved_search',public.ca_delete_saved_search(search_a) and not public.ca_delete_saved_search(search_a));
 perform pg_temp.ca_market_as('none',null);
 perform pg_temp.ca_market_check('deleting_search_cascades_only_its_notifications',not exists(select 1 from ca_private.search_notifications where search_id=search_a) and exists(select 1 from ca_private.search_notifications where id=notification_b and not is_read));

 -- Enforce the maximum at the API, while allowing a normalized existing retry.
 select count(*) into n from ca_private.saved_searches where owner_id=owner_a;
 perform pg_temp.ca_market_as('authenticated',owner_a);
 for i in n+1..20 loop perform public.ca_save_search('Capacity fixture',jsonb_build_object('make',marker||'_CAP_'||i));end loop;
 perform pg_temp.ca_market_check('search_limit_reached',jsonb_array_length(public.ca_list_saved_searches())=20);
 perform pg_temp.ca_market_check('existing_search_retry_allowed_at_limit',public.ca_save_search('Wrong renamed',jsonb_build_object('make',marker||'_UNFINDABLE'))=wrong_search);
 perform pg_temp.ca_market_error('search21_denied',format('select public.ca_save_search(''Too many'',jsonb_build_object(''make'',%L))',marker||'_CAP_21'),'22023');
 perform pg_temp.ca_market_as('none',null);
 perform pg_temp.ca_market_check('existing_business_listing_rows_unchanged',not exists(select 1 from pg_temp.ca_market_existing_listings b left join public.elanlar e on e.id=b.id where e.id is null or to_jsonb(e) is distinct from b.row_data));
 perform pg_temp.ca_market_check('existing_business_payment_rows_unchanged',not exists(select 1 from pg_temp.ca_market_existing_packages b left join public.paket_sorgulari p on p.id=b.id where p.id is null or to_jsonb(p) is distinct from b.row_data));
 perform pg_temp.ca_market_check('only_optional_transactional_auth_fixture_created',(select count(*)=before_auth_users+synthetic_owner::int from auth.users));
 update ca_private.photo_review_config set enabled=(photo_flags->>'enabled')::boolean,admin_preview=(photo_flags->>'admin_preview')::boolean where singleton;
 perform pg_temp.ca_market_check('photo_review_configuration_restored_within_transaction',(select to_jsonb(c)=photo_flags from ca_private.photo_review_config c where singleton));
end $test$;
select count(*) passed_count,array_agg(name order by name) passed_tests from pg_temp.ca_market_results;
rollback;
