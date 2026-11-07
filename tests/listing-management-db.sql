-- Atomic rollback regressions. Requires the proposed management+browse schema.
-- To prototype the migration, place its DDL immediately after BEGIN below.
-- No auth users are created, no existing user/listing/payment row is changed,
-- and no IDs or credentials are returned. NEVER replace ROLLBACK with COMMIT.
begin;

create temporary table ca_test_results (name text primary key);
create temporary table ca_test_context (
  owner_id uuid, admin_id uuid, marker text, paid_id uuid, other_id uuid,
  draft_id uuid, paid_request_id uuid, paid_starts timestamptz,
  paid_ends timestamptz
);
do $test$
begin
  execute format('grant usage on schema %I to anon, authenticated',
    (select nspname from pg_namespace where oid=pg_my_temp_schema()));
end;
$test$;
-- Snapshots remain private temporary data and are never selected for output.
create temporary table ca_test_existing_listings as
  select e.id, to_jsonb(e) as row_data from public.elanlar e;
create temporary table ca_test_existing_requests as
  select p.id, to_jsonb(p) as row_data from public.paket_sorgulari p;
grant select, insert on ca_test_results to anon, authenticated;
grant select, update on ca_test_context to anon, authenticated;

create function pg_temp.ca_check(p_name text, p_ok boolean)
returns text language plpgsql security invoker set search_path = ''
as $test$
begin
  if p_ok is distinct from true then
    raise exception 'FAILED: %',p_name;
  end if;
  insert into pg_temp.ca_test_results(name) values (p_name);
  return p_name;
end;
$test$;
grant execute on function pg_temp.ca_check(text,boolean) to anon, authenticated;

do $test$
declare v_owner uuid; v_admin uuid;
begin
  select u.id into v_owner from auth.users u
    where not exists (select 1 from public.adminler a where a.istifadeci_id=u.id)
    order by u.created_at,u.id limit 1;
  select a.istifadeci_id into v_admin from public.adminler a
    join auth.users u on u.id=a.istifadeci_id
    order by u.created_at,u.id limit 1;
  if v_owner is null or v_admin is null then
    raise exception 'SETUP: existing non-admin and admin accounts are required';
  end if;
  insert into pg_temp.ca_test_context(owner_id,admin_id,marker,other_id)
    values(v_owner,v_admin,'CA_TEST_'||replace(gen_random_uuid()::text,'-',''),gen_random_uuid());
  insert into public.elanlar(id,satici_id,marka,model,il,qiymet,veziyyet,ca_data)
    select other_id,admin_id,marker||'_OTHER','Other owner',2020,100,'gozlemede','{}'::jsonb
    from pg_temp.ca_test_context;
  perform pg_temp.ca_check('approval_timestamp_has_no_fabricated_default',not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='elanlar'
      and column_name='tesdiq_tarixi' and column_default is not null
  ));
end;
$test$;

set local role authenticated;
do $test$
declare v_uid uuid;
begin
  select owner_id into v_uid from pg_temp.ca_test_context;
  perform set_config('request.jwt.claims',jsonb_build_object('sub',v_uid,'role','authenticated')::text,true);
  perform set_config('request.jwt.claim.sub',v_uid::text,true);
end;
$test$;

do $test$
declare
  c record; v_id uuid; v_returned uuid; v_count integer; v_blocked boolean;
  v_column text; v_expr text; v_first uuid; v_second uuid;
