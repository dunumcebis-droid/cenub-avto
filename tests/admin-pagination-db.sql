-- Run with the proposed admin-pagination DDL inside this transaction for a
-- preflight, or against the applied schema. Never replace ROLLBACK with COMMIT.
begin;
create temporary table ca_admin_test_results(name text primary key);
create temporary table ca_admin_test_context as
select (select a.istifadeci_id from public.adminler a join auth.users u on u.id=a.istifadeci_id limit 1) admin_id,
 (select u.id from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) limit 1) owner_id,
 'CA_ADMIN_TEST_'||replace(gen_random_uuid()::text,'-','') marker,
 (select md5(jsonb_agg(to_jsonb(e) order by e.id)::text) from public.elanlar e) listing_hash,
 (select md5(jsonb_agg(to_jsonb(p) order by p.id)::text) from public.paket_sorgulari p) payment_hash;
grant select on ca_admin_test_context to authenticated,anon;
grant insert on ca_admin_test_results to authenticated,anon;
do $test$ begin
 execute format('grant usage on schema %I to authenticated,anon',(select nspname from pg_namespace where oid=pg_my_temp_schema()));
 if exists(select 1 from pg_temp.ca_admin_test_context where admin_id is null or owner_id is null) then raise exception 'Missing existing test identities';end if;
end; $test$;
create function pg_temp.ca_admin_check(n text,ok boolean) returns void language plpgsql security invoker as $test$
begin if ok is distinct from true then raise exception 'FAILED: %',n;end if;insert into pg_temp.ca_admin_test_results values(n);end;$test$;
grant execute on function pg_temp.ca_admin_check(text,boolean) to authenticated,anon;

create temporary table ca_admin_fixture_ids as
select gen_random_uuid() id,g.n from generate_series(1,1205) g(n);
insert into public.elanlar(id,satici_id,marka,model,il,qiymet,veziyyet,yaradildi,ca_data)
select f.id,c.owner_id,c.marker,'Model-'||lpad(f.n::text,4,'0'),2020,f.n,
 case when f.n=1 then 'gozlemede' else 'aktiv' end,
 now()-f.n*interval '1 second','{}'::jsonb
from ca_admin_fixture_ids f cross join ca_admin_test_context c;
-- The oldest pending listing is deliberately outside the old newest1000 cap.
update public.elanlar set veziyyet='gozlemede' where id=(select id from ca_admin_fixture_ids where n=1205);
insert into public.paket_sorgulari(elan_id,satici_id,paket_adi,odenis_veziyyeti,yaradilib)
select f.id,c.owner_id,'VIP',case when f.n=1205 then 'gozlemede' else 'tesdiqlendi' end,
 now()-f.n*interval '1 second' from ca_admin_fixture_ids f cross join ca_admin_test_context c;

