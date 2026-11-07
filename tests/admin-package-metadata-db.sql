-- Admin package feedback regressions. Run after the proposed DDL, or place its
-- DDL after BEGIN for preflight. Only generated fixtures are modified. Existing
-- users/listings/payments/photos/packages are never changed. Never COMMIT.
begin;
create temporary table ca_pkg_results(name text primary key);
create temporary table ca_pkg_context as
select
 (select a.istifadeci_id from public.adminler a join auth.users u on u.id=a.istifadeci_id limit 1) admin_id,
 (select u.id from auth.users u where not exists(select 1 from public.adminler a where a.istifadeci_id=u.id) limit 1) owner_id,
 'CA_PACKAGE_TEST_'||replace(gen_random_uuid()::text,'-','') marker,
 (select md5(jsonb_agg(to_jsonb(e) order by e.id)::text) from public.elanlar e) listing_hash,
 (select md5(jsonb_agg(to_jsonb(p) order by p.id)::text) from public.paket_sorgulari p) payment_hash,
 now()-interval '1 day' expected_start,now()+interval '14 days' expected_end;
create temporary table ca_pkg_fixture_ids as
select gen_random_uuid() id,v.scenario,v.n from (values
 ('free',1),('vip_pending',2),('premium_pending',3),('standard_confirmed',4),
 ('vip_confirmed_edit',5),('premium_rejected',6),('legacy_missing',7),
 ('canonical_vip',8),('forged_pack',9),('latest_rejected',10),('same_name_pending',11)
) v(scenario,n)
union all select gen_random_uuid(),'bulk_'||g.n,100+g.n from generate_series(1,25) g(n);
create temporary table ca_pkg_request_ids as
select gen_random_uuid() id,v.scenario,v.package,v.status,now()-v.age as created
from (values
 ('vip_pending','VIP','gozlemede',interval '30 days'),
 ('premium_pending','Premium','gozlemede',interval '2 days'),
 ('standard_confirmed','Standart','tesdiqlendi',interval '2 days'),
 ('vip_confirmed_edit','VIP','tesdiqlendi',interval '2 days'),
 ('premium_rejected','Premium','reddedildi',interval '2 days'),
 ('latest_rejected','Premium','reddedildi',interval '10 days'),
 ('latest_rejected','VIP','gozlemede',interval '11 days'),
 ('same_name_pending','VIP','gozlemede',interval '1 hour')
) v(scenario,package,status,age)
union all select gen_random_uuid(),'bulk_'||g.n,'VIP','gozlemede',now()-g.n*interval '1 minute'
from generate_series(1,25) g(n);
-- Deliberate cross-table UUID collision: a different same-name listing has the
-- old target request's UUID. The existing exact-request test must still return
-- only that request, never the colliding listing's newer request.
update ca_pkg_fixture_ids set id=(select id from ca_pkg_request_ids where scenario='vip_pending')
 where scenario='same_name_pending';
grant select on ca_pkg_context,ca_pkg_fixture_ids,ca_pkg_request_ids to authenticated,anon;
grant insert on ca_pkg_results to authenticated,anon;
do $test$ begin
 execute format('grant usage on schema %I to authenticated,anon',(select nspname from pg_namespace where oid=pg_my_temp_schema()));
 if exists(select 1 from pg_temp.ca_pkg_context where admin_id is null or owner_id is null) then
  raise exception 'SETUP: existing admin and non-admin identities are required';
 end if;
end;$test$;
create function pg_temp.ca_pkg_check(n text,ok boolean) returns text
language plpgsql security invoker set search_path='' as $test$
begin
 if ok is distinct from true then raise exception 'FAILED: %',n;end if;
 insert into pg_temp.ca_pkg_results values(n);return n;
end;$test$;
grant execute on function pg_temp.ca_pkg_check(text,boolean) to authenticated,anon;