begin
  select * into c from pg_temp.ca_test_context;
  perform pg_temp.ca_check('owner_identity_is_non_admin',not public.cenub_admin_yoxla());

  insert into public.elanlar(satici_id,marka,model,il,qiymet,yurus,veziyyet,sekiller,ca_data)
    values(c.owner_id,c.marker||'_OWNER','Editable',2020,100,0,'gozlemede',
      array['https://fixture.invalid/front.jpg','https://fixture.invalid/rear.jpg'],
      jsonb_build_object('requestedPackage',''))
    returning id into v_id;
  update pg_temp.ca_test_context set draft_id=v_id;
  perform pg_temp.ca_check('owner_insert_is_pending_with_unknown_approval',exists (
    select 1 from public.elanlar where id=v_id and veziyyet='gozlemede'
      and tesdiq_tarixi is null and paket_adi='Pulsuz'
  ));

  update public.elanlar set qiymet=125,tesvir='edited',veziyyet='gozlemede'
    where id=v_id returning id into v_returned;
  perform pg_temp.ca_check('owner_edit_returns_one_real_affected_row',v_returned=v_id);

  update public.elanlar set tesvir='forbidden other edit',veziyyet='gozlemede'
    where id=c.other_id;
  get diagnostics v_count=row_count;
  perform pg_temp.ca_check('owner_cannot_edit_another_listing',v_count=0);

  v_blocked:=false;
  begin
    update public.elanlar set satici_id=c.admin_id,veziyyet='gozlemede' where id=v_id;
  exception when insufficient_privilege then v_blocked:=true;
  end;
  perform pg_temp.ca_check('owner_cannot_reassign_listing',v_blocked);

  v_blocked:=false;
  begin
    update public.elanlar set veziyyet='aktiv' where id=v_id;
  exception when insufficient_privilege then v_blocked:=true;
  end;
  perform pg_temp.ca_check('owner_cannot_self_approve',v_blocked);

  foreach v_column in array array[
    'paket_adi','paket_baslayir','paket_bitir','paket_tesdiq_qeydi',
    'tesdiq_tarixi','yaradildi','id'
  ] loop
    v_expr:=case v_column
      when 'paket_adi' then quote_literal('VIP')
      when 'paket_tesdiq_qeydi' then quote_literal('spoof')
      when 'id' then 'gen_random_uuid()' else 'now()' end;
    v_blocked:=false;
    begin
      execute format('insert into public.elanlar(marka,model,il,qiymet,satici_id,veziyyet,%I) values($1,''Spoof'',2020,10,$2,''gozlemede'',%s)',v_column,v_expr)
        using c.marker||'_SPOOF',c.owner_id;
    exception when insufficient_privilege then v_blocked:=true;
    end;
    perform pg_temp.ca_check('owner_insert_protected_'||v_column||'_denied',v_blocked);
    v_blocked:=false;
    begin
      execute format('update public.elanlar set %I=%s where id=$1',v_column,v_expr) using v_id;
    exception when insufficient_privilege then v_blocked:=true;
    end;
    perform pg_temp.ca_check('owner_update_protected_'||v_column||'_denied',v_blocked);
  end loop;

  insert into public.elanlar(satici_id,marka,model,il,qiymet,yurus,veziyyet,sekiller,ca_data)
    values(c.owner_id,c.marker||'_PAID','Paid lifecycle',2020,150,0,'gozlemede',
      array['https://fixture.invalid/paid-front.jpg','https://fixture.invalid/paid-rear.jpg'],
      jsonb_build_object('requestedPackage','Önə çıxarılan — 15 AZN / 15 gün'))
    returning id into v_id;
  v_first:=public.ca_paket_sorgusu_yarat(v_id,'VIP');
  v_second:=public.ca_paket_sorgusu_yarat(v_id,'VIP');
  update pg_temp.ca_test_context set paid_id=v_id,paid_request_id=v_first;
  perform pg_temp.ca_check('matching_package_retries_return_same_request',v_first is not null and v_first=v_second);

  v_blocked:=false;
  begin perform public.ca_paket_sorgusu_yarat(v_id,'Premium');
  exception when invalid_parameter_value then v_blocked:=true;
  end;
  perform pg_temp.ca_check('different_pending_package_is_rejected',v_blocked);

  v_blocked:=false;
  begin perform public.ca_paket_sorgusu_yarat(c.other_id,'VIP');
  exception when insufficient_privilege then v_blocked:=true;
  end;
  perform pg_temp.ca_check('package_rpc_denies_other_owner',v_blocked);

  v_blocked:=false;
  begin perform public.ca_admin_status(v_id,'aktiv');
  exception when insufficient_privilege then v_blocked:=true;
  end;
  perform pg_temp.ca_check('non_admin_cannot_call_approval_rpc',v_blocked);
end;
$test$;
reset role;

do $test$
begin
  perform pg_temp.ca_check('paid_trigger_and_retries_create_exactly_one_pending_request',(
    select count(*)=1 and bool_and(p.odenis_veziyyeti='gozlemede')
    from public.paket_sorgulari p join pg_temp.ca_test_context c on p.elan_id=c.paid_id
  ));
end;
$test$;