set local role authenticated;
do $test$ declare c record;begin select * into c from pg_temp.ca_admin_test_context;
 perform set_config('request.jwt.claim.sub',c.admin_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',c.admin_id,'role','authenticated')::text,true);end;$test$;
with pages as materialized (
 select g.n,public.ca_admin_browse_listings('all',c.marker,g.n,24) d
 from pg_temp.ca_admin_test_context c cross join generate_series(1,51) g(n)
), ids as (select e->>'id' id from pages cross join lateral jsonb_array_elements(d->'items') e)
select pg_temp.ca_admin_check('all_1205_ads_reachable_without_duplicates',
 (select count(*)=1205 and count(distinct id)=1205 from ids)
 and (select bool_and((d->>'total')::int=1205 and (d->>'total_pages')::int=51) from pages));
with r as(select public.ca_admin_browse_listings('gozlemede',marker,1,24) d from pg_temp.ca_admin_test_context)
select pg_temp.ca_admin_check('old_pending_listing_visible_with_server_filter',
 (d->>'total')::int=2 and exists(select 1 from jsonb_array_elements(d->'items') e where e->>'model'='Model-1205')) from r;
with r as(select public.ca_admin_browse_listings('all',marker||' Model-1205',1,24) d from pg_temp.ca_admin_test_context)
select pg_temp.ca_admin_check('search_finds_old_record_across_all_pages',(d->>'total')::int=1) from r;
with r as(select public.ca_admin_browse_listings('all',marker,999999,24) d from pg_temp.ca_admin_test_context)
select pg_temp.ca_admin_check('out_of_range_page_clamps_to_last_page',
 (d->>'page')::int=51 and jsonb_array_length(d->'items')=5) from r;
with r as(select public.ca_admin_browse_listings('all',marker,1,24) d from pg_temp.ca_admin_test_context)
select pg_temp.ca_admin_check('admin_metadata_excludes_private_notes_and_images',
 not exists(select 1 from jsonb_array_elements(d->'items') e where e?'paket_tesdiq_qeydi' or e?'ca_data' or e?'sekiller')) from r;
with pages as materialized (
 select public.ca_admin_browse_payments('all',c.marker,g.n,24) d
 from pg_temp.ca_admin_test_context c cross join generate_series(1,51) g(n)
), ids as (select e->>'id' id from pages cross join lateral jsonb_array_elements(d->'items') e)
select pg_temp.ca_admin_check('all_1205_payment_requests_reachable_without_duplicates',
 (select count(*)=1205 and count(distinct id)=1205 from ids)
 and (select bool_and((d->>'total')::int=1205) from pages));
with r as(select public.ca_admin_browse_payments('gozlemede',marker,1,24) d from pg_temp.ca_admin_test_context)
select pg_temp.ca_admin_check('old_pending_payment_request_visible',(d->>'total')::int=1 and d->'items'->0->>'model'='Model-1205') from r;
do $test$ declare blocked boolean:=false;begin
 begin perform public.ca_admin_browse_listings('invalid','',1,24);exception when invalid_parameter_value then blocked:=true;end;
 perform pg_temp.ca_admin_check('invalid_status_rejected',blocked);
end;$test$;
reset role;
set local role authenticated;
do $test$ declare c record;n text;blocked boolean;begin
 select * into c from pg_temp.ca_admin_test_context;
 perform set_config('request.jwt.claim.sub',c.owner_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',c.owner_id,'role','authenticated')::text,true);
 foreach n in array array['ca_admin_browse_listings','ca_admin_browse_payments'] loop
  blocked:=false;begin execute format('select public.%I()',n);exception when insufficient_privilege then blocked:=true;end;
  perform pg_temp.ca_admin_check('non_admin_denied_'||n,blocked);
 end loop;
end;$test$;
reset role;
set local role anon;
do $test$ declare n text;blocked boolean;begin
 perform set_config('request.jwt.claim.sub','',true);perform set_config('request.jwt.claims','{"role":"anon"}',true);
 foreach n in array array['ca_admin_browse_listings','ca_admin_browse_payments'] loop
  blocked:=false;begin execute format('select public.%I()',n);exception when insufficient_privilege then blocked:=true;end;
  perform pg_temp.ca_admin_check('anon_denied_'||n,blocked);
 end loop;
end;$test$;
reset role;
select pg_temp.ca_admin_check('new_and_changed_admin_read_functions_are_invoker',not exists(
 select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public'
 and p.proname in('ca_admin_list','ca_admin_browse_listings','ca_admin_browse_payments') and p.prosecdef));
select pg_temp.ca_admin_check('existing_listing_rows_unchanged',c.listing_hash=(
 select md5(jsonb_agg(to_jsonb(e) order by e.id)::text) from public.elanlar e where not exists(select 1 from ca_admin_fixture_ids f where f.id=e.id))) from ca_admin_test_context c;
select pg_temp.ca_admin_check('existing_payment_rows_unchanged',c.payment_hash=(
 select md5(jsonb_agg(to_jsonb(p) order by p.id)::text) from public.paket_sorgulari p where not exists(select 1 from ca_admin_fixture_ids f where f.id=p.elan_id))) from ca_admin_test_context c;
select count(*) passed_count,array_agg(name order by name) passed_tests from ca_admin_test_results;
rollback;
