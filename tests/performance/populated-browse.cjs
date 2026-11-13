'use strict';
/** Exact repository browse SQL on a disposable, network-isolated PostgreSQL.
 * No Supabase connection, real listing, upload, provider call or host bind mount.
 * Requires a local Docker daemon and the pinned official image below.
 */
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const IMAGE='postgres:17.7-alpine@sha256:bb377b7239d2774ac8cc76f481596ce96c5a6b5e9d141f6d0a0ee371a6e7c0f2';
const ROOT=path.resolve(__dirname,'../..');
const options=process.argv.slice(2);
const destination=options.find(value=>!value.startsWith('--'))||path.join(__dirname,'populated-browse-result.json');
const existing=options.find(value=>value.startsWith('--container='))?.slice(12);
if(existing&&!/^ca-browse-benchmark-[0-9]+-[0-9]+$/.test(existing))throw Error('Only an explicit benchmark-owned container is accepted');
const taskContainer=existing||'ca-browse-benchmark-'+process.pid+'-'+Date.now();
const keepContainer=options.includes('--keep-container');
const setupOnly=options.includes('--setup-only');
const referenceOnly=options.includes('--reference');
const baselineMode=options.includes('--baseline');
const concurrencyOnly=options.includes('--concurrency-only');
const functionName=referenceOnly?'public.ca_browse_listings_reference':'public.ca_browse_listings';
const dockerEnv={...process.env};
for(const key of ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'])delete dockerEnv[key];
function docker(args,input,timeout=60000){return execFileSync('docker',['--host=unix:///var/run/docker.sock',...args],{env:dockerEnv,input,encoding:'utf8',timeout,maxBuffer:32*1024*1024,stdio:['pipe','pipe','pipe']});}
function sql(query){return docker(['exec','-i',taskContainer,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','postgres','-d','ca_benchmark','-At'],query);}
function percentile(values,p){const copy=[...values].sort((a,b)=>a-b);return Number(copy[Math.max(0,Math.ceil(copy.length*p)-1)].toFixed(3));}
const quoted=value=>"'"+String(value).replaceAll("'","''")+"'";
function functionSql(){
 const old=fs.readFileSync(path.join(ROOT,'database/applied-listing-management.sql'),'utf8');
 const current=fs.readFileSync(path.join(ROOT,'database/marketplace-features.sql'),'utf8');
 const helpers=old.slice(old.indexOf('create or replace function public.ca_listing_value'),old.indexOf('create or replace function public.ca_browse_listings('));
 const referenceBrowse=current.slice(current.indexOf('CREATE OR REPLACE FUNCTION public.ca_browse_listings('),current.indexOf('CREATE OR REPLACE FUNCTION public.ca_admin_status('));
 const latestPath=path.join(ROOT,'database/browse-performance.sql');
 const browse=!baselineMode&&fs.existsSync(latestPath)?fs.readFileSync(latestPath,'utf8'):referenceBrowse;
 assert.ok(helpers.includes('ca_listing_number(variadic p_values jsonb[])')&&browse.includes('and not e.is_sold'),'Exact current source extraction failed');
 return {helpers,browse,referenceBrowse};
}
const setup=`
create role anon;create role authenticated;
create table public.elanlar(id uuid primary key,satici_id uuid not null,is_sold boolean not null default false,
 marka text,model text,il integer,qiymet numeric,yurus integer,seher text,tesvir text,veziyyet text,yaradildi timestamptz,
 neqliyyat_novu text,nesil text,ban_novu text,yanacaq text,suretler_qutusu text,muherrik_hecmi numeric,at_gucu integer,reng text,
 bazar_ucun text,oturacaq_sayi integer,techizat text[],sekiller text[],telefon text,ca_data jsonb,paket_adi text,
 paket_baslayir timestamptz,paket_bitir timestamptz,tesdiq_tarixi timestamptz);
alter table public.elanlar enable row level security;
create policy active_public on public.elanlar for select to anon,authenticated using(veziyyet='aktiv' and not is_sold);
alter table public.elanlar add column paket_tesdiq_qeydi text default 'Synthetic internal note';
grant select(id,satici_id,is_sold,marka,model,il,qiymet,yurus,seher,tesvir,veziyyet,yaradildi,neqliyyat_novu,nesil,ban_novu,yanacaq,suretler_qutusu,muherrik_hecmi,at_gucu,reng,bazar_ucun,oturacaq_sayi,techizat,sekiller,telefon,ca_data,paket_adi,paket_baslayir,paket_bitir,tesdiq_tarixi) on public.elanlar to anon,authenticated;
grant usage on schema public to anon,authenticated;
create schema auth;
create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
grant usage on schema auth to anon,authenticated;
grant execute on function auth.uid() to anon,authenticated;
create policy owner_private on public.elanlar for select to authenticated using(satici_id=(select auth.uid()));
create policy admin_private on public.elanlar for select to authenticated using((select auth.uid())='11111111-1111-4111-8111-111111111111');
create index elanlar_active_created_id_idx on public.elanlar(yaradildi desc,id desc) where veziyyet='aktiv';
create index elanlar_owner_created_id_idx on public.elanlar(satici_id,yaradildi desc,id desc);
with candidates as(
 select n,(array['BMW','Toyota','LADA','Mercedes-Benz'])[1+n%4] make,
 (array['Bakı','Lənkəran','Mingəçevir'])[1+n%3] city,
 array(select 'https://fixture.invalid/benchmark-'||n||'-'||p||'.jpg' from generate_series(1,12)p) photos
 from generate_series(1,10750)n
), docs as(
 select *,jsonb_build_object('make',make,'model','Model '||lpad((n%100)::text,2,'0'),'city',city,
 'vehicleState','Sürülmüş','mileage',n*10,'engine',1.6+(n%5)::numeric/10,'horsepower',100+n%200,
 'equipment',jsonb_build_array('ABS','ESP','Kondisioner'),
 'photos',jsonb_build_object('front',to_jsonb(photos[1:2]),'rear',to_jsonb(photos[3:4]),'side',to_jsonb(photos[5:6]),'interior',to_jsonb(photos[7:8]),'engine',to_jsonb(photos[9:10]),'other',to_jsonb(photos[11:12])),
 'photo',photos[1],'description',repeat('Synthetic benchmark vehicle. ',20)) data
 from candidates
)
insert into public.elanlar(id,satici_id,is_sold,marka,model,il,qiymet,yurus,seher,tesvir,veziyyet,yaradildi,neqliyyat_novu,nesil,ban_novu,yanacaq,suretler_qutusu,muherrik_hecmi,at_gucu,reng,bazar_ucun,oturacaq_sayi,techizat,sekiller,telefon,ca_data,paket_adi,paket_baslayir,paket_bitir,tesdiq_tarixi)
 select md5('ca-benchmark-'||n)::uuid,'22222222-2222-4222-8222-222222222222',n between 10001 and 10250,
 case when n%17=0 then '' else make end,'Model '||lpad((n%100)::text,2,'0'),2000+n%25,5000+(n%900)*50,
 case when n%13=0 then null else n*10 end,case when n%19=0 then '' else city end,repeat('Synthetic benchmark vehicle. ',20),
 case when n<=10250 then 'aktiv' when n<=10500 then 'gozlemede' else 'reddedildi' end,
 timestamptz '2026-11-13 00:00:00+00'-make_interval(mins=>n),'Avtomobil','Synthetic generation','Sedan','Benzin','Avtomat',1.6+(n%5)::numeric/10,100+n%200,'Göy','Avropa',5,
 array['ABS','ESP','Kondisioner'],photos,'+994000000000',case when n%11=0 then to_jsonb(data::text) else data end,
 case n%20 when 0 then 'VIP' when 1 then 'Premium' when 2 then 'Standart' else 'Pulsuz' end,now()-interval '1 day',now()+interval '30 days',
 timestamptz '2026-11-13 00:00:00+00'-make_interval(mins=>n)
 from docs;
analyze public.elanlar;
`;
const reference=Array.from({length:10000},(_,i)=>{const n=i+1;return {n,id:crypto.createHash('md5').update('ca-benchmark-'+n).digest('hex').replace(/(.{8})(.{4})(.{4})(.{4})(.{12})/,'$1-$2-$3-$4-$5'),make:['BMW','Toyota','LADA','Mercedes-Benz'][n%4],city:['Bakı','Lənkəran','Mingəçevir'][n%3],price:5000+(n%900)*50,rank:n%20===0?0:n%20===1?1:n%20===2?2:3};});
const cases=[
 {name:'first_page',filters:{},page:1},
 {name:'deep_page_200',filters:{},page:200},
 {name:'last_page_417',filters:{},page:417},
 {name:'make_city_price_filter',filters:{make:'BMW',city:'Bakı',priceMax:20000},page:1},
 {name:'price_ascending',filters:{sort:'priceAsc'},page:1},
 {name:'price_descending',filters:{sort:'priceDesc'},page:1}
];
async function main(){
 const {helpers,browse,referenceBrowse}=functionSql();let started=false;
 try{
  if(!existing){docker(['run','-d','--rm','--name',taskContainer,'--network','none','--cpus','2','--memory','768m','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_DB=ca_benchmark',IMAGE,'-c','shared_buffers=128MB','-c','max_connections=60']);started=true;
  let ready=false;for(let i=0;i<80;i++){try{const startup=docker(['logs',taskContainer],undefined,5000);if(!startup.includes('PostgreSQL init process complete; ready for start up.'))throw Error('Initialization pending');docker(['exec',taskContainer,'pg_isready','-U','postgres','-d','ca_benchmark'],undefined,5000);ready=true;break;}catch{await new Promise(resolve=>setTimeout(resolve,250));}}
  assert.ok(ready,'Isolated PostgreSQL did not become ready');
  const referenceDefinition=referenceBrowse.replace(/(function\s+)public\.ca_browse_listings\(/i,'$1public.ca_browse_listings_reference(');
  assert.ok(referenceDefinition.includes('ca_browse_listings_reference('));
  sql(setup+helpers+referenceDefinition+browse+'\ngrant execute on function public.ca_browse_listings(jsonb,integer,integer) to anon;');
  }
  if(setupOnly){console.log(JSON.stringify({container:taskContainer,setupComplete:true}));return;}
  const serverVersion=sql('select version();').trim();
  const executedBrowseSha256=crypto.createHash('sha256').update(sql("select pg_get_functiondef('"+functionName+"(jsonb,integer,integer)'::regprocedure);")).digest('hex');
  const dataset=JSON.parse(sql("select jsonb_build_object('total_rows',count(*),'active_unsold',count(*) filter(where veziyyet='aktiv' and not is_sold),'sold',count(*) filter(where is_sold),'pending',count(*) filter(where veziyyet='gozlemede'),'rejected',count(*) filter(where veziyyet='reddedildi'),'relation_bytes',pg_total_relation_size('public.elanlar')) from public.elanlar;").trim());
  assert.equal(dataset.active_unsold,10000);assert.equal(dataset.total_rows,10750);
  const permissions=JSON.parse(sql("select jsonb_build_object('role','anon','tableLevelSelectGranted',has_table_privilege('anon','public.elanlar','SELECT'),'privateColumnSelectGranted',has_column_privilege('anon','public.elanlar','paket_tesdiq_qeydi','SELECT'),'rlsEnabled',(select relrowsecurity from pg_class where oid='public.elanlar'::regclass));").trim());
  assert.equal(permissions.tableLevelSelectGranted,false);assert.equal(permissions.privateColumnSelectGranted,false);assert.equal(permissions.rlsEnabled,true);
  const results=[];
  const concurrency=[];let complete=false;
  function snapshot(){const report={complete,success:complete&&concurrency.every(stage=>!stage.failure),generatedAt:new Date().toISOString(),scope:'Synthetic isolated PostgreSQL only; no live Supabase requests, no real business records, no model or image requests.',image:IMAGE,serverVersion,functionName,permissions,limits:{cpus:2,memoryMiB:768,sharedBuffersMiB:128,statementTimeoutSeconds:15},dataset,executedBrowseSha256,referenceSourceSha256:crypto.createHash('sha256').update(helpers+referenceBrowse).digest('hex'),cases:results,concurrency,claims:{productionCapacityEstablished:false,realUsersSimulated:false,liveWrites:0}};fs.mkdirSync(path.dirname(destination),{recursive:true});fs.writeFileSync(destination,JSON.stringify(report,null,2)+'\n');return report;}
  snapshot();
  for(const item of (concurrencyOnly?[]:cases)){
   const select='select '+functionName+'('+quoted(JSON.stringify(item.filters))+'::jsonb,'+item.page+',24)';
   const raw=sql("set role anon;set statement_timeout='15s';"+select+';').trim();const value=JSON.parse(raw);
   const filtered=reference.filter(r=>(!item.filters.make||r.make===item.filters.make)&&(!item.filters.city||r.city===item.filters.city)&&(!item.filters.priceMax||r.price<=item.filters.priceMax));
   filtered.sort((a,b)=>a.rank-b.rank||((item.filters.sort==='priceAsc'?a.price-b.price:item.filters.sort==='priceDesc'?b.price-a.price:0))||a.n-b.n);
   const expected=filtered.slice((item.page-1)*24,item.page*24);
   assert.equal(value.total,filtered.length,item.name+' count');assert.equal(value.total_pages,Math.ceil(filtered.length/24),item.name+' pages');
   assert.deepEqual(value.items.map(r=>r.id),expected.map(r=>r.id),item.name+' exact ordering and page');
   assert.ok(value.items.every(r=>r.veziyyet==='aktiv'),'Only active rows');assert.equal(value.vip_items.length,6);
   assert.ok(value.items.every(r=>r.sekiller.length===12),'Complete synthetic photograph metadata');
   const timings=[];
   for(let run=0;run<1;run++){
    const plan=JSON.parse(sql("set role anon;set statement_timeout='15s';explain(analyze,buffers,format json) "+select+';').trim())[0];
    timings.push(plan['Execution Time']);
   }
   results.push({name:item.name,filters:item.filters,page:item.page,totalMatches:value.total,returnedItems:value.items.length,payloadBytes:Buffer.byteLength(raw),warmRuns:1,executionMs:timings,p50Ms:percentile(timings,.5),p95Ms:percentile(timings,.95)});snapshot();console.error(JSON.stringify({case:item.name,executionMs:timings}));
  }
  const phases=referenceOnly?[{name:'default',clients:10,filters:{}},{name:'default',clients:20,filters:{}}]:[
   ...[1,5,10,20].map(clients=>({name:'default',clients,filters:{}})),
   {name:'combined_filter',clients:20,filters:{make:'BMW',city:'Bakı',priceMax:20000}}
  ];
  for(const phase of phases){
   const clients=phase.clients;
   docker(['exec','-i',taskContainer,'sh','-c','cat > /tmp/ca-benchmark.sql'],"set role anon;\nset statement_timeout='15s';\nselect "+functionName+"("+quoted(JSON.stringify(phase.filters))+"::jsonb,1,24);\n");
   const transactions=clients===1?3:1;
   const prefix='/tmp/ca-pgbench-'+(referenceOnly?'reference-':'')+phase.name+'-'+clients;
   let output,failure;
   try{output=docker(['exec',taskContainer,'pgbench','-n','-U','postgres','-d','ca_benchmark','-f','/tmp/ca-benchmark.sql','-c',String(clients),'-j',String(Math.min(clients,4)),'-t',String(transactions),'-l','--log-prefix='+prefix],undefined,60000);}catch(error){output=error.stdout?.toString()||'';failure={exitStatus:error.status,statementTimeout:String(error.stderr||'').includes('statement timeout'),message:String(error.stderr||error.message).split('\n')[0]};}
   if(!failure)assert.match(output,/number of failed transactions:\s+0\s/,'All synthetic concurrent reads succeed');
   let logs='';try{logs=docker(['exec',taskContainer,'sh','-c','cat '+prefix+'.*']);}catch{}
   const logEntries=logs.trim().split('\n').filter(Boolean).map(line=>line.trim().split(/\s+/));
   const latency=logEntries.map(entry=>Number(entry[2])/1000).filter(value=>Number.isFinite(value)&&value>=0);
   if(!failure)assert.equal(latency.length,clients*transactions,'Every transaction has a latency log');assert.ok(latency.every(Number.isFinite));
   concurrency.push({name:phase.name,filters:phase.filters,clients,workerThreads:Math.min(clients,4),transactions:latency.length,requestedTransactions:clients*transactions,failedOrUnfinishedTransactions:clients*transactions-latency.length,stageAborted:!!failure,failure,p50Ms:latency.length?percentile(latency,.5):null,p95Ms:latency.length?percentile(latency,.95):null,maxMs:latency.length?Math.max(...latency):null,transactionsPerSecond:Number(output.match(/tps = ([\d.]+)/)?.[1]||0),scope:'Concurrent database sessions inside one network-isolated two-CPU container; excludes HTTP, browser and images.'});snapshot();console.error(JSON.stringify({clients,completed:latency.length,failure}));if(failure)break;
  }
  complete=true;const report=snapshot();if(!report.success)process.exitCode=1;
  console.log(JSON.stringify({success:report.success,activeSyntheticRows:dataset.active_unsold,cases:results.map(r=>({name:r.name,p95Ms:r.p95Ms})),concurrency,report:destination}));
 }finally{if(started&&!keepContainer)docker(['rm','-f',taskContainer],undefined,10000);}
}
main().catch(error=>{console.error(error.stderr?.toString()||error.message);process.exitCode=1;});