set local role anon;
do $test$
declare c record; v_blocked boolean:=false;
begin
  perform set_config('request.jwt.claims','{"role":"anon"}',true);
  perform set_config('request.jwt.claim.sub','',true);
  select * into c from pg_temp.ca_test_context;
  begin perform public.ca_paket_sorgusu_yarat(c.paid_id,'VIP');
  exception when insufficient_privilege then v_blocked:=true;
  end;
  perform pg_temp.ca_check('anonymous_package_rpc_is_denied',v_blocked);
end;
$test$;
reset role;

set local role authenticated;
do $test$
declare c record; v_before timestamptz:=statement_timestamp(); r record;
begin
  select * into c from pg_temp.ca_test_context;
  perform set_config('request.jwt.claims',jsonb_build_object('sub',c.admin_id,'role','authenticated')::text,true);
  perform set_config('request.jwt.claim.sub',c.admin_id::text,true);
  perform pg_temp.ca_check('admin_identity_is_authorized',public.cenub_admin_yoxla());
  perform public.ca_admin_paket_tesdiq(c.paid_request_id);
  perform public.ca_admin_status(c.paid_id,'aktiv');
  select id,veziyyet,paket_adi,paket_baslayir,paket_bitir,tesdiq_tarixi into r
    from public.elanlar where id=c.paid_id;
  perform pg_temp.ca_check('admin_approval_records_real_timestamp',
    r.veziyyet='aktiv' and r.tesdiq_tarixi>=v_before and r.tesdiq_tarixi<=clock_timestamp());
  perform pg_temp.ca_check('new_paid_approval_starts_fifteen_day_vip_term',
    r.paket_adi='VIP' and r.paket_baslayir is not null
    and r.paket_bitir=r.paket_baslayir+make_interval(days=>15));
  update pg_temp.ca_test_context set paid_starts=r.paket_baslayir,paid_ends=r.paket_bitir;
end;
$test$;
reset role;

set local role authenticated;
do $test$
declare c record; v_returned uuid;
begin
  select * into c from pg_temp.ca_test_context;
  perform set_config('request.jwt.claims',jsonb_build_object('sub',c.owner_id,'role','authenticated')::text,true);
  perform set_config('request.jwt.claim.sub',c.owner_id::text,true);
  update public.elanlar set qiymet=151,veziyyet='gozlemede',
    ca_data=jsonb_build_object('requestedPackage','')
    where id=c.paid_id returning id into v_returned;
  perform pg_temp.ca_check('owner_can_edit_active_listing_back_to_pending',v_returned=c.paid_id);
  perform pg_temp.ca_check('owner_edit_keeps_recorded_paid_dates',exists (
    select 1 from public.elanlar where id=c.paid_id
      and paket_baslayir=c.paid_starts and paket_bitir=c.paid_ends
  ));
end;
$test$;
reset role;
do $test$
begin
  perform pg_temp.ca_check('ordinary_paid_edit_creates_no_new_purchase',(
    select count(*)=1 and bool_and(p.odenis_veziyyeti='tesdiqlendi')
    from public.paket_sorgulari p join pg_temp.ca_test_context c on p.elan_id=c.paid_id
  ));
end;
$test$;

set local role authenticated;
do $test$
declare c record;
begin
  select * into c from pg_temp.ca_test_context;
  perform set_config('request.jwt.claims',jsonb_build_object('sub',c.admin_id,'role','authenticated')::text,true);
  perform set_config('request.jwt.claim.sub',c.admin_id::text,true);
  perform public.ca_admin_status(c.paid_id,'aktiv');
  perform pg_temp.ca_check('paid_reapproval_does_not_extend_vip',exists (
    select 1 from public.elanlar where id=c.paid_id and veziyyet='aktiv'
      and paket_baslayir=c.paid_starts and paket_bitir=c.paid_ends
  ));
end;
$test$;
reset role;

