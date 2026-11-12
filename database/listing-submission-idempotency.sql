-- Same authenticated draft cannot create duplicate rows after a lost response.
-- No new API/table grants and no existing listing or photo is rewritten.
create unique index if not exists ca_elanlar_submission_once
on public.elanlar(satici_id,(ca_data->>'_submission_id'))
where (ca_data->>'_submission_id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

create or replace function ca_private.preserve_submission_key()
returns trigger language plpgsql security invoker set search_path='' as $$
begin
 if (old.ca_data->>'_submission_id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
  if jsonb_typeof(new.ca_data)='object' then
   new.ca_data:=jsonb_set(new.ca_data,'{_submission_id}',old.ca_data->'_submission_id',true);
  else
   new.ca_data:=jsonb_build_object('_submission_id',old.ca_data->'_submission_id');
  end if;
 end if;
 return new;
end $$;
revoke all on function ca_private.preserve_submission_key() from public,anon,authenticated;
do $trigger$
begin
 if not exists(select 1 from pg_trigger where tgname='zz_ca_preserve_submission_key' and tgrelid='public.elanlar'::regclass) then
  create trigger zz_ca_preserve_submission_key before update on public.elanlar
  for each row execute function ca_private.preserve_submission_key();
 end if;
end $trigger$;
notify pgrst,'reload schema';
