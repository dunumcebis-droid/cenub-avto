-- Cash/credit/barter authorization and matching checks. Run after sale-options.sql.
-- Synthetic rows only, with one optional Auth identity inside BEGIN...ROLLBACK.
-- No account API, email, HTTP, stored-image upload or permanent change is made.
-- Never replace ROLLBACK with COMMIT. Output contains test names/counts only.
begin;
create temporary table ca_sale_results(name text primary key);
create temporary table ca_sale_original_listings as select id,to_jsonb(e) row_data from public.elanlar e;
create temporary table ca_sale_original_packages as select id,to_jsonb(p) row_data from public.paket_sorgulari p;
do $$begin
 execute format('grant usage on schema %I to anon,authenticated',(select nspname from pg_namespace where oid=pg_my_temp_schema()));
end$$;
grant select,insert on ca_sale_results to anon,authenticated;
create function pg_temp.ca_sale_check(p_name text,p_ok boolean)
returns void language plpgsql security invoker set search_path='' as $$
begin
 if p_ok is distinct from true then raise exception 'FAILED: %',p_name;end if;
 insert into pg_temp.ca_sale_results values(p_name);
end$$;
create function pg_temp.ca_sale_error(p_name text,p_sql text,p_state text)
returns void language plpgsql security invoker set search_path='' as $$
declare blocked boolean:=false;actual text;
begin
 begin execute p_sql;exception when others then get stacked diagnostics actual=returned_sqlstate;blocked:=actual=p_state;end;
 perform pg_temp.ca_sale_check(p_name,blocked);
end$$;
create function pg_temp.ca_sale_as(p_role text,p_uid uuid)
returns void language plpgsql security invoker set search_path='' as $$
begin
 perform set_config('role','none',true);
 perform set_config('request.jwt.claim.sub',coalesce(p_uid::text,''),true);
 perform set_config('request.jwt.claims',case when p_uid is null then jsonb_build_object('role',p_role)::text else jsonb_build_object('sub',p_uid,'role',p_role)::text end,true);
 perform set_config('role',p_role,true);
end$$;
grant execute on function pg_temp.ca_sale_check(text,boolean),pg_temp.ca_sale_error(text,text,text),pg_temp.ca_sale_as(text,uuid) to anon,authenticated;

do $test$
declare
 admin_id uuid;owner_a uuid;owner_b uuid;ids uuid[];
 marker text:='CA_SALE_ROLLBACK_'||replace(gen_random_uuid()::text,'-','');
 cash_id uuid:=gen_random_uuid();credit_id uuid:=gen_random_uuid();barter_id uuid:=gen_random_uuid();combo_id uuid:=gen_random_uuid();
 legacy_id uuid:=gen_random_uuid();encoded_id uuid:=gen_random_uuid();sold_id uuid:=gen_random_uuid();pending_id uuid:=gen_random_uuid();
 rejected_id uuid:=gen_random_uuid();deleted_id uuid:=gen_random_uuid();own_id uuid:=gen_random_uuid();vip_credit_id uuid:=gen_random_uuid();vip_barter_id uuid:=gen_random_uuid();
 probe_id uuid:=gen_random_uuid();fixture_id uuid;
 new_credit uuid:=gen_random_uuid();new_barter uuid:=gen_random_uuid();new_cash uuid:=gen_random_uuid();new_combo uuid:=gen_random_uuid();new_own uuid:=gen_random_uuid();new_wrong uuid:=gen_random_uuid();
 search_credit uuid;search_barter uuid;search_cash uuid;search_default uuid;
 before_auth bigint;synthetic_owner boolean:=false;photo_flags jsonb;base_time timestamptz;last_seq bigint;
 i integer;j integer;n integer;affected integer;r jsonb;row jsonb;f jsonb;options jsonb;kind text;filters jsonb[];
 picture constant text:='https://fixture.invalid/sale-front.jpg';