set local role authenticated;
do $test$
declare c record; v_returned uuid; v_count integer;
begin
  select * into c from pg_temp.ca_test_context;
  perform set_config('request.jwt.claims',jsonb_build_object('sub',c.owner_id,'role','authenticated')::text,true);
  perform set_config('request.jwt.claim.sub',c.owner_id::text,true);
  update public.elanlar set veziyyet='silindi' where id=c.paid_id returning id into v_returned;
  perform pg_temp.ca_check('owner_soft_archive_returns_real_affected_row',v_returned=c.paid_id);
  perform pg_temp.ca_check('soft_archive_preserves_photo_urls_and_paid_dates',exists (
    select 1 from public.elanlar where id=c.paid_id and veziyyet='silindi'
      and sekiller=array['https://fixture.invalid/paid-front.jpg','https://fixture.invalid/paid-rear.jpg']
      and paket_adi='VIP' and paket_baslayir=c.paid_starts and paket_bitir=c.paid_ends
  ));
  update public.elanlar set veziyyet='gozlemede' where id=c.paid_id;
  get diagnostics v_count=row_count;
  perform pg_temp.ca_check('owner_cannot_reactivate_archive',v_count=0);
  update public.elanlar set tesvir='forbidden archived edit' where id=c.paid_id;
  get diagnostics v_count=row_count;
  perform pg_temp.ca_check('owner_cannot_edit_archive',v_count=0);
  delete from public.elanlar where id=c.paid_id;
  get diagnostics v_count=row_count;
  perform pg_temp.ca_check('owner_cannot_hard_delete_payment_evidence',v_count=0);
end;
$test$;
reset role;

do $test$
begin
  perform pg_temp.ca_check('archive_retains_package_foreign_key_and_payment_record',(
    select count(*)=1 and bool_and(p.odenis_veziyyeti='tesdiqlendi')
    from public.paket_sorgulari p join pg_temp.ca_test_context c on p.elan_id=c.paid_id
  ));
end;
$test$;

set local role authenticated;
do $test$
declare c record; v_blocked boolean:=false;
begin
  select * into c from pg_temp.ca_test_context;
  perform set_config('request.jwt.claims',jsonb_build_object('sub',c.admin_id,'role','authenticated')::text,true);
  perform set_config('request.jwt.claim.sub',c.admin_id::text,true);
  begin perform public.ca_admin_status(c.paid_id,'aktiv');
  exception when invalid_parameter_value then v_blocked:=true;
  end;
  perform pg_temp.ca_check('admin_rpc_cannot_accidentally_restore_archive',v_blocked);
end;
$test$;
reset role;

-- TEST FRAGMENT ONLY. Root must place this inside its outer ROLLBACK test.
-- No statement here is intended to be committed or run by itself.
-- Requires ca_test_context, ca_test_results and pg_temp.ca_check from root.

reset role;
do $test$ begin
  perform set_config('request.jwt.claims', '{}', true);
  perform set_config('request.jwt.claim.sub', '', true);
end; $test$;

create temporary table ca_browse_fixture_context on commit drop as
select c.owner_id, c.marker,
  c.marker || '_BROWSE' as bulk_make,
  c.marker || '-browse-sort' as sort_make,
  c.marker || '-browse-alias' as alias_make,
  c.marker || '-browse-number' as number_make,
  (select count(*) from public.elanlar e
    where e.veziyyet = 'aktiv'
      and (e.tesdiq_tarixi at time zone 'Asia/Baku')::date =
          (now() at time zone 'Asia/Baku')::date) as baseline_today,
  greatest(now(), coalesce((select max(e.yaradildi) from public.elanlar e), now()))
    + interval '1 day' as fixture_created_at
from ca_test_context c;
grant select on ca_browse_fixture_context to anon, authenticated;

-- A full 600-row make proves pagination is not silently capped at 500 rows.
-- Price order and creation order intentionally disagree.
insert into public.elanlar (
  id, satici_id, marka, model, il, qiymet, yurus, seher, veziyyet,
  yaradildi, ca_data, paket_adi, paket_tesdiq_qeydi
)
select gen_random_uuid(), c.owner_id, c.bulk_make,
  'Bulk-' || lpad(g.n::text, 3, '0'), 2020, 10000 + g.n,
  case when g.n = 1 then 0 else g.n * 100 end, 'Bakı', 'aktiv',
  c.fixture_created_at + g.n * interval '1 second',
  '{}'::jsonb, 'Pulsuz', 'ROLLBACK fixture private approval note'
from ca_browse_fixture_context c cross join generate_series(1, 600) g(n);

-- These must not increase public totals or appear in any public page.
insert into public.elanlar (
  id, satici_id, marka, model, il, qiymet, yurus, veziyyet, ca_data
)
select gen_random_uuid(), c.owner_id, c.bulk_make,
  'Hidden-' || v.status, 2020, 1, 0, v.status, '{}'::jsonb
