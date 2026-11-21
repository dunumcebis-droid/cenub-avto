-- PostgreSQL 17: remove unused browser-role capabilities without changing rows,
-- RLS policies, owner-scoped profile writes, listing edits or admin RPCs.
-- TRUNCATE is not protected by RLS; it is not a PostgREST table endpoint either.
-- These revokes are defense in depth, not evidence of an exposed SQL endpoint.
revoke truncate, references, trigger, maintain
 on table public.profiller from public, anon, authenticated;
revoke delete on table public.elanlar from public, anon, authenticated;

do $browser_privileges$
declare role_name text; privilege_name text;
begin
 foreach role_name in array array['anon','authenticated'] loop
  foreach privilege_name in array array['TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'] loop
   if has_table_privilege(role_name,'public.profiller',privilege_name) then
    raise exception 'Unused profile capability remains: % %',role_name,privilege_name;
   end if;
  end loop;
  if has_table_privilege(role_name,'public.elanlar','DELETE') then
   raise exception 'Browser role can hard-delete listings: %',role_name;
  end if;
 end loop;
 foreach privilege_name in array array['SELECT','INSERT','UPDATE'] loop
  if not has_table_privilege('authenticated','public.profiller',privilege_name) then
   raise exception 'Required owner-scoped profile capability missing: %',privilege_name;
  end if;
 end loop;
 if not has_column_privilege('authenticated','public.elanlar','tesvir','UPDATE')
 or has_column_privilege('anon','public.elanlar','tesvir','UPDATE')
 or has_column_privilege('authenticated','public.elanlar','paket_adi','UPDATE') then
  raise exception 'Listing column privilege boundary changed unexpectedly';
 end if;
 if not (select relrowsecurity from pg_class where oid='public.profiller'::regclass)
 or not (select relrowsecurity from pg_class where oid='public.elanlar'::regclass) then
  raise exception 'Required RLS protection missing';
 end if;
end $browser_privileges$;
