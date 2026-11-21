-- Focused authorization boundaries after the browser-privilege hardening.
-- PostgreSQL 17+. Synthetic storage metadata only; no stored bytes, Auth API,
-- email, provider request, existing-row mutation or destructive TRUNCATE occurs.
-- Every DML predicate names a generated fixture ID/path. Never replace ROLLBACK.
-- Direct SQL deletion is guarded by Storage. Only this rolled-back fixture
-- emulates Storage API context with transaction-local allow_delete_query=true
-- so DELETE cases exercise RLS, then restores the prior/default-deny setting.
begin;
set transaction isolation level repeatable read;
set local statement_timeout = '30s';

create temporary table ca_boundary_results(name text primary key);
create temporary table ca_boundary_context as
select gen_random_uuid() owner_a,gen_random_uuid() owner_b,
 gen_random_uuid() other_legacy_id,gen_random_uuid() own_checked_id,
 gen_random_uuid() other_checked_id,gen_random_uuid() own_legacy_id,
 gen_random_uuid() denied_insert_id,
 current_setting('storage.allow_delete_query',true) delete_guard_before,
 (select md5(coalesce(jsonb_agg(to_jsonb(o) order by o.id)::text,'[]'))
  from storage.objects o) storage_before;
do $$begin
 if current_setting('server_version_num')::integer < 170000 then
  raise exception 'SETUP: PostgreSQL 17+ required for MAINTAIN privilege checks';
 end if;
 execute format('grant usage on schema %I to anon,authenticated',
  (select nspname from pg_namespace where oid=pg_my_temp_schema()));
end$$;
grant select on ca_boundary_context to anon,authenticated;
grant select,insert on ca_boundary_results to anon,authenticated;

create function pg_temp.ca_boundary_check(p_name text,p_ok boolean)
returns void language plpgsql security invoker set search_path='' as $$
begin
 if p_ok is distinct from true then raise exception 'FAILED: %',p_name;end if;
 insert into pg_temp.ca_boundary_results values(p_name);
end$$;

create function pg_temp.ca_boundary_denied(p_name text,p_statement text)
returns void language plpgsql security invoker set search_path='' as $$
declare blocked boolean:=false;
begin
 begin execute p_statement;
 exception when sqlstate '42501' then blocked:=true;end;
 perform pg_temp.ca_boundary_check(p_name,blocked);
end$$;

create function pg_temp.ca_boundary_zero(p_name text,p_statement text)
returns void language plpgsql security invoker set search_path='' as $$
declare affected bigint;
begin
 begin execute p_statement;get diagnostics affected=row_count;
 exception when sqlstate '42501' then affected:=0;end;
 perform pg_temp.ca_boundary_check(p_name,affected=0);
end$$;
revoke all on function pg_temp.ca_boundary_check(text,boolean),
 pg_temp.ca_boundary_denied(text,text),pg_temp.ca_boundary_zero(text,text) from public;
grant execute on function pg_temp.ca_boundary_check(text,boolean),
 pg_temp.ca_boundary_denied(text,text),pg_temp.ca_boundary_zero(text,text) to anon,authenticated;

