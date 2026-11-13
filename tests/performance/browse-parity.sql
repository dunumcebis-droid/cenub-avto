-- ISOLATED SYNTHETIC DATABASE ONLY. Never apply this fixture to production.
-- The disposable benchmark must have the original function copied to
-- ca_browse_listings_reference and the candidate installed as ca_browse_listings.
-- Every temporary fixture/ACL modification below is rolled back.
begin;
set local timezone='UTC';
set local statement_timeout='180s';
do $$begin
 if current_database()<>'ca_benchmark' or (select count(*) from public.elanlar)<>10750
 or exists(select 1 from public.elanlar where satici_id<>'22222222-2222-4222-8222-222222222222' or tesvir not like 'Synthetic benchmark vehicle.%') then
  raise exception 'Isolated benchmark fixture required';
 end if;
end$$;
-- A smaller matrix keeps parity coverage quick; the 10k rows return at rollback.
delete from public.elanlar where id not in(select id from public.elanlar order by id limit 480);
with numbered as(select id,row_number() over(order by id) n from public.elanlar)
update public.elanlar e set
 marka=case n%7 when 0 then U&'\00A0' when 1 then null when 2 then ' İSUZU ' else e.marka end,
 seher=case n%5 when 0 then '' when 1 then null else e.seher end,
 yurus=case n%5 when 0 then null when 1 then 0 else e.yurus end,
 muherrik_hecmi=case n%5 when 0 then null else e.muherrik_hecmi end,
 at_gucu=case n%7 when 0 then null else e.at_gucu end,
 techizat=case n%5 when 0 then null when 1 then '{}'::text[] when 2 then array['ABS',null] else e.techizat end,
 qiymet=case n%17 when 0 then null when 1 then 0 else e.qiymet end,
 paket_adi=case n%9 when 0 then 'VIP' when 1 then 'Premium' when 2 then 'Standart' when 3 then 'Unknown' else e.paket_adi end,
 paket_bitir=case n%5 when 0 then null when 1 then now()-interval '1 second' when 2 then now()+interval '1 day' else e.paket_bitir end,
 tesdiq_tarixi=case n%7 when 0 then null when 1 then now()+interval '1 day' when 2 then now()-interval '20 days' when 3 then now()-interval '1 day' else e.tesdiq_tarixi end,
 ca_data=case n%12 when 0 then 'null'::jsonb when 1 then to_jsonb('malformed {'::text) when 2 then '[]'::jsonb when 3 then to_jsonb('[]'::text)
 else case when n%3=0 then to_jsonb(jsonb_build_object('make','Toyota','modelName','Legacy','seher','Lənkəran','vehicle','Avtomobil','vehicleState','Yeni','bodyType','Sedan','reng','Qırmızı','bazar_ucun','Avropa','seats','5','km','1.234','muherrik_hecmi','1,8 L','hp','150 hp','equipment',jsonb_build_array('ABS','ESP'))::text)
 else jsonb_build_object('brand','LADA','model','Legacy','city','Bakı','vehicleType','Avtomobil','vehicleState','Sürülmüş','body','Sedan','color','Göy','market','Avropa','oturacaq_sayi',5,'mileage',1234,'engine',1.8,'horsepower',150,'techizat',jsonb_build_array('ABS','ESP')) end end
from numbered where e.id=numbered.id;
alter policy active_public on public.elanlar to anon,authenticated;
grant usage on schema auth to anon,authenticated;
grant execute on function auth.uid() to anon,authenticated;
grant select(id,satici_id,is_sold,marka,model,il,qiymet,yurus,seher,tesvir,veziyyet,yaradildi,neqliyyat_novu,nesil,ban_novu,yanacaq,suretler_qutusu,muherrik_hecmi,at_gucu,reng,bazar_ucun,oturacaq_sayi,techizat,sekiller,telefon,ca_data,paket_adi,paket_baslayir,paket_bitir,tesdiq_tarixi) on public.elanlar to authenticated;
create temporary table ca_parity_results(context text,case_number integer,params jsonb,passed boolean);
grant select,insert on ca_parity_results to anon,authenticated;
do $parity$
declare context text;uid text;f jsonb;old_result jsonb;new_result jsonb;row jsonb;pg integer;sz integer;case_number integer:=0;checks integer:=0;
 filters jsonb[]:=array[
 '{}'::jsonb,null,'{"make":"BMW"}','{"make":"toyota"}','{"make":"LADA"}','{"make":"isuzu"}','{"make":"İSUZU"}','{"make":"ısu"}',
 '{"model":"Legacy"}','{"model":"Model 0"}','{"city":"Bakı"}','{"city":"lənkəran"}','{"city":"Mingəçevir"}',
 '{"vehicle":"Avtomobil"}','{"state":"Yeni"}','{"state":"Sürülmüş"}','{"body":"Sedan"}','{"color":"Göy"}','{"color":"qırmızı"}','{"market":"Avropa"}','{"seats":"5"}',
 '{"price":10000}','{"priceMin":0,"priceMax":15000}','{"price":"10 000 AZN"}','{"price":-1}','{"price":""}',
 '{"yearMin":2005,"yearMax":2015}','{"yearMin":null,"yearMax":""}',
 '{"kmMin":0,"kmMax":3000}','{"kmMin":"1.234","kmMax":"15 000 km"}','{"engineMin":"1,8 L","engineMax":2}','{"hpMin":100,"hpMax":"160 hp"}',
 '{"equipment":[]}','{"equipment":["ABS"]}','{"equipment":["ABS","ESP"]}','{"equipment":[null]}','{"equipment":{"bad":"ABS"}}','{"equipment":["Never"]}',
 '{"pack":"all"}','{"pack":"VIP"}','{"pack":"Premium"}','{"pack":"Standart"}','{"pack":"Pulsuz"}','{"pack":"Unknown"}',
 '{"sort":"priceAsc"}','{"sort":"priceDesc"}','{"sort":"newest"}','{"sort":"unknown"}',
 '{"make":"BMW","city":"Bakı","priceMax":20000,"sort":"priceAsc"}',
 '{"make":"LADA","state":"Sürülmüş","body":"Sedan","equipment":["ABS"],"engineMin":1.6,"kmMax":100000}',
 '{"make":"not found","pack":"VIP"}','{"unknown":"ignored"}','{"make":123,"city":null}'
 ];
