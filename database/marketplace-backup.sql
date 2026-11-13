-- Add marketplace data to the existing admin-only application ZIP backup.
-- Apply after admin-read-export.sql and marketplace-features.sql, together with
-- the matching twelve-resource allowlist in assets/js/14-server-backup.js.
-- No listing/photo/package is updated. Raw private-table grants and RLS remain
-- unchanged. The existing UUID-cursor page API and SHA-256 row checks remain.

-- Two tables have non-UUID primary keys. Their deterministic export-only UUID
-- expressions are indexed so each page can seek rather than rescan/sort them.
-- The positive bigint identity is encoded losslessly, without a hash.
create unique index if not exists ca_approved_events_export_key
 on ca_private.approved_listing_events ((lpad(to_hex(seq),32,'0')::uuid));

-- A composite event key cannot fit losslessly into a UUID. Use a deterministic
-- digest of an unambiguous tuple. A unique index rejects any theoretical digest
-- collision instead of allowing UUID keyset pagination to silently skip a row.
-- Integer days avoid DateStyle/time-zone dependent date-to-text conversions.
create unique index if not exists ca_listing_events_export_key
 on ca_private.listing_events ((md5(elan_id::text||':'||kind||':'||
  (day-date '2000-01-01')::text||':'||visitor_hash)::uuid));

-- SQL fragments come only from this fixed allowlist, never user identifiers.
-- The first five fragments preserve the existing export representation.
create or replace function ca_private.export_resource_sql(p_resource text)
returns text language plpgsql immutable security invoker set search_path='' as $$
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
 when 'listing_stats' then return 'select s.elan_id row_key,to_jsonb(s) row_data from ca_private.listing_stats s';
 when 'listing_events' then return $query$select
  md5(e.elan_id::text||':'||e.kind||':'||(e.day-date '2000-01-01')::text||':'||e.visitor_hash)::uuid row_key,
  to_jsonb(e) row_data from ca_private.listing_events e$query$;
 when 'listing_reports' then return 'select r.id row_key,to_jsonb(r) row_data from ca_private.listing_reports r';
 when 'saved_searches' then return 'select s.id row_key,to_jsonb(s) row_data from ca_private.saved_searches s';
 when 'approved_listing_events' then return $query$select
  lpad(to_hex(e.seq),32,'0')::uuid row_key,to_jsonb(e) row_data from ca_private.approved_listing_events e$query$;
 when 'notification_progress' then return 'select p.owner_id row_key,to_jsonb(p) row_data from ca_private.notification_progress p';
 when 'search_notifications' then return 'select n.id row_key,to_jsonb(n) row_data from ca_private.search_notifications n';
 else raise exception 'Naməlum ehtiyat nüsxə mənbəyi.' using errcode='22023';
 end case;
end $$;

create or replace function ca_private.admin_export_manifest()
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare resource text; total bigint; fingerprint text; resources jsonb:='[]'::jsonb;
begin
 -- Recheck current database membership, not editable JWT/user metadata.
 perform ca_private.require_admin();
 foreach resource in array array[
  'elanlar','paket_sorgulari','profiller','adminler','storage_objects',
  'listing_stats','listing_events','listing_reports','saved_searches',
  'approved_listing_events','notification_progress','search_notifications'
 ] loop
  execute 'select count(*),encode(sha256(convert_to(coalesce(string_agg(encode(sha256(convert_to(row_data::text,''UTF8'')),''hex''),'''' order by row_key),''''),''UTF8'')),''hex'') from ('||ca_private.export_resource_sql(resource)||') source'
   into total,fingerprint;
  resources:=resources||jsonb_build_array(jsonb_build_object('name',resource,'count',total,'sha256',fingerprint));
 end loop;
 return jsonb_build_object('version',1,'generated_at',transaction_timestamp(),'resources',resources,
  'scope','application and marketplace tables and current listing bucket objects; excludes Auth secrets/system configuration');
end $$;

-- Retain the guarded internal page implementation from admin-read-export.sql:
-- require_admin() every request, sizes 1..200, UUID keyset, paired row hashes.
-- Reassert invoker-only public wrappers and their narrow existing RPC grants.
create or replace function public.ca_admin_export_manifest()
returns jsonb language sql stable security invoker set search_path=''
as $$ select ca_private.admin_export_manifest() $$;
create or replace function public.ca_admin_export_page(p_resource text,p_cursor uuid default null,p_page_size integer default 100)
returns jsonb language sql stable security invoker set search_path=''
as $$ select ca_private.admin_export_page(p_resource,p_cursor,p_page_size) $$;

revoke all on function ca_private.export_resource_sql(text) from public,anon,authenticated;
revoke all on function ca_private.admin_export_manifest(),ca_private.admin_export_page(text,uuid,integer) from public,anon,authenticated;
grant execute on function ca_private.admin_export_manifest(),ca_private.admin_export_page(text,uuid,integer) to authenticated;
revoke all on function public.ca_admin_export_manifest(),public.ca_admin_export_page(text,uuid,integer) from public,anon,authenticated;
grant execute on function public.ca_admin_export_manifest(),public.ca_admin_export_page(text,uuid,integer) to authenticated;
notify pgrst,'reload schema';
