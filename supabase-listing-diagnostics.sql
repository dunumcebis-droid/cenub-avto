-- Cənub Avto: read-only diagnostics for an anonymous listing SELECT failure.
-- Run this file in the project's Supabase SQL Editor. It changes no permissions,
-- policies, rows, uploaded photos, packages or storage settings.
-- Check the failed HTTP response first: an invalid API key / JWT requires the
-- correct project URL and public key, not SQL permission changes.

select
  to_regclass('public.elanlar') as listing_table,
  current_user as diagnostic_role;

select
  c.relrowsecurity as rls_enabled,
  c.relforcerowsecurity as force_rls,
  pg_get_userbyid(c.relowner) as table_owner
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'elanlar';

select
  r.rolname,
  r.rolbypassrls,
  has_schema_privilege(r.rolname, 'public', 'USAGE') as schema_usage,
  has_table_privilege(r.rolname, to_regclass('public.elanlar'), 'SELECT') as table_select
from pg_roles r
where r.rolname in ('anon', 'authenticated');

select
  policyname, permissive, roles, cmd, qual, with_check
from pg_policies
where schemaname = 'public' and tablename = 'elanlar'
order by policyname;

select
  ordinal_position, column_name, data_type
from information_schema.columns
where table_schema = 'public' and table_name = 'elanlar'
order by ordinal_position;

-- Interpretation and conditional remediation (intentionally NOT executable):
--
-- 1. HTTP 401 with "Invalid API key", "invalid JWT", or an expired/invalid key:
--    verify the project URL / public anon or publishable key in Supabase.
--    Do not place a service_role or secret key in index.html.
--
-- 2. PostgreSQL 42501 "permission denied for table elanlar": compare the grants
--    above. Do not blindly GRANT SELECT: the page currently requests select=*,
--    which means every table column, including ca_data, would be readable when
--    its row passes RLS. Review the actual columns before granting access.
--
-- 3. A successful SELECT with [] is different from a 401: a SELECT policy may
--    be missing, there may be no active rows, or existing RLS rules may hide them.
--    Review the existing policies rather than replacing owner/admin policies.
--
-- If diagnosis confirms a missing anonymous SELECT grant AND all listing columns
-- are suitable for public active listings, the smallest reviewed migration is:
--
-- BEGIN;
-- -- Require RLS to already be enabled; do not silently change its configuration.
-- DO $$ BEGIN
--   IF NOT EXISTS (
--     SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
--     WHERE n.nspname = 'public' AND c.relname = 'elanlar' AND c.relrowsecurity
--   ) THEN
--     RAISE EXCEPTION 'Review and enable listing RLS before public access';
--   END IF;
-- END $$;
-- -- A restrictive policy also limits any existing broader permissive policies.
-- -- These names must be new; a collision safely aborts the transaction.
-- CREATE POLICY ca_anon_active_guard ON public.elanlar AS RESTRICTIVE
--   FOR SELECT TO anon USING (veziyyet = 'aktiv');
-- CREATE POLICY ca_anon_active_read ON public.elanlar AS PERMISSIVE
--   FOR SELECT TO anon USING (veziyyet = 'aktiv');
-- GRANT USAGE ON SCHEMA public TO anon;
-- GRANT SELECT ON public.elanlar TO anon;
-- COMMIT;
--
-- The example does not change authenticated users, INSERT/UPDATE/DELETE,
-- storage, package activation or admin functions. If any columns are private,
-- use an explicitly scoped public API/view and update the frontend query first.
-- Recheck the public API and an authenticated owner's cabinet after any reviewed
-- backend migration. No backend migration was executed by this code change.