begin
 if exists(select 1 from pg_proc where oid in('public.ca_browse_listings(jsonb,integer,integer)'::regprocedure,'public.ca_browse_listings_reference(jsonb,integer,integer)'::regprocedure) and (prosecdef or provolatile<>'s' or proconfig is distinct from array['search_path=""'])) then raise exception 'Invoker/stable/search path contract changed';end if;
 if has_column_privilege('anon','public.elanlar','paket_tesdiq_qeydi','SELECT') or has_column_privilege('authenticated','public.elanlar','paket_tesdiq_qeydi','SELECT') then raise exception 'Internal column unexpectedly granted';end if;
 foreach context in array array['anon','owner','admin','other_signed_in'] loop
  perform set_config('role','none',true);
  uid:=case context when 'owner' then '22222222-2222-4222-8222-222222222222' when 'admin' then '11111111-1111-4111-8111-111111111111' when 'other_signed_in' then '33333333-3333-4333-8333-333333333333' else '' end;
  perform set_config('request.jwt.claim.sub',uid,true);
  perform set_config('role',case when context='anon' then 'anon' else 'authenticated' end,true);
  case_number:=0;
  foreach f in array filters loop
   case_number:=case_number+1;
   foreach pg in array array[1,3] loop
    old_result:=public.ca_browse_listings_reference(f,pg,24);new_result:=public.ca_browse_listings(f,pg,24);
    if old_result::text is distinct from new_result::text then raise exception 'Exact JSON parity failed: context %, filter %, page %',context,case_number,pg;end if;
    for row in select value from jsonb_array_elements(new_result->'items') union all select value from jsonb_array_elements(new_result->'vip_items') loop
     if (select count(*) from jsonb_object_keys(row))<>29 or row?'is_sold' or row?'paket_tesdiq_qeydi' then raise exception 'Public column projection changed';end if;
     if row->>'veziyyet'<>'aktiv' then raise exception 'Private listing appeared';end if;
    end loop;
    insert into pg_temp.ca_parity_results values(context,case_number,jsonb_build_object('page',pg,'size',24),true);checks:=checks+1;
   end loop;
  end loop;
  foreach pg in array array[null::integer,-1,0,2147483647] loop
   foreach sz in array array[null::integer,0,49] loop
    old_result:=public.ca_browse_listings_reference('{}',pg,sz);new_result:=public.ca_browse_listings('{}',pg,sz);
    if old_result::text is distinct from new_result::text then raise exception 'Page/size edge parity failed';end if;
    insert into pg_temp.ca_parity_results values(context,0,jsonb_build_object('page',pg,'size',sz),true);checks:=checks+1;
   end loop;
  end loop;
  begin perform public.ca_browse_listings('[]',1,24);raise exception 'Array filters unexpectedly accepted';exception when invalid_parameter_value then null;end;
  begin perform public.ca_browse_listings_reference('[]',1,24);raise exception 'Reference array filters unexpectedly accepted';exception when invalid_parameter_value then null;end;
 end loop;
 perform set_config('role','none',true);
 if checks<400 then raise exception 'Parity matrix incomplete';end if;
end $parity$;
select jsonb_build_object('success',bool_and(passed),'exact_json_comparisons',count(*),'contexts',(select jsonb_agg(context order by context) from(select distinct context from ca_parity_results)c),'public_projection_columns',29,'isolated_synthetic_rows',480,'live_writes',0) result from ca_parity_results;
rollback;
select count(*)=10750 as original_synthetic_rows_restored from public.elanlar;
