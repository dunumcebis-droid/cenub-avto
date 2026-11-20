-- Run after database/daily-site-visitors.sql. All counter fixtures, role/zone
-- changes and receipt cleanup are transactional and ROLLBACK. No Auth, email,
-- listing, photo, account or provider write occurs. Never replace ROLLBACK.
begin;
create temporary table ca_visit_results(name text primary key);
do $$ begin
 execute format('grant usage on schema %I to anon,authenticated',
  (select nspname from pg_namespace where oid=pg_my_temp_schema()));
end $$;
grant select,insert on ca_visit_results to anon,authenticated;
create function pg_temp.ca_visit_check(p_name text,p_ok boolean)
returns void language plpgsql security invoker set search_path='' as $$
begin
 if p_ok is distinct from true then raise exception 'FAILED: %',p_name;end if;
 insert into pg_temp.ca_visit_results values(p_name);
end $$;
create function pg_temp.ca_visit_error(p_name text,p_sql text,p_state text)
returns void language plpgsql security invoker set search_path='' as $$
declare actual text;
begin
 begin execute p_sql;exception when others then
  get stacked diagnostics actual=returned_sqlstate;
 end;
 perform pg_temp.ca_visit_check(p_name,actual=p_state);
end $$;
create function pg_temp.ca_visit_as(p_role text,p_uid uuid default null)
returns void language plpgsql security invoker set search_path='' as $$
begin
 perform set_config('role','none',true);
 perform set_config('request.jwt.claim.sub',coalesce(p_uid::text,''),true);
 perform set_config('request.jwt.claims',jsonb_build_object('role',p_role,'sub',p_uid)::text,true);
 perform set_config('role',p_role,true);
end $$;
grant execute on function pg_temp.ca_visit_check(text,boolean),
 pg_temp.ca_visit_error(text,text,text),pg_temp.ca_visit_as(text,uuid)
 to anon,authenticated;

do $test$
declare
 d date:=ca_private.site_visit_day(statement_timestamp());
 visitor_a uuid:=gen_random_uuid();visitor_b uuid:=gen_random_uuid();visitor_c uuid:=gen_random_uuid();
 marker text:=gen_random_uuid()::text;
 r jsonb;r2 jsonb;base bigint;historical bigint;old_count bigint;receipt_count bigint;
 role_name text;table_name text;fn text;hash_a text;hash_yesterday text;keep_hash text;
 original_zone text:=current_setting('TimeZone');