insert into public.elanlar(id,satici_id,marka,model,il,qiymet,veziyyet,yaradildi,
 ca_data,paket_adi,paket_baslayir,paket_bitir,sekiller)
select f.id,c.owner_id,c.marker,
 case when f.scenario in ('vip_pending','same_name_pending') then 'Same vehicle' else f.scenario end,
 2020,1200,
 case when f.scenario in ('legacy_missing','canonical_vip','vip_confirmed_edit') then 'aktiv' else 'gozlemede' end,
 now()-f.n*interval '1 second',
 case when f.scenario='legacy_missing' then to_jsonb('{"requestedPackage":"Önə çıxarılan — 15 AZN / 15 gün"}'::text)
  when f.scenario='forged_pack' then '{"pack":"VIP","requestedPackage":""}'::jsonb
  else '{"pack":"Pulsuz","requestedPackage":""}'::jsonb end,
 case when f.scenario='standard_confirmed' then 'Standart'
  when f.scenario in ('vip_confirmed_edit','canonical_vip') then 'VIP' else 'Pulsuz' end,
 case when f.scenario in ('vip_confirmed_edit','canonical_vip') then c.expected_start end,
 case when f.scenario in ('vip_confirmed_edit','canonical_vip') then c.expected_end end,
 array['https://fixture.invalid/package-photo.jpg']
from ca_pkg_fixture_ids f cross join ca_pkg_context c;
-- Simulate a historical missing request without disabling triggers or changing
-- real records. Only the status changes, so UPDATE OF ca_data does not fire.
update public.elanlar set veziyyet='gozlemede'
 where id=(select id from ca_pkg_fixture_ids where scenario='legacy_missing');
insert into public.paket_sorgulari(id,elan_id,satici_id,paket_adi,odenis_veziyyeti,yaradilib,tesdiqlenib)
select r.id,f.id,c.owner_id,r.package,r.status,r.created,
 case when r.status='tesdiqlendi' then r.created end
from ca_pkg_request_ids r join ca_pkg_fixture_ids f on f.scenario=r.scenario
cross join ca_pkg_context c;

