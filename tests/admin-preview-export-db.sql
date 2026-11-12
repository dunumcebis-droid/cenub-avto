-- Read-only role, private-preview and exact keyset-export checks. Always rolled back.
begin;
do $$
declare admin_id uuid; private_id uuid; expected jsonb; manifest jsonb; page jsonb; resource jsonb;
 cursor_id uuid; total integer; hashes text; seen integer; denied boolean; statement text; actual jsonb;
begin
 select istifadeci_id into admin_id from public.adminler limit 1;
 if admin_id is null then raise exception 'An existing administrator is required for this verification.'; end if;
 select id,to_jsonb(e) into private_id,expected from public.elanlar e order by id limit 1;
 if has_function_privilege('anon','public.ca_admin_listing_detail(uuid)','execute') or
    has_function_privilege('anon','public.ca_admin_export_manifest()','execute') or
    has_function_privilege('anon','public.ca_admin_export_page(text,uuid,integer)','execute') then raise exception 'Anonymous RPC execution is open.'; end if;
 if exists(select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname in ('ca_admin_listing_detail','ca_admin_export_manifest','ca_admin_export_page') and p.prosecdef) then raise exception 'Public wrappers must be invoker.'; end if;
 perform set_config('request.jwt.claim.sub',admin_id::text,true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',admin_id,'role','authenticated')::text,true);
 perform set_config('role','authenticated',true);
 if private_id is not null and public.ca_admin_listing_detail(private_id) is distinct from expected then raise exception 'Admin preview is incomplete.'; end if;
 if public.ca_admin_listing_detail('ffffffff-ffff-4fff-8fff-ffffffffffff') is not null then raise exception 'Missing listing did not return null.'; end if;
 manifest:=public.ca_admin_export_manifest();
 if manifest->>'version'<>'1' or jsonb_array_length(manifest->'resources')<>5 then raise exception 'Manifest is incomplete.'; end if;
 for resource in select value from jsonb_array_elements(manifest->'resources') loop
  cursor_id:=null;total:=0;hashes:='';seen:=0;
  loop
   page:=public.ca_admin_export_page(resource->>'name',cursor_id,2);
   if jsonb_array_length(page->'items')>2 or jsonb_array_length(page->'items')<>jsonb_array_length(page->'hashes') then raise exception 'Bad page size/hash pairing.'; end if;
   total:=total+jsonb_array_length(page->'items');
   select hashes||coalesce(string_agg(value,'' order by ordinal), '') into hashes from jsonb_array_elements_text(page->'hashes') with ordinality as h(value,ordinal);
   exit when page->>'next_cursor' is null;
   if cursor_id is not null and (page->>'next_cursor')::uuid<=cursor_id then raise exception 'Cursor is not increasing.'; end if;
   cursor_id:=(page->>'next_cursor')::uuid;seen:=seen+1;
   if seen>10000 then raise exception 'Pagination did not finish.'; end if;
  end loop;
  if total<>(resource->>'count')::integer or encode(sha256(convert_to(hashes,'UTF8')),'hex')<>resource->>'sha256' then raise exception 'Rows were skipped, duplicated or changed.'; end if;
 end loop;
 if (public.ca_admin_export_manifest()->'resources') is distinct from manifest->'resources' then raise exception 'Read-only verification changed export state.'; end if;
 foreach statement in array array[
  $q$select public.ca_admin_export_page('elanlar',null,0)$q$,
  $q$select public.ca_admin_export_page('elanlar',null,201)$q$,
  $q$select public.ca_admin_export_page('auth.users',null,100)$q$,
  $q$select public.ca_admin_export_page('elanlar; delete from public.elanlar',null,100)$q$
 ] loop
  denied:=false;begin execute statement into actual;exception when invalid_parameter_value then denied:=true;end;
  if not denied then raise exception 'Invalid export parameters were accepted.'; end if;
 end loop;
 -- The same authenticated API grant must never authorize an ordinary user,
 -- even if that user's editable metadata claims to be an administrator.
 perform set_config('request.jwt.claim.sub','eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',true);
 perform set_config('request.jwt.claims','{"sub":"eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee","role":"authenticated","user_metadata":{"admin":true}}',true);
 foreach statement in array array[
  $q$select public.ca_admin_listing_detail('ffffffff-ffff-4fff-8fff-ffffffffffff')$q$,
  $q$select public.ca_admin_export_manifest()$q$,
  $q$select public.ca_admin_export_page('elanlar',null,100)$q$,
  $q$select ca_private.admin_export_manifest()$q$
 ] loop
  denied:=false;begin execute statement into actual;exception when insufficient_privilege then denied:=true;end;
  if not denied then raise exception 'Ordinary user accessed private data.'; end if;
 end loop;
 perform set_config('role','anon',true);
 denied:=false;begin perform public.ca_admin_export_manifest();exception when insufficient_privilege then denied:=true;end;
 if not denied then raise exception 'Anonymous user accessed export.'; end if;
end $$;
rollback;
select jsonb_build_object('admin_preview','passed','exact_keyset_export_all_five_resources','passed','public_invoker_wrappers','passed','anonymous_and_non_admin_denials','passed','editable_metadata_not_authorization','passed','invalid_resource_and_size_denials','passed','real_records_changed',false) as result;