begin
 -- The tested helper uses a named zone; client/session timezone cannot change
 -- which date is public, and the caller cannot supply a counting date.
 perform pg_temp.ca_visit_check('baku_before_midnight',ca_private.site_visit_day('2026-11-20 19:59:59+00')='2026-11-20'::date);
 perform pg_temp.ca_visit_check('baku_at_midnight',ca_private.site_visit_day('2026-11-20 20:00:00+00')='2026-11-21'::date);
 perform set_config('TimeZone','Pacific/Kiritimati',true);
 perform pg_temp.ca_visit_check('named_zone_independent_of_session',ca_private.site_visit_day('2026-11-20 19:59:59+00')='2026-11-20'::date);

 foreach table_name in array array['site_visit_totals','site_visit_receipts'] loop
  perform pg_temp.ca_visit_check('rls_'||table_name,(select relrowsecurity from pg_class where oid=('ca_private.'||table_name)::regclass));
  foreach role_name in array array['anon','authenticated'] loop
   perform pg_temp.ca_visit_check('no_table_acl_'||role_name||'_'||table_name,
    not has_table_privilege(role_name,'ca_private.'||table_name,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE'));
  end loop;
 end loop;
 perform pg_temp.ca_visit_check('receipt_stores_date_and_hash_only',
  (select array_agg(attname::text order by attnum)=array['day','visitor_hash']
   from pg_attribute where attrelid='ca_private.site_visit_receipts'::regclass and attnum>0 and not attisdropped));
 perform pg_temp.ca_visit_check('receipt_unique_day_hash_key',
  exists(select 1 from pg_constraint where conrelid='ca_private.site_visit_receipts'::regclass and contype='p'
   and pg_get_constraintdef(oid)='PRIMARY KEY (day, visitor_hash)'));
 foreach fn in array array['ca_private.api_record_site_visit(uuid)','ca_private.api_daily_site_visitors()',
  'public.ca_record_site_visit(uuid)','public.ca_daily_site_visitors()'] loop
  perform pg_temp.ca_visit_check('narrow_security_'||fn,
   (select prosecdef=(split_part(fn,'.',1)='ca_private') and proconfig @> array['search_path=""']
    from pg_proc where oid=fn::regprocedure));
  perform pg_temp.ca_visit_check('no_public_execute_'||fn,
   not exists(select 1 from pg_proc p cross join lateral aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
    where p.oid=fn::regprocedure and a.grantee=0 and a.privilege_type='EXECUTE'));
  perform pg_temp.ca_visit_check('explicit_api_execute_'||fn,
   has_function_privilege('anon',fn,'EXECUTE') and has_function_privilege('authenticated',fn,'EXECUTE'));
 end loop;
 perform pg_temp.ca_visit_check('read_apis_are_stable',
  (select bool_and(provolatile='s') from pg_proc where oid in(
   'public.ca_daily_site_visitors()'::regprocedure,'ca_private.api_daily_site_visitors()'::regprocedure)));

 hash_a:=encode(sha256(convert_to('avtounvan-site-v1:'||d::text||':'||visitor_a::text,'UTF8')),'hex');
 hash_yesterday:=encode(sha256(convert_to('avtounvan-site-v1:'||(d-1)::text||':'||visitor_a::text,'UTF8')),'hex');
 insert into ca_private.site_visit_receipts(day,visitor_hash) values(d-1,hash_yesterday);
 insert into ca_private.site_visit_totals(day,visitors) values(d-1,17) on conflict do nothing;
 select visitors into historical from ca_private.site_visit_totals where day=d-1;

 perform pg_temp.ca_visit_as('anon');
 r:=public.ca_daily_site_visitors();base:=(r->>'visitors')::bigint;
 perform pg_temp.ca_visit_check('public_read_contract',r=jsonb_build_object('day',d,'timezone','Asia/Baku','visitors',base));
 perform pg_temp.ca_visit_check('public_nonnegative_safe_integer',base between 0 and 9007199254740991);
 r:=public.ca_record_site_visit(visitor_a);
 perform pg_temp.ca_visit_check('anonymous_today_counted_despite_yesterday',r=jsonb_build_object('day',d,'timezone','Asia/Baku','visitors',base+1,'counted',true));
 r2:=public.ca_record_site_visit(visitor_a);
 perform pg_temp.ca_visit_check('repeat_does_not_increase',r2=jsonb_build_object('day',d,'timezone','Asia/Baku','visitors',base+1,'counted',false));

 perform pg_temp.ca_visit_as('authenticated',gen_random_uuid());
 r:=public.ca_record_site_visit(visitor_a);
 perform pg_temp.ca_visit_check('login_does_not_double_count_browser',not (r->>'counted')::boolean and (r->>'visitors')::bigint=base+1);
 r:=public.ca_record_site_visit(visitor_b);
 perform pg_temp.ca_visit_check('second_browser_increments_once',(r->>'counted')::boolean and (r->>'visitors')::bigint=base+2);
 perform pg_temp.ca_visit_as('authenticated',gen_random_uuid());
 r:=public.ca_record_site_visit(visitor_b);
 perform pg_temp.ca_visit_check('different_account_same_browser_still_deduped',not (r->>'counted')::boolean and (r->>'visitors')::bigint=base+2);
 perform pg_temp.ca_visit_as('anon');
 perform pg_temp.ca_visit_check('public_total_shared_across_roles',(public.ca_daily_site_visitors()->>'visitors')::bigint=base+2);

 foreach role_name in array array['anon','authenticated'] loop
  perform pg_temp.ca_visit_as(role_name);
  foreach table_name in array array['site_visit_totals','site_visit_receipts'] loop
   perform pg_temp.ca_visit_error('table_read_denied_'||role_name||'_'||table_name,
    format('select * from ca_private.%I limit 1',table_name),'42501');
   perform pg_temp.ca_visit_error('table_delete_denied_'||role_name||'_'||table_name,
    format('delete from ca_private.%I where false',table_name),'42501');
  end loop;
  perform pg_temp.ca_visit_error('count_cannot_be_set_'||role_name,
   'update ca_private.site_visit_totals set visitors=999999','42501');
  perform pg_temp.ca_visit_error('receipt_cannot_be_forged_'||role_name,
   'insert into ca_private.site_visit_receipts values(current_date,repeat(''0'',64))','42501');
  perform pg_temp.ca_visit_error('date_helper_not_callable_'||role_name,
   'select ca_private.site_visit_day(now())','42501');
 end loop;
 perform pg_temp.ca_visit_as('anon');
 perform pg_temp.ca_visit_error('null_id_rejected','select public.ca_record_site_visit(null)','22023');
 perform pg_temp.ca_visit_error('nil_id_rejected',
  'select public.ca_record_site_visit(''00000000-0000-0000-0000-000000000000'')','22023');
 perform pg_temp.ca_visit_error('malformed_uuid_rejected','select public.ca_record_site_visit(''not-a-uuid'')','22P02');
 perform pg_temp.ca_visit_error('no_custom_count_parameter',
  format('select public.ca_record_site_visit(p_visitor=>%L::uuid,p_visitors=>999999)',visitor_a),'42883');
 perform pg_temp.ca_visit_error('no_custom_date_parameter','select public.ca_daily_site_visitors(p_day=>current_date)','42883');
 perform pg_temp.ca_visit_error('no_public_reset_api','select public.ca_reset_site_visitors()','42883');
 perform pg_temp.ca_visit_check('invalid_calls_leave_total_unchanged',(public.ca_daily_site_visitors()->>'visitors')::bigint=base+2);

 perform pg_temp.ca_visit_as('none');
 perform pg_temp.ca_visit_check('stored_receipt_is_daily_sha256',
  exists(select 1 from ca_private.site_visit_receipts where day=d and visitor_hash=hash_a)
  and length(hash_a)=64 and hash_a<>visitor_a::text and hash_a<>hash_yesterday);
 perform pg_temp.ca_visit_check('historical_aggregate_preserved',
  (select visitors from ca_private.site_visit_totals where day=d-1)=historical);
 select count(*) into receipt_count from ca_private.site_visit_receipts;
 perform public.ca_daily_site_visitors();
 perform pg_temp.ca_visit_check('read_does_not_write_receipts',
  (select count(*) from ca_private.site_visit_receipts)=receipt_count);

 -- More than one batch proves cleanup is bounded; current/recent receipts and
 -- all daily aggregates survive. Existing rows are restored by ROLLBACK too.
 insert into ca_private.site_visit_receipts(day,visitor_hash)
 select d-10,encode(sha256(convert_to(marker||':'||i::text,'UTF8')),'hex') from generate_series(1,105) i;
 keep_hash:=encode(sha256(convert_to(marker||':keep','UTF8')),'hex');
 insert into ca_private.site_visit_receipts(day,visitor_hash) values(d-2,keep_hash);
 insert into ca_private.site_visit_totals(day,visitors) values(d-10,211) on conflict do nothing;
 select visitors into historical from ca_private.site_visit_totals where day=d-10;
 select count(*) into old_count from ca_private.site_visit_receipts where day<d-2;
 perform pg_temp.ca_visit_as('anon');
 r:=public.ca_record_site_visit(visitor_c);
 perform pg_temp.ca_visit_check('cleanup_record_still_counts_once',
  (r->>'counted')::boolean and (r->>'visitors')::bigint=base+3);
 perform pg_temp.ca_visit_as('none');
 perform pg_temp.ca_visit_check('old_receipt_cleanup_exactly_one_bounded_batch',
  (select count(*) from ca_private.site_visit_receipts where day<d-2)=old_count-100);
 perform pg_temp.ca_visit_check('recent_dates_retained',
  exists(select 1 from ca_private.site_visit_receipts where day=d-2 and visitor_hash=keep_hash)
  and exists(select 1 from ca_private.site_visit_receipts where day=d-1 and visitor_hash=hash_yesterday)
  and exists(select 1 from ca_private.site_visit_receipts where day=d and visitor_hash=hash_a));
 perform pg_temp.ca_visit_check('cleanup_keeps_historical_aggregate',
  (select visitors from ca_private.site_visit_totals where day=d-10)=historical);
 select count(*) into old_count from ca_private.site_visit_receipts where day<d-2;
 perform pg_temp.ca_visit_as('anon');
 r:=public.ca_record_site_visit(visitor_c);
 perform pg_temp.ca_visit_check('retry_cleanup_does_not_add_visitors',
  not (r->>'counted')::boolean and (r->>'visitors')::bigint=base+3);
 perform pg_temp.ca_visit_as('none');
 perform pg_temp.ca_visit_check('next_request_continues_bounded_cleanup',
  (select count(*) from ca_private.site_visit_receipts where day<d-2)=greatest(0,old_count-100));
 perform set_config('TimeZone',original_zone,true);
end $test$;
select jsonb_build_object('passed',count(*),'checks',jsonb_agg(name order by name)) as daily_site_visitors_regressions from ca_visit_results;
rollback;