-- Ordinary owner editing removes the old purchase intent, preserving its
-- canonical VIP and recorded dates. No approval/payment operation is called.
set local role authenticated;
do $test$ declare c record;begin
 select * into c from pg_temp.ca_pkg_context;
 perform set_config('request.jwt.claim.sub',c.owner_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',c.owner_id,'role','authenticated')::text,true);
 update public.elanlar set veziyyet='gozlemede',ca_data='{"pack":"Pulsuz","requestedPackage":""}'::jsonb
  where id=(select id from pg_temp.ca_pkg_fixture_ids where scenario='vip_confirmed_edit');
 perform pg_temp.ca_pkg_check('ordinary_edit_keeps_canonical_vip_dates',exists(
  select 1 from public.elanlar e where e.id=(select id from pg_temp.ca_pkg_fixture_ids where scenario='vip_confirmed_edit')
   and e.paket_adi='VIP' and e.paket_baslayir=c.expected_start and e.paket_bitir=c.expected_end));
end;$test$;
reset role;
-- A second snapshot proves that metadata reads themselves change no fixture.
create temporary table ca_pkg_fixture_before as
select (select md5(jsonb_agg(to_jsonb(e) order by e.id)::text) from public.elanlar e) listing_hash,
 (select md5(jsonb_agg(to_jsonb(p) order by p.id)::text) from public.paket_sorgulari p) payment_hash;

set local role authenticated;
do $test$
declare c record;d jsonb;item jsonb;s record;expected_request uuid;v_payment jsonb;
begin
 select * into c from pg_temp.ca_pkg_context;
 perform set_config('request.jwt.claim.sub',c.admin_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',c.admin_id,'role','authenticated')::text,true);
 d:=public.ca_admin_browse_listings('all',c.marker,1,48);
 for s in select * from (values
  ('free','Pulsuz','free','Pulsuz'),
  ('vip_pending','VIP','pending','Pulsuz'),
  ('premium_pending','Premium','pending','Pulsuz'),
  ('standard_confirmed','Standart','confirmed','Standart'),
  ('vip_confirmed_edit','VIP','confirmed','VIP'),
  ('premium_rejected','Premium','rejected','Pulsuz'),
  ('legacy_missing','VIP','legacy_unrequested','Pulsuz'),
  ('canonical_vip','VIP','legacy_unrequested','VIP'),
  ('forged_pack','Pulsuz','free','Pulsuz'),
  ('latest_rejected','Premium','rejected','Pulsuz')
 ) expected(scenario,requested,status,approved) loop
  select j into item from jsonb_array_elements(d->'items') j
   where j->>'id'=(select f.id::text from pg_temp.ca_pkg_fixture_ids f where f.scenario=s.scenario);
  select r.id into expected_request from pg_temp.ca_pkg_request_ids r
   where r.scenario=s.scenario order by r.created desc,r.id desc limit 1;
  perform pg_temp.ca_pkg_check('package_metadata_'||s.scenario,
   item->>'requested_package'=s.requested and item->>'package_status'=s.status
   and item->>'approved_package'=s.approved
   and (item->>'package_request_id') is not distinct from expected_request::text);
 end loop;
 perform pg_temp.ca_pkg_check('admin_package_metadata_has_no_private_note_or_photo_payload',
  not exists(select 1 from jsonb_array_elements(d->'items') j
   where j?'paket_tesdiq_qeydi' or j?'ca_data' or j?'sekiller'
    or (select count(*) from jsonb_object_keys(j))<>13));
 perform pg_temp.ca_pkg_check('metadata_does_not_change_filtered_count_or_page_size',
  (d->>'total')::int=(select count(*) from pg_temp.ca_pkg_fixture_ids)
   and (d->>'page_size')::int=48 and (d->>'total_pages')::int=1);
 select r.id into expected_request from pg_temp.ca_pkg_request_ids r where r.scenario='vip_pending';
 v_payment:=public.ca_admin_browse_payments('all',c.marker,1,24);
 perform pg_temp.ca_pkg_check('linked_old_payment_is_outside_initial_queue_page',
  not exists(select 1 from jsonb_array_elements(v_payment->'items') j where j->>'id'=expected_request::text));
 v_payment:=public.ca_admin_browse_payments('all',expected_request::text,1,24);
 perform pg_temp.ca_pkg_check('full_request_uuid_finds_exact_old_payment_despite_same_vehicle_name',
  (v_payment->>'total')::int=1 and jsonb_array_length(v_payment->'items')=1
   and v_payment->'items'->0->>'id'=expected_request::text
   and v_payment->'items'->0->>'elan_id'=(select id::text from pg_temp.ca_pkg_fixture_ids where scenario='vip_pending'));
 v_payment:=public.ca_admin_browse_payments('all',(select id::text from pg_temp.ca_pkg_fixture_ids where scenario='latest_rejected'),1,24);
 perform pg_temp.ca_pkg_check('listing_uuid_search_preserves_all_related_payment_history',
  (v_payment->>'total')::int=2 and v_payment->'items'->0->>'odenis_veziyyeti'='reddedildi');
end;$test$;

with pages as materialized (
 select g.n,public.ca_admin_browse_listings('all',c.marker,g.n,3) d
 from pg_temp.ca_pkg_context c
 cross join generate_series(1,(select (count(*)+2)/3 from pg_temp.ca_pkg_fixture_ids)::int) g(n)
), ids as(select j->>'id' id from pages cross join lateral jsonb_array_elements(d->'items') j)
select pg_temp.ca_pkg_check('enrichment_keeps_every_listing_once_across_pages',
 (select count(*)=(select count(*) from pg_temp.ca_pkg_fixture_ids)
   and count(*)=count(distinct id) from ids));
with r as(select public.ca_admin_browse_listings('all',marker,1,3) d from pg_temp.ca_pkg_context),
actual as(select array_agg(j->>'id' order by n) ids from r cross join lateral jsonb_array_elements(d->'items') with ordinality a(j,n)),
expected as(select array_agg(id::text order by yaradildi desc,id desc) ids from(
 select e.id,e.yaradildi from public.elanlar e join pg_temp.ca_pkg_fixture_ids f using(id)
 order by e.yaradildi desc,e.id desc limit 3) q)
select pg_temp.ca_pkg_check('enrichment_preserves_existing_newest_then_id_order',actual.ids=expected.ids) from actual,expected;
with r as(select public.ca_admin_browse_listings('gozlemede',marker,1,48) d from pg_temp.ca_pkg_context)
select pg_temp.ca_pkg_check('enrichment_preserves_listing_status_filter',
 (d->>'total')::int=(select count(*) from public.elanlar e join pg_temp.ca_pkg_fixture_ids f using(id) where e.veziyyet='gozlemede')
 and not exists(select 1 from jsonb_array_elements(d->'items') j where j->>'veziyyet'<>'gozlemede')) from r;
reset role;

set local role authenticated;
do $test$ declare c record;blocked boolean:=false;begin
 select * into c from pg_temp.ca_pkg_context;
 perform set_config('request.jwt.claim.sub',c.owner_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',c.owner_id,'role','authenticated')::text,true);
 begin perform public.ca_admin_browse_listings();exception when insufficient_privilege then blocked:=true;end;
 perform pg_temp.ca_pkg_check('non_admin_cannot_read_package_feedback',blocked);
end;$test$;
reset role;
set local role anon;
do $test$ declare blocked boolean:=false;begin
 perform set_config('request.jwt.claim.sub','',true);perform set_config('request.jwt.claims','{"role":"anon"}',true);
 begin perform public.ca_admin_browse_listings();exception when insufficient_privilege then blocked:=true;end;
 perform pg_temp.ca_pkg_check('anon_cannot_read_package_feedback',blocked);
end;$test$;
with r as(select public.ca_browse_listings(jsonb_build_object('make',marker),1,48) d from pg_temp.ca_pkg_context)
select pg_temp.ca_pkg_check('public_browse_does_not_expose_admin_package_feedback',
 not exists(select 1 from jsonb_array_elements(d->'items') j
  where j?'requested_package' or j?'package_status' or j?'package_request_id' or j?'approved_package')) from r;
reset role;

select pg_temp.ca_pkg_check('metadata_functions_remain_security_invoker',not exists(
 select 1 from pg_proc where oid in(
 'public.ca_admin_browse_listings(text,text,integer,integer)'::regprocedure,
 'public.ca_admin_browse_payments(text,text,integer,integer)'::regprocedure) and prosecdef));
select pg_temp.ca_pkg_check('metadata_reads_change_no_listing_or_payment_record',
 b.listing_hash=(select md5(jsonb_agg(to_jsonb(e) order by e.id)::text) from public.elanlar e)
 and b.payment_hash=(select md5(jsonb_agg(to_jsonb(p) order by p.id)::text) from public.paket_sorgulari p)) from ca_pkg_fixture_before b;
select pg_temp.ca_pkg_check('existing_listing_photos_packages_remain_unchanged',c.listing_hash=(
 select md5(jsonb_agg(to_jsonb(e) order by e.id)::text) from public.elanlar e
 where not exists(select 1 from ca_pkg_fixture_ids f where f.id=e.id))) from ca_pkg_context c;
select pg_temp.ca_pkg_check('existing_payment_records_remain_unchanged',c.payment_hash=(
 select md5(jsonb_agg(to_jsonb(p) order by p.id)::text) from public.paket_sorgulari p
 where not exists(select 1 from ca_pkg_fixture_ids f where f.id=p.elan_id))) from ca_pkg_context c;
select count(*) passed_count,array_agg(name order by name) passed_tests from ca_pkg_results;
rollback;