begin
 select count(*) into before_auth from auth.users;
 select a.istifadeci_id into admin_id from public.adminler a join auth.users u on u.id=a.istifadeci_id order by u.created_at,u.id limit 1;
 select array_agg(id order by created_at,id) into ids from(select u.id,u.created_at from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) order by u.created_at,u.id limit 2)t;
 owner_a:=ids[1];owner_b:=ids[2];
 if admin_id is null or owner_a is null then raise exception 'SETUP: an existing admin and nonadmin identity are required';end if;
 if owner_b is null then
  owner_b:=gen_random_uuid();synthetic_owner:=true;
  insert into auth.users(id,email,aud,role,raw_app_meta_data,raw_user_meta_data,created_at,updated_at)
  values(owner_b,'ca-sale-rollback-'||owner_b::text||'@fixture.invalid','authenticated','authenticated','{}','{}',now(),now());
 end if;
 select to_jsonb(c) into photo_flags from ca_private.photo_review_config c where singleton;
 update ca_private.photo_review_config set enabled=false,admin_preview=false where singleton;
 select greatest(now(),coalesce(max(yaradildi),now()))+interval '1 hour' into base_time from public.elanlar;

 -- The normalizer reads input only; it grants no table or private-helper access.
 perform pg_temp.ca_sale_check('normalizer_is_pure_invoker_immutable',(select not prosecdef and provolatile='i' and proconfig=array['search_path=""']::text[] from pg_proc where oid='public.ca_listing_sale_options(jsonb)'::regprocedure));
 perform pg_temp.ca_sale_check('normalizer_allowed_to_public_roles',has_function_privilege('anon','public.ca_listing_sale_options(jsonb)','EXECUTE') and has_function_privilege('authenticated','public.ca_listing_sale_options(jsonb)','EXECUTE'));
 perform pg_temp.ca_sale_check('write_guard_not_directly_callable',not has_function_privilege('anon','ca_private.check_listing_sale_options()','EXECUTE') and not has_function_privilege('authenticated','ca_private.check_listing_sale_options()','EXECUTE'));
 perform pg_temp.ca_sale_check('search_match_stays_private',not has_function_privilege('anon','ca_private.search_matches(uuid,jsonb)','EXECUTE') and not has_function_privilege('authenticated','ca_private.search_matches(uuid,jsonb)','EXECUTE'));
 perform pg_temp.ca_sale_check('saved_filter_helper_stays_private',not has_function_privilege('anon','ca_private.clean_saved_filters(jsonb)','EXECUTE') and not has_function_privilege('authenticated','ca_private.clean_saved_filters(jsonb)','EXECUTE'));
 perform pg_temp.ca_sale_check('browse_keeps_invoker_stable',(select not prosecdef and provolatile='s' from pg_proc where oid='public.ca_browse_listings(jsonb,integer,integer)'::regprocedure));

 perform pg_temp.ca_sale_as('anon',null);
 perform pg_temp.ca_sale_check('legacy_absent_defaults_cash',public.ca_listing_sale_options('{}')=array['cash']);
 perform pg_temp.ca_sale_check('sql_null_defaults_cash',public.ca_listing_sale_options(null)=array['cash']);
 perform pg_temp.ca_sale_check('json_null_defaults_cash',public.ca_listing_sale_options('null')=array['cash']);
 perform pg_temp.ca_sale_check('nonobject_defaults_cash',public.ca_listing_sale_options('[]')=array['cash']);
 perform pg_temp.ca_sale_check('malformed_legacy_string_defaults_cash',public.ca_listing_sale_options(to_jsonb('broken {'::text))=array['cash']);
 perform pg_temp.ca_sale_check('explicit_cash_only',public.ca_listing_sale_options('{"saleOptions":["cash"]}')=array['cash']);
 perform pg_temp.ca_sale_check('explicit_credit_only',public.ca_listing_sale_options('{"saleOptions":["credit"]}')=array['credit']);
 perform pg_temp.ca_sale_check('explicit_barter_only',public.ca_listing_sale_options('{"saleOptions":["barter"]}')=array['barter']);
 perform pg_temp.ca_sale_check('normalizer_deduplicates_fixed_order',public.ca_listing_sale_options('{"saleOptions":["barter","cash","credit","cash"]}')=array['cash','credit','barter']);
 perform pg_temp.ca_sale_check('normalizer_preserves_credit_barter_without_cash',public.ca_listing_sale_options('{"saleOptions":["barter","credit"]}')=array['credit','barter']);
 perform pg_temp.ca_sale_check('encoded_object_choices_are_read',public.ca_listing_sale_options(to_jsonb('{"saleOptions":["credit","barter"]}'::text))=array['credit','barter']);
 perform pg_temp.ca_sale_check('old_flags_or_package_do_not_infer_credit_or_barter',public.ca_listing_sale_options('{"credit":true,"barter":true,"pack":"VIP"}')=array['cash']);
 perform pg_temp.ca_sale_check('unknown_or_nonstring_choices_do_not_create_offer',public.ca_listing_sale_options('{"saleOptions":[true,{},3,"unknown"]}')=array['cash']);
 perform pg_temp.ca_sale_check('mixed_legacy_values_keep_only_real_choices',public.ca_listing_sale_options('{"saleOptions":[null,{},"credit","unknown"]}')=array['credit']);
 perform pg_temp.ca_sale_as('none',null);

 insert into public.elanlar(id,satici_id,marka,model,il,qiymet,yurus,seher,veziyyet,sekiller,ca_data,paket_adi,yaradildi)
 values(cash_id,owner_b,marker,'Cash',2020,10000,100,'Bakı','aktiv',array[picture],'{"saleOptions":["cash"]}','Pulsuz',base_time),
 (credit_id,owner_b,marker,'Credit',2021,20000,200,'Bakı','aktiv',array[picture],'{"saleOptions":["credit"]}','Pulsuz',base_time),
 (barter_id,owner_b,marker,'Barter',2022,30000,300,'Bakı','aktiv',array[picture],'{"saleOptions":["barter"]}','Pulsuz',base_time),
 (combo_id,owner_b,marker,'Credit and barter',2023,40000,400,'Bakı','aktiv',array[picture],'{"saleOptions":["credit","barter"]}','Pulsuz',base_time),
 (legacy_id,owner_b,marker,'Legacy',2020,50000,500,'Lənkəran','aktiv',array[picture],'{}','Pulsuz',base_time),
 (encoded_id,owner_b,marker,'Encoded choices',2020,60000,600,'Bakı','aktiv',array[picture],to_jsonb('{"saleOptions":["credit","barter"]}'::text),'Pulsuz',base_time),
 (pending_id,owner_b,marker,'Pending credit',2020,100,0,'Bakı','gozlemede',array[picture],'{"saleOptions":["credit"]}','Pulsuz',base_time);

 insert into public.elanlar(id,satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data,paket_adi,yaradildi,is_sold)
 values(sold_id,owner_b,marker,'Sold credit',2020,100,'aktiv',array[picture],'{"saleOptions":["credit"]}','Pulsuz',base_time,true),
 (rejected_id,owner_b,marker,'Rejected barter',2020,100,'reddedildi',array[picture],'{"saleOptions":["barter"]}','Pulsuz',base_time,false),
 (deleted_id,owner_b,marker,'Archived credit',2020,100,'silindi',array[picture],'{"saleOptions":["credit"]}','Pulsuz',base_time,false),
 (own_id,owner_a,marker,'Owner edit',2020,100,'gozlemede',array[picture],'{"saleOptions":["cash"]}','Pulsuz',base_time,false);
 insert into public.elanlar(id,satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data,paket_adi,paket_baslayir,paket_bitir,yaradildi)
 values(vip_credit_id,owner_b,marker,'VIP credit',2020,70000,'aktiv',array[picture],'{"saleOptions":["credit"]}','VIP',now()-interval '1 day',now()+interval '1 day',base_time),
 (vip_barter_id,owner_b,marker,'VIP barter',2020,80000,'aktiv',array[picture],'{"saleOptions":["barter"]}','VIP',now()-interval '1 day',now()+interval '1 day',base_time);
 for i in 1..8 loop
  insert into public.elanlar(satici_id,marka,model,il,qiymet,veziyyet,sekiller,ca_data,paket_adi,paket_baslayir,paket_bitir,yaradildi)
  values(owner_b,marker,'Newer VIP cash '||i,2020,90000+i,'aktiv',array[picture],'{"saleOptions":["cash"]}','VIP',now()-interval '1 day',now()+interval '1 day',base_time+make_interval(mins=>i));
 end loop;

 -- Probe old malformed metadata on a temporary table. No production trigger is disabled.
 create temporary table ca_sale_guard_probe (like public.elanlar including defaults);
 insert into pg_temp.ca_sale_guard_probe(id,satici_id,marka,model,il,qiymet,ca_data)
 values(probe_id,owner_a,marker,'Old invalid choices',2020,100,'{"saleOptions":[]}');
 create trigger ca_sale_probe_guard before insert or update on pg_temp.ca_sale_guard_probe for each row execute function ca_private.check_listing_sale_options();
 grant select,insert,update on pg_temp.ca_sale_guard_probe to authenticated;

 perform pg_temp.ca_sale_as('authenticated',owner_a);
 update public.elanlar set ca_data='{"saleOptions":["barter","cash","cash"]}' where id=own_id;
 perform pg_temp.ca_sale_check('valid_owner_choices_are_canonicalized',exists(select 1 from public.elanlar where id=own_id and ca_data->'saleOptions'='["cash","barter"]'));
 update public.elanlar set ca_data=to_jsonb('{"saleOptions":["barter","credit"]}'::text) where id=own_id;
 perform pg_temp.ca_sale_check('encoded_metadata_shape_is_retained',exists(select 1 from public.elanlar where id=own_id and jsonb_typeof(ca_data)='string' and (ca_data#>>'{}')::jsonb->'saleOptions'='["credit","barter"]'));
 i:=0;
 for options in select value from jsonb_array_elements('[[],["credit","bad"],["cash",null],[true],["cash",5],["cash",{}],["cash","cash","cash","cash"],"credit",null,{"credit":true}]'::jsonb) loop
  i:=coalesce(i,0)+1;
  perform pg_temp.ca_sale_error('invalid_changed_choices_denied_'||i,format('update public.elanlar set ca_data=%L::jsonb where id=%L',jsonb_build_object('saleOptions',options)::text,own_id),'23514');
 end loop;
 perform pg_temp.ca_sale_error('invalid_new_listing_choices_denied',format('insert into public.elanlar(satici_id,marka,model,il,qiymet,ca_data) values(%L,%L,''Bad choices'',2020,100,''{"saleOptions":[]}'')',owner_a,marker),'23514');
 update pg_temp.ca_sale_guard_probe set qiymet=200,ca_data=jsonb_set(ca_data,'{description}','"Metadata edit"') where id=probe_id;
 perform pg_temp.ca_sale_check('unchanged_invalid_legacy_options_allow_other_edits',exists(select 1 from pg_temp.ca_sale_guard_probe where id=probe_id and qiymet=200 and ca_data->'saleOptions'='[]'));
 update pg_temp.ca_sale_guard_probe set ca_data='{"saleOptions":["credit"]}' where id=probe_id;
 perform pg_temp.ca_sale_check('legacy_invalid_options_can_be_repaired',exists(select 1 from pg_temp.ca_sale_guard_probe where id=probe_id and ca_data->'saleOptions'='["credit"]'));
 update public.elanlar set qiymet=101 where id=legacy_id;get diagnostics affected=row_count;
 perform pg_temp.ca_sale_check('other_owner_cannot_edit_legacy_listing',affected=0);
 perform pg_temp.ca_sale_as('none',null);
 perform pg_temp.ca_sale_check('other_owner_edit_did_not_change_row',exists(select 1 from public.elanlar where id=legacy_id and qiymet=50000));

 perform pg_temp.ca_sale_as('anon',null);
 r:=public.ca_browse_listings(jsonb_build_object('make',marker),1,48);
 perform pg_temp.ca_sale_check('unfiltered_legacy_and_all_sale_choices_remain_visible',(r->>'total')::int=16);
 perform pg_temp.ca_sale_check('featured_default_limit_excludes_older_credit_fixture',jsonb_array_length(r->'vip_items')=6 and not exists(select 1 from jsonb_array_elements(r->'vip_items') x where (x->>'id')::uuid in(vip_credit_id,vip_barter_id)));
 foreach kind in array array['cash','credit','barter'] loop
  r:=public.ca_browse_listings(jsonb_build_object('make',marker,'saleType',kind),1,48);
  perform pg_temp.ca_sale_check('browse_count_'||kind,(r->>'total')::int=case kind when 'cash' then 10 when 'credit' then 4 else 4 end);
  perform pg_temp.ca_sale_check('browse_items_all_match_'||kind,not exists(select 1 from jsonb_array_elements(r->'items') x where not(kind=any(public.ca_listing_sale_options(x->'ca_data')))));
  perform pg_temp.ca_sale_check('featured_items_all_match_'||kind,not exists(select 1 from jsonb_array_elements(r->'vip_items') x where not(kind=any(public.ca_listing_sale_options(x->'ca_data')))));
  perform pg_temp.ca_sale_check('hidden_states_excluded_'||kind,not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid in(sold_id,pending_id,rejected_id,deleted_id,own_id)));
  perform pg_temp.ca_sale_check('public_projection_still29_columns_'||kind,not exists(select 1 from jsonb_array_elements(r->'items') x where (select count(*) from jsonb_object_keys(x))<>29 or x?'paket_tesdiq_qeydi' or x?'is_sold'));
 end loop;
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'saleType','cash'),1,48);
 perform pg_temp.ca_sale_check('legacy_no_option_is_cash_only',exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=legacy_id));
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'saleType','credit'),1,48);
 perform pg_temp.ca_sale_check('credit_does_not_include_cash_legacy',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid in(cash_id,legacy_id)));
 perform pg_temp.ca_sale_check('credit_featured_filter_happens_before_limit',exists(select 1 from jsonb_array_elements(r->'vip_items') x where (x->>'id')::uuid=vip_credit_id));
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'saleType','barter'),1,48);
 perform pg_temp.ca_sale_check('barter_featured_filter_happens_before_limit',exists(select 1 from jsonb_array_elements(r->'vip_items') x where (x->>'id')::uuid=vip_barter_id));
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'saleType','credit','priceMax',25000),1,48);
 perform pg_temp.ca_sale_check('sale_filter_combines_with_price',(r->>'total')::int=1 and (r->'items'->0->>'id')::uuid=credit_id);
 r:=public.ca_browse_listings(jsonb_build_object('make',marker,'saleType','credit','pack','Pulsuz','sort','priceAsc'),1,48);
 perform pg_temp.ca_sale_check('sale_filter_combines_with_package_and_sort',(select array_agg((x->>'id')::uuid order by ord) from jsonb_array_elements(r->'items') with ordinality q(x,ord))=array[credit_id,combo_id,encoded_id]);
 foreach f in array array['{"saleType":""}'::jsonb,'{"saleType":null}'::jsonb] loop
  r:=public.ca_browse_listings(f||jsonb_build_object('make',marker),1,48);
  perform pg_temp.ca_sale_check('empty_sale_filter_means_all_'||case when f->'saleType'='null' then 'null' else 'string' end,(r->>'total')::int=16);
 end loop;
 i:=0;
 for f in select value from jsonb_array_elements('[{"saleType":"loan"},{"saleType":"Credit"},{"saleType":3},{"saleType":true},{"saleType":["cash"]}]') loop
  i:=i+1;
  perform pg_temp.ca_sale_error('invalid_browse_sale_filter_denied_'||i,format('select public.ca_browse_listings(%L,1,24)',f::text),'22023');
 end loop;
 perform pg_temp.ca_sale_as('none',null);

 -- The private notification matcher must use the same public-sale predicate.
 filters:=array[jsonb_build_object('make',marker,'saleType','cash'),jsonb_build_object('make',marker,'saleType','credit'),jsonb_build_object('make',marker,'saleType','barter'),jsonb_build_object('make',marker,'saleType','credit','priceMax',25000)];
 i:=0;
 foreach f in array filters loop
  i:=i+1;r:=public.ca_browse_listings(f,1,48);
  j:=0;
  foreach fixture_id in array array[cash_id,credit_id,barter_id,combo_id,legacy_id,encoded_id,sold_id,pending_id,rejected_id,deleted_id] loop
   j:=j+1;perform pg_temp.ca_sale_check('notification_matcher_parity_'||i||'_'||j,ca_private.search_matches(fixture_id,f)=exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'id')::uuid=fixture_id));
  end loop;
 end loop;

 select count(*) into n from ca_private.saved_searches where owner_id=owner_a;
 if n>16 then raise exception 'SETUP: fixture owner needs four spare saved-search slots';end if;
 select coalesce(max(seq),0) into last_seq from ca_private.approved_listing_events;
 insert into ca_private.notification_progress(owner_id,cursor_seq) values(owner_a,last_seq) on conflict(owner_id) do update set cursor_seq=excluded.cursor_seq;
 perform pg_temp.ca_sale_as('authenticated',owner_a);
 search_credit:=public.ca_save_search('Credit fixture',jsonb_build_object('make',marker||'_NEW','saleType','credit'));
 search_barter:=public.ca_save_search('Barter fixture',jsonb_build_object('make',marker||'_NEW','saleType','barter'));
 search_cash:=public.ca_save_search('Cash fixture',jsonb_build_object('make',marker||'_NEW','saleType','cash'));
 search_default:=public.ca_save_search('All fixture',jsonb_build_object('make',marker||'_NEW','saleType',''));
 r:=public.ca_list_saved_searches();
 perform pg_temp.ca_sale_check('saved_search_retains_sale_type',exists(select 1 from jsonb_array_elements(r) x where (x->>'id')::uuid=search_credit and x->'filters'->>'saleType'='credit'));
 perform pg_temp.ca_sale_check('empty_saved_sale_type_is_omitted',exists(select 1 from jsonb_array_elements(r) x where (x->>'id')::uuid=search_default and not(x->'filters'?'saleType')));
 perform pg_temp.ca_sale_check('null_saved_sale_filter_deduplicates_default',public.ca_save_search('All renamed',jsonb_build_object('make',marker||'_NEW','saleType',null))=search_default);
 perform pg_temp.ca_sale_check('distinct_sale_types_are_distinct_saved_searches',search_credit<>search_barter and search_credit<>search_cash and search_cash<>search_default);
 i:=0;
 for f in select value from jsonb_array_elements('[{"saleType":"loan"},{"saleType":"Credit"},{"saleType":3},{"saleType":true},{"saleType":["cash"]}]') loop
  i:=i+1;perform pg_temp.ca_sale_error('invalid_saved_sale_filter_denied_'||i,format('select public.ca_save_search(''Invalid'',%L)',f::text),'22023');
 end loop;
 r:=public.ca_list_notifications(1,24);
 perform pg_temp.ca_sale_check('saved_search_does_not_backfill_history',not exists(select 1 from jsonb_array_elements(r->'items') x where (x->>'search_id')::uuid in(search_credit,search_barter,search_cash,search_default)));
 perform pg_temp.ca_sale_as('none',null);
 insert into public.elanlar(id,satici_id,marka,model,il,qiymet,veziyyet,ca_data)
 values(new_credit,owner_b,marker||'_NEW','Fresh credit',2020,100,'gozlemede','{"saleOptions":["credit"]}'),
 (new_barter,owner_b,marker||'_NEW','Fresh barter',2020,100,'gozlemede','{"saleOptions":["barter"]}'),
 (new_cash,owner_b,marker||'_NEW','Fresh legacy cash',2020,100,'gozlemede','{}'),
 (new_combo,owner_b,marker||'_NEW','Fresh combo',2020,100,'gozlemede','{"saleOptions":["credit","barter"]}'),
 (new_own,owner_a,marker||'_NEW','Own credit',2020,100,'gozlemede','{"saleOptions":["credit"]}'),
 (new_wrong,owner_b,marker||'_OTHER','Wrong make credit',2020,100,'gozlemede','{"saleOptions":["credit"]}');
 perform pg_temp.ca_sale_as('authenticated',admin_id);
 foreach fixture_id in array array[new_credit,new_barter,new_cash,new_combo,new_own,new_wrong] loop perform public.ca_admin_status(fixture_id,'aktiv');end loop;
 perform pg_temp.ca_sale_as('authenticated',owner_a);
 r:=public.ca_list_notifications(1,24);
 perform pg_temp.ca_sale_as('none',null);
 perform pg_temp.ca_sale_check('credit_search_notifies_only_credit_and_combo',(select array_agg(elan_id order by elan_id) from ca_private.search_notifications where search_id=search_credit)=(select array_agg(id order by id) from unnest(array[new_credit,new_combo]) id));
 perform pg_temp.ca_sale_check('barter_search_notifies_only_barter_and_combo',(select array_agg(elan_id order by elan_id) from ca_private.search_notifications where search_id=search_barter)=(select array_agg(id order by id) from unnest(array[new_barter,new_combo]) id));
 perform pg_temp.ca_sale_check('cash_search_notifies_legacy_cash_only',(select array_agg(elan_id) from ca_private.search_notifications where search_id=search_cash)=array[new_cash]);
 perform pg_temp.ca_sale_check('all_search_notifies_four_new_other_owner_listings',(select count(*) from ca_private.search_notifications where search_id=search_default)=4);
 perform pg_temp.ca_sale_check('wrong_make_and_own_listings_do_not_notify',not exists(select 1 from ca_private.search_notifications where search_id in(search_credit,search_barter,search_cash,search_default) and elan_id in(new_wrong,new_own)));

 perform pg_temp.ca_sale_check('original_business_listing_rows_unchanged',not exists(select 1 from pg_temp.ca_sale_original_listings b left join public.elanlar e on e.id=b.id where e.id is null or to_jsonb(e) is distinct from b.row_data));
 perform pg_temp.ca_sale_check('original_package_rows_unchanged',not exists(select 1 from pg_temp.ca_sale_original_packages b left join public.paket_sorgulari p on p.id=b.id where p.id is null or to_jsonb(p) is distinct from b.row_data));
 perform pg_temp.ca_sale_check('only_optional_transactional_auth_fixture_created',(select count(*)=before_auth+synthetic_owner::int from auth.users));
 update ca_private.photo_review_config set enabled=(photo_flags->>'enabled')::boolean,admin_preview=(photo_flags->>'admin_preview')::boolean where singleton;
 perform pg_temp.ca_sale_check('photo_review_flags_restored',(select to_jsonb(c)=photo_flags from ca_private.photo_review_config c where singleton));
end $test$;
select count(*) passed_count,array_agg(name order by name) passed_tests from pg_temp.ca_sale_results;
rollback;