from ca_browse_fixture_context c
cross join (values ('gozlemede'), ('silindi')) v(status);

-- Distinct price values verify aggregate order, price direction and paid rank.
-- Fresh fixture creation timestamps also place both VIP rows in vip_items.
insert into public.elanlar (
  id, satici_id, marka, model, il, qiymet, yurus, seher, veziyyet,
  yaradildi, ca_data, paket_adi, paket_baslayir, paket_bitir
)
select gen_random_uuid(), c.owner_id, c.sort_make, v.model, 2022, v.price,
  1000, 'Bakı', 'aktiv', c.fixture_created_at + interval '1 hour'
    + v.n * interval '1 second', '{}'::jsonb, v.package,
  case when v.package <> 'Pulsuz' then now() end,
  case when v.package <> 'Pulsuz' then now() + interval '15 days' end
from ca_browse_fixture_context c
cross join (values
  (1, 'VIP-cheap',       100::numeric, 'VIP'),
  (2, 'VIP-expensive', 99999::numeric, 'VIP'),
  (3, 'Premium',       50000::numeric, 'Premium'),
  (4, 'Standard',          5::numeric, 'Standart'),
  (5, 'Free-cheap',        1::numeric, 'Pulsuz'),
  (6, 'Free-expensive', 88888::numeric, 'Pulsuz')
) v(n, model, price, package);

-- Blank higher-priority aliases must not hide populated lower-priority ones.
-- ca_data is deliberately a JSON string containing an object, as in legacy rows.
insert into public.elanlar (
  id, satici_id, marka, model, il, qiymet, yurus, seher, veziyyet,
  neqliyyat_novu, ban_novu, reng, bazar_ucun, oturacaq_sayi,
  muherrik_hecmi, at_gucu, techizat, ca_data
)
select gen_random_uuid(), c.owner_id, U&'\00A0\202F', '', 2021, 23456, null, '', 'aktiv',
  '', '', '', '', null, null, null, null,
  to_jsonb(jsonb_build_object(
    'make', U&'\00A0\202F', 'marka', ' ', 'brand', c.alias_make,
    'model', ' ', 'modelName', 'Legacy aliases',
    'city', ' ', 'seher', 'Lənkəran',
    'vehicleType', ' ', 'vehicle', ' ', 'neqliyyat_novu', 'Avtomobil',
    'body', ' ', 'bodyType', ' ', 'ban_novu', 'Sedan',
    'color', ' ', 'reng', 'Mavi',
    'market', ' ', 'bazar_ucun', 'Avropa',
    'seats', ' ', 'oturacaq_sayi', 5,
    'mileage', ' ', 'km', '94 000 km',
    'engine', ' ', 'muherrik_hecmi', '2,5 L',
    'horsepower', ' ', 'hp', ' ', 'at_gucu', '1,000 hp',
    'equipment', null, 'techizat', jsonb_build_array('ABS', 'ESP'),
    'vehicleState', 'İşlənmiş'
  )::text)
from ca_browse_fixture_context c;

-- JSON numbers bypass string thousands heuristics; JSON strings retain them.
insert into public.elanlar (
  id, satici_id, marka, model, il, qiymet, yurus, veziyyet,
  muherrik_hecmi, at_gucu, ca_data
)
select gen_random_uuid(), c.owner_id, c.number_make, v.model,
  2023, 30000, null, 'aktiv', null, null, v.data
from ca_browse_fixture_context c
cross join (values
  ('JSON typed decimals', jsonb_build_object(
    'mileage', 1.234::numeric, 'engine', 1.234::numeric,
    'horsepower', 1.234::numeric)),
  ('JSON string thousands', jsonb_build_object(
    'mileage', '1.234', 'engine', '1.234', 'horsepower', '1.234'))
) v(model, data);

insert into public.elanlar (
  id,satici_id,marka,model,il,qiymet,yurus,veziyyet,muherrik_hecmi,ca_data
)
select gen_random_uuid(),c.owner_id,c.number_make,'SQL typed decimals',
  2023,30000,0,'aktiv',1.234,'{}'::jsonb
from ca_browse_fixture_context c;