-- These are capability checks only: there is intentionally no TRUNCATE query.
do $$
declare browser_role text;
begin
 foreach browser_role in array array['anon','authenticated'] loop
  perform pg_temp.ca_boundary_check('profile_unneeded_privileges_absent_'||browser_role,
   not has_table_privilege(browser_role,'public.profiller',
    'TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'));
 end loop;
 perform pg_temp.ca_boundary_check('listing_hard_delete_privilege_absent',
  not has_table_privilege('authenticated','public.elanlar','DELETE'));
 perform pg_temp.ca_boundary_check('admin_table_browser_grants_closed',
  not has_table_privilege('anon','public.adminler','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
  and not has_table_privilege('authenticated','public.adminler','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'));
 perform pg_temp.ca_boundary_check('app_table_rls_enabled',
  (select count(*)=3 and bool_and(c.relrowsecurity) from pg_class c
   where c.oid in ('public.elanlar'::regclass,'public.profiller'::regclass,'public.adminler'::regclass)));
 perform pg_temp.ca_boundary_check('private_tables_rls_enabled',
  (select count(*)>0 and bool_and(c.relrowsecurity) from pg_class c
   join pg_namespace n on n.oid=c.relnamespace
   where n.nspname='ca_private' and c.relkind in ('r','p')));
 perform pg_temp.ca_boundary_check('private_browser_table_grants_closed',not exists(
  select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
  cross join unnest(array['anon','authenticated']) r(role_name)
  where n.nspname='ca_private' and c.relkind in ('r','p')
   and has_table_privilege(r.role_name,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')));
 perform pg_temp.ca_boundary_check('storage_objects_rls_enabled',
  (select relrowsecurity from pg_class where oid='storage.objects'::regclass));
end$$;

-- The bucket already exists. These are nonexistent-file metadata records only.
-- owner_id is deliberately omitted, as in the existing photo-review suite.
insert into storage.objects(id,bucket_id,name,metadata)
select other_legacy_id,'elan-sekilleri',owner_b::text||'/original/'||other_legacy_id::text||'.jpg',
 '{"mimetype":"image/jpeg","size":100}'::jsonb from ca_boundary_context
union all
select own_checked_id,'elan-sekilleri',owner_a::text||'/checked/'||own_checked_id::text||'-ca-wm1.jpg',
 '{"mimetype":"image/jpeg","size":100}'::jsonb from ca_boundary_context
union all
select other_checked_id,'elan-sekilleri',owner_b::text||'/checked/'||other_checked_id::text||'-ca-wm1.jpg',
 '{"mimetype":"image/jpeg","size":100}'::jsonb from ca_boundary_context;

-- Trusted fixture setup only. This context is normally supplied by Storage API;
-- it never grants table access or bypasses object RLS to the browser roles.
select set_config('storage.allow_delete_query','true',true);

set local role anon;
do $$
declare c record;
begin
 select * into c from pg_temp.ca_boundary_context;
 perform set_config('request.jwt.claim.sub','',true);
 perform set_config('request.jwt.claims','{"role":"anon"}',true);
 perform pg_temp.ca_boundary_denied('anon_cannot_insert_storage_object',format(
  'insert into storage.objects(id,bucket_id,name,metadata) values(%L,''elan-sekilleri'',%L,''{"size":100}''::jsonb)',
  c.denied_insert_id,c.owner_a::text||'/original/'||c.denied_insert_id::text||'.jpg'));
 perform pg_temp.ca_boundary_zero('anon_cannot_delete_other_legacy_object',format(
  'delete from storage.objects where id=%L and bucket_id=''elan-sekilleri'' and name=%L',
  c.other_legacy_id,c.owner_b::text||'/original/'||c.other_legacy_id::text||'.jpg'));
 perform pg_temp.ca_boundary_zero('anon_cannot_delete_checked_object',format(
  'delete from storage.objects where id=%L and bucket_id=''elan-sekilleri'' and name=%L',
  c.own_checked_id,c.owner_a::text||'/checked/'||c.own_checked_id::text||'-ca-wm1.jpg'));
end$$;
reset role;

set local role authenticated;
do $$
declare c record;affected bigint;
begin
 select * into c from pg_temp.ca_boundary_context;
 perform set_config('request.jwt.claim.sub',c.owner_a::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',c.owner_a,
  'role','authenticated','user_metadata',jsonb_build_object('admin',true,'role','admin'))::text,true);
 perform pg_temp.ca_boundary_check('fake_admin_metadata_does_not_authorize',not public.cenub_admin_yoxla());
 perform pg_temp.ca_boundary_denied('auth_cannot_insert_other_prefix',format(
  'insert into storage.objects(id,bucket_id,name,metadata) values(%L,''elan-sekilleri'',%L,''{"size":100}''::jsonb)',
  c.denied_insert_id,c.owner_b::text||'/original/'||c.denied_insert_id::text||'.jpg'));
 perform pg_temp.ca_boundary_zero('auth_cannot_update_other_legacy_object',format(
  'update storage.objects set metadata=''{}''::jsonb where id=%L and bucket_id=''elan-sekilleri'' and name=%L',
  c.other_legacy_id,c.owner_b::text||'/original/'||c.other_legacy_id::text||'.jpg'));
 perform pg_temp.ca_boundary_zero('auth_cannot_delete_other_legacy_object',format(
  'delete from storage.objects where id=%L and bucket_id=''elan-sekilleri'' and name=%L',
  c.other_legacy_id,c.owner_b::text||'/original/'||c.other_legacy_id::text||'.jpg'));
 perform pg_temp.ca_boundary_zero('auth_cannot_delete_other_checked_object',format(
  'delete from storage.objects where id=%L and bucket_id=''elan-sekilleri'' and name=%L',
  c.other_checked_id,c.owner_b::text||'/checked/'||c.other_checked_id::text||'-ca-wm1.jpg'));

 -- A positive own-prefix INSERT proves the role is not simply denied all writes.
 insert into storage.objects(id,bucket_id,name,metadata) values(c.own_legacy_id,'elan-sekilleri',
  c.owner_a::text||'/original/'||c.own_legacy_id::text||'.jpg','{"mimetype":"image/jpeg","size":100}'::jsonb);
 get diagnostics affected=row_count;
 perform pg_temp.ca_boundary_check('own_legacy_insert_allowed',affected=1);
 -- Prove the SQL guard separately. Then emulate Storage API context again and
 -- require a positive OWN-prefix DELETE, so denied foreign deletes are genuine
 -- ownership checks rather than a globally blocked DELETE statement.
 perform set_config('storage.allow_delete_query','false',true);
 perform pg_temp.ca_boundary_denied('direct_sql_delete_guard_denies_own_fixture',format(
  'delete from storage.objects where id=%L and bucket_id=''elan-sekilleri'' and name=%L',
  c.own_legacy_id,c.owner_a::text||'/original/'||c.own_legacy_id::text||'.jpg'));
 perform set_config('storage.allow_delete_query','true',true);
 delete from storage.objects where id=c.own_legacy_id and bucket_id='elan-sekilleri'
  and name=c.owner_a::text||'/original/'||c.own_legacy_id::text||'.jpg';
 get diagnostics affected=row_count;
 perform pg_temp.ca_boundary_check('own_legacy_delete_allowed_in_api_context',affected=1);

 perform pg_temp.ca_boundary_denied('own_checked_insert_denied',format(
  'insert into storage.objects(id,bucket_id,name,metadata) values(%L,''elan-sekilleri'',%L,''{"size":100}''::jsonb)',
  c.denied_insert_id,c.owner_a::text||'/checked/'||c.denied_insert_id::text||'-ca-wm1.jpg'));
 perform pg_temp.ca_boundary_zero('own_checked_update_denied',format(
  'update storage.objects set metadata=''{}''::jsonb where id=%L and bucket_id=''elan-sekilleri'' and name=%L',
  c.own_checked_id,c.owner_a::text||'/checked/'||c.own_checked_id::text||'-ca-wm1.jpg'));
 perform pg_temp.ca_boundary_zero('own_checked_delete_denied',format(
  'delete from storage.objects where id=%L and bucket_id=''elan-sekilleri'' and name=%L',
  c.own_checked_id,c.owner_a::text||'/checked/'||c.own_checked_id::text||'-ca-wm1.jpg'));
end$$;
reset role;

do $$
declare c record;actual_hash text;
begin
 select * into c from pg_temp.ca_boundary_context;
 perform pg_temp.ca_boundary_check('other_and_checked_fixture_metadata_unchanged',(
  select count(*)=3 and bool_and(o.metadata='{"mimetype":"image/jpeg","size":100}'::jsonb)
  from storage.objects o where o.id in(c.other_legacy_id,c.own_checked_id,c.other_checked_id)));
 select md5(coalesce(jsonb_agg(to_jsonb(o) order by o.id)::text,'[]')) into actual_hash
  from storage.objects o
  where o.id not in(c.other_legacy_id,c.own_checked_id,c.other_checked_id,c.own_legacy_id);
 perform pg_temp.ca_boundary_check('preexisting_storage_metadata_unchanged',actual_hash=c.storage_before);
 perform set_config('storage.allow_delete_query',coalesce(c.delete_guard_before,'false'),true);
 perform pg_temp.ca_boundary_check('storage_api_context_restored',
  current_setting('storage.allow_delete_query',true)=coalesce(c.delete_guard_before,'false'));
 if (select count(*) from pg_temp.ca_boundary_results)<>25 then
  raise exception 'FAILED: expected exactly 25 boundary checks';
 end if;
end$$;

select count(*) passed_count,array_agg(name order by name) passed_checks from ca_boundary_results;
rollback;
select jsonb_build_object('suite','security_boundaries','passed',25,'synthetic_metadata_only',true,
 'transaction','ROLLBACK','existing_rows_changed',false,'provider_calls',0) as result;
