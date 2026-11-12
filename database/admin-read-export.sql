-- Reference SQL for the remote admin-preview/application-export migration.
-- No listing, profile, package request or stored image is changed.
create schema if not exists ca_private;
revoke all on schema ca_private from public, anon;
grant usage on schema ca_private to authenticated;

create or replace function ca_private.require_admin()
returns void language plpgsql stable security definer set search_path = '' as $$
begin
 if auth.uid() is null or not exists(select 1 from public.adminler a where a.istifadeci_id=auth.uid()) then
  raise exception 'Admin girişi tələb olunur.' using errcode='42501';
 end if;
end $$;

create or replace function ca_private.admin_listing_detail(p_id uuid)
returns jsonb language plpgsql stable security definer set search_path = '' as $$
declare result jsonb;
begin
 perform ca_private.require_admin();
 select to_jsonb(e) into result from public.elanlar e where e.id=p_id;
 return result;
end $$;

-- The fixed allowlist is used to build paged SQL. No caller-supplied SQL/identifier
-- is interpolated, and direct table queries retain primary-key pagination.
create or replace function ca_private.export_resource_sql(p_resource text)
returns text language plpgsql immutable set search_path = '' as $$
begin
 case p_resource
 when 'elanlar' then return 'select e.id row_key,to_jsonb(e) row_data from public.elanlar e';
 when 'paket_sorgulari' then return 'select p.id row_key,to_jsonb(p) row_data from public.paket_sorgulari p';
 when 'profiller' then return 'select p.id row_key,to_jsonb(p) row_data from public.profiller p';
 when 'adminler' then return 'select a.istifadeci_id row_key,to_jsonb(a) row_data from public.adminler a';
 when 'storage_objects' then return $query$select o.id row_key,jsonb_build_object(
  'id',o.id,'bucket_id',o.bucket_id,'name',o.name,'metadata',o.metadata,
  'created_at',o.created_at,'updated_at',o.updated_at,'version',o.version,
  'owner',o.owner,'owner_id',o.owner_id,'user_metadata',o.user_metadata) row_data
  from storage.objects o where o.bucket_id='elan-sekilleri'
   and o.archived_at is null and not coalesce(o.is_delete_marker,false)$query$;
 else raise exception 'Naməlum ehtiyat nüsxə mənbəyi.' using errcode='22023';
 end case;
end $$;

create or replace function ca_private.admin_export_manifest()
returns jsonb language plpgsql stable security definer set search_path = '' as $$
declare resource text; total bigint; fingerprint text; resources jsonb:='[]'::jsonb;
begin
 perform ca_private.require_admin();
 foreach resource in array array['elanlar','paket_sorgulari','profiller','adminler','storage_objects'] loop
  execute 'select count(*),encode(sha256(convert_to(coalesce(string_agg(encode(sha256(convert_to(row_data::text,''UTF8'')),''hex''),'''' order by row_key),''''),''UTF8'')),''hex'') from ('||ca_private.export_resource_sql(resource)||') source'
   into total,fingerprint;
  resources:=resources||jsonb_build_array(jsonb_build_object('name',resource,'count',total,'sha256',fingerprint));
 end loop;
 return jsonb_build_object('version',1,'generated_at',transaction_timestamp(),'resources',resources,
  'scope','application tables and current listing bucket objects; excludes Auth secrets/system configuration');
end $$;

create or replace function ca_private.admin_export_page(p_resource text,p_cursor uuid default null,p_page_size integer default 100)
returns jsonb language plpgsql stable security definer set search_path = '' as $$
declare batch jsonb; items jsonb; hashes jsonb; next_cursor text; page_size integer;
begin
 perform ca_private.require_admin();
 if p_page_size is null or p_page_size<1 or p_page_size>200 then
  raise exception 'Səhifə ölçüsü 1–200 olmalıdır.' using errcode='22023';
 end if;
 page_size:=p_page_size;
 execute 'select coalesce(jsonb_agg(jsonb_build_object(''key'',row_key,''item'',row_data,''hash'',encode(sha256(convert_to(row_data::text,''UTF8'')),''hex'')) order by row_key),''[]''::jsonb) from (select * from ('||ca_private.export_resource_sql(p_resource)||') source where ($1 is null or row_key>$1) order by row_key limit $2) page'
  into batch using p_cursor,page_size+1;
 if jsonb_array_length(batch)>page_size then next_cursor:=batch->(page_size-1)->>'key'; end if;
 select coalesce(jsonb_agg(entry->'item' order by ord),'[]'::jsonb),coalesce(jsonb_agg(entry->'hash' order by ord),'[]'::jsonb)
 into items,hashes from jsonb_array_elements(batch) with ordinality as rows(entry,ord) where ord<=page_size;
 return jsonb_build_object('items',items,'hashes',hashes,'next_cursor',next_cursor);
end $$;

-- Invoker wrappers are the only Data API endpoints. Privileged reads stay in an
-- unexposed schema and re-check current admin membership on every request.
create or replace function public.ca_admin_listing_detail(p_id uuid)
returns jsonb language sql stable security invoker set search_path = ''
as $$ select ca_private.admin_listing_detail(p_id) $$;
create or replace function public.ca_admin_export_manifest()
returns jsonb language sql stable security invoker set search_path = ''
as $$ select ca_private.admin_export_manifest() $$;
create or replace function public.ca_admin_export_page(p_resource text,p_cursor uuid default null,p_page_size integer default 100)
returns jsonb language sql stable security invoker set search_path = ''
as $$ select ca_private.admin_export_page(p_resource,p_cursor,p_page_size) $$;

revoke all on function ca_private.require_admin() from public,anon,authenticated;
revoke all on function ca_private.export_resource_sql(text) from public,anon,authenticated;
revoke all on function ca_private.admin_listing_detail(uuid) from public,anon,authenticated;
revoke all on function ca_private.admin_export_manifest() from public,anon,authenticated;
revoke all on function ca_private.admin_export_page(text,uuid,integer) from public,anon,authenticated;
grant execute on function ca_private.admin_listing_detail(uuid),ca_private.admin_export_manifest(),ca_private.admin_export_page(text,uuid,integer) to authenticated;
revoke all on function public.ca_admin_listing_detail(uuid),public.ca_admin_export_manifest(),public.ca_admin_export_page(text,uuid,integer) from public,anon,authenticated;
grant execute on function public.ca_admin_listing_detail(uuid),public.ca_admin_export_manifest(),public.ca_admin_export_page(text,uuid,integer) to authenticated;
notify pgrst,'reload schema';