set local role anon;
do $test$ begin
  perform set_config('request.jwt.claims', '{"role":"anon"}', true);
  perform set_config('request.jwt.claim.sub', '', true);
end; $test$;

-- Built-in helper contracts: normal units, punctuation, Unicode spaces and zero.
select pg_temp.ca_check('browse_number_parser_formats',
  public.ca_listing_number('94 000 km'::text) = 94000
  and public.ca_listing_number('1,000 hp'::text) = 1000
  and public.ca_listing_number('94.5 km'::text) = 94.5
  and public.ca_listing_number('1.234,56'::text) = 1234.56
  and public.ca_listing_number('1,234.56'::text) = 1234.56
  and public.ca_listing_number(U&'94\00A0000 km'::text) = 94000
  and public.ca_listing_number(U&'94\202F000 km'::text) = 94000
  and public.ca_listing_number('+0'::text) = 0
  and public.ca_listing_number('-5'::text) is null
  and public.ca_listing_number('1,2,3'::text) is null
  and public.ca_listing_number('unknown'::text) is null);

select pg_temp.ca_check('browse_json_number_type_and_blank_aliases',
  public.ca_listing_number('null'::jsonb, '" "'::jsonb, '1.234'::jsonb) = 1.234
  and public.ca_listing_number('"1.234"'::jsonb, 'null'::jsonb) = 1234
  and public.ca_listing_value(null::text, U&'\00A0\202F', ' Toyota ') = 'Toyota');

with result as (
  select public.ca_browse_listings(jsonb_build_object('make', c.bulk_make), 1, 24) as r
  from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_600_total_and_25_pages',
  (r->>'total')::integer = 600
  and (r->>'total_pages')::integer = 25
  and (r->>'page')::integer = 1
  and (r->>'page_size')::integer = 24
  and jsonb_array_length(r->'items') = 24)
from result;

with pages as materialized (
  select g.n, public.ca_browse_listings(
    jsonb_build_object('make', c.bulk_make), g.n, 24) as r
  from ca_browse_fixture_context c cross join generate_series(1,25) g(n)
), ids as (
  select item->>'id' as id from pages
  cross join lateral jsonb_array_elements(r->'items') item
)
select pg_temp.ca_check('browse_25_pages_contain_600_unique_ids',
  (select bool_and(jsonb_array_length(r->'items') = 24
    and (r->>'page')::integer = n
    and (r->>'total')::integer = 600
    and (r->>'total_pages')::integer = 25) from pages)
  and (select count(*) = 600 and count(distinct id) = 600 from ids));

with result as (
  select public.ca_browse_listings(jsonb_build_object(
    'make', c.bulk_make, 'model', 'Bulk-001', 'kmMin', 0, 'kmMax', 0), 1, 24) as r
  from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_zero_mileage_matches_zero_bounds',
  (r->>'total')::integer = 1 and (r->'items'->0->>'yurus')::integer = 0)
from result;

with result as (
  select v.sort, public.ca_browse_listings(jsonb_build_object(
    'make', c.sort_make, 'sort', v.sort), 1, 24) as r, v.expected
  from ca_browse_fixture_context c cross join (values
    ('priceAsc', array['VIP-cheap','VIP-expensive','Premium','Standard','Free-cheap','Free-expensive']),
    ('priceDesc', array['VIP-expensive','VIP-cheap','Premium','Standard','Free-expensive','Free-cheap'])
  ) v(sort, expected)
), ordered as (
  select sort, expected,
    array(select item->>'model' from jsonb_array_elements(r->'items')
      with ordinality a(item,n) order by n) as actual
  from result
)
select pg_temp.ca_check('browse_vip_priority_and_' || sort, actual = expected)
from ordered;

with result as (
  select public.ca_browse_listings(jsonb_build_object(
    'make', c.alias_make, 'model', 'Legacy aliases', 'city', 'Lənkəran',
    'vehicle', 'Avtomobil', 'state', 'İşlənmiş', 'body', 'Sedan',
    'color', 'Mavi', 'market', 'Avropa', 'seats', '5',
    'kmMin', 94000, 'kmMax', 94000, 'engineMin', 2.5, 'engineMax', 2.5,
    'hpMin', 1000, 'hpMax', 1000, 'equipment', jsonb_build_array('ABS','ESP')
  ), 1, 24) as r
  from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_all_legacy_aliases_units_and_json_string',
  (r->>'total')::integer = 1 and jsonb_array_length(r->'items') = 1)
from result;

with result as (
  select public.ca_browse_listings(jsonb_build_object(
    'make',upper(c.alias_make),'city','LƏNKƏRAN','color','MAVİ'),1,24) as r
  from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_azerbaijani_uppercase_and_unicode_blank_alias',
  (r->>'total')::integer=1)
from result;

with result as (
  select public.ca_browse_listings(jsonb_build_object(
    'make',c.number_make,'model','SQL typed decimals',
    'engineMin',1.234,'engineMax',1.234),1,24) as r
  from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_sql_typed_decimal_filter_parity',
  (r->>'total')::integer=1
  and (r->'items'->0->>'muherrik_hecmi')::numeric=1.234)
from result;

with result as (
  select public.ca_browse_listings(jsonb_build_object(
    'make', c.number_make, 'kmMin', 1.2, 'kmMax', 1.3,
    'engineMin', 1.2, 'engineMax', 1.3, 'hpMin', 1.2, 'hpMax', 1.3), 1, 24) as r
  from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_json_typed_decimal_filter_parity',
  (r->>'total')::integer = 1
  and r->'items'->0->>'model' = 'JSON typed decimals')
from result;

with result as (
  select public.ca_browse_listings(jsonb_build_object(
    'make', c.number_make, 'kmMin', 1234, 'kmMax', 1234,
    'engineMin', 1234, 'engineMax', 1234, 'hpMin', 1234, 'hpMax', 1234), 1, 24) as r
  from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_json_string_thousands_filter_parity',
  (r->>'total')::integer = 1
  and r->'items'->0->>'model' = 'JSON string thousands')
from result;

with result as (
  select public.ca_browse_listings(jsonb_build_object('make', c.sort_make), 1, 24) as r
  from ca_browse_fixture_context c
), public_items as (
  select item from result cross join lateral jsonb_array_elements(r->'items') item
  union all
  select item from result cross join lateral jsonb_array_elements(r->'vip_items') item
)
select pg_temp.ca_check('browse_items_and_vip_exclude_private_and_internal_keys',
  (select count(*) >= 8 from public_items)
  and not exists (select 1 from public_items
    where item ? 'paket_tesdiq_qeydi'
      or exists (select 1 from jsonb_object_keys(item) k where left(k,1) = '_'))
  and (select bool_and(item ?& array['id','marka','model','il','qiymet','yurus','tesdiq_tarixi'])
    from public_items));

with result as (
  select public.ca_browse_listings(jsonb_build_object('make', c.sort_make), 1, 24) as r,
    c.sort_make from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_promoted_vip_rows_are_returned',
  (select count(*) = 2 from jsonb_array_elements(r->'vip_items') item
    where item->>'marka' = sort_make
      and item->>'model' in ('VIP-cheap','VIP-expensive')))
from result;

with result as (
  select public.ca_browse_listings(jsonb_build_object('make', c.bulk_make), 1, 24) as r,
    c.baseline_today from ca_browse_fixture_context c
)
select pg_temp.ca_check('browse_today_approved_uses_all_active_rows',
  (r->>'today_approved')::bigint = baseline_today + 610)
from result;

select pg_temp.ca_check('browse_rpc_is_security_invoker',
  (select not prosecdef from pg_proc
    where oid = 'public.ca_browse_listings(jsonb,integer,integer)'::regprocedure));

reset role;
do $test$ begin
  perform set_config('request.jwt.claims', '{}', true);
  perform set_config('request.jwt.claim.sub', '', true);
end; $test$;


do $test$
begin
  perform pg_temp.ca_check('all_existing_listing_records_remain_unchanged',not exists (
    select 1 from pg_temp.ca_test_existing_listings b
    left join public.elanlar e on e.id=b.id
    where e.id is null or to_jsonb(e) is distinct from b.row_data
  ));
  perform pg_temp.ca_check('all_existing_payment_records_remain_unchanged',not exists (
    select 1 from pg_temp.ca_test_existing_requests b
    left join public.paket_sorgulari p on p.id=b.id
    where p.id is null or to_jsonb(p) is distinct from b.row_data
  ));
end;
$test$;

select count(*) as passed_count,array_agg(name order by name) as passed_tests
  from pg_temp.ca_test_results;
rollback;
