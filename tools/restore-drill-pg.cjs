'use strict';
// This process accepts a local directory only. It has no production connection
// string, Supabase client, HTTP implementation or restore-to-server command.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
process.umask(0o077);
const RESOURCES=['elanlar','paket_sorgulari','profiller','adminler','storage_objects','listing_stats','listing_events','listing_reports','saved_searches','approved_listing_events','notification_progress','search_notifications'];
const quote=value=>{assert.match(value,/^[A-Za-z_][A-Za-z0-9_]*$/);return '"'+value+'"';};
const qualified=t=>quote(t.schema)+'.'+quote(t.table);
const allowedTypes=/^(?:uuid|text(?:\[\])?|integer|bigint|smallint|boolean|jsonb|date|timestamp(?: with(?:out)? time zone)?|numeric(?:\(\d+(?:,\d+)?\))?)$/;
function identitySeedQuery(resource,table,column){
 const maximum='coalesce(max('+quote(column.name)+'),0)';
 const watermarks=resource==='approved_listing_events'?',coalesce((select max(cursor_seq) from ca_private.notification_progress),0),coalesce((select max(start_seq) from ca_private.saved_searches),0)':'';
 return 'select (greatest('+maximum+',0'+watermarks+')+1)::text next from '+qualified(table);
}
async function main(){
 const [dataPath,schemaPath,directory,modulePath]=process.argv.slice(2);
 assert(dataPath&&schemaPath&&directory&&modulePath,'Local paths are required');
 assert(!fs.existsSync(directory),'Local database directory must not already exist');
 assert.equal(require(path.join(modulePath,'package.json')).version,'0.5.16','Use the pinned PostgreSQL/WASM dependency');
 const {PGlite}=require(modulePath),capture=JSON.parse(fs.readFileSync(dataPath,'utf8')),schema=JSON.parse(fs.readFileSync(schemaPath,'utf8'));
 assert.deepEqual(capture.manifest.resources.map(r=>r.name),RESOURCES);
 const tables=new Map(schema.tables.map(t=>[t.resource,t]));assert.equal(tables.size,RESOURCES.length);
 assert(RESOURCES.every(r=>tables.has(r)),'Schema must describe every resource');
 const db=new PGlite(directory);let constraints=0,foreignKeys=0,identities=0;
 try{
  await db.exec("set timezone='UTC';set datestyle='ISO,YMD';set search_path=public;create schema auth;create schema storage;create schema ca_private;create table auth.users(id uuid primary key);create table storage.buckets(id text primary key);");
  for(const resource of RESOURCES){
   const table=tables.get(resource);assert(['public','ca_private','storage'].includes(table.schema));
   assert(Array.isArray(table.columns)&&table.columns.length>0);
   const columns=table.columns.map(column=>{
    assert.match(column.type,allowedTypes,'Unexpected column type');
    let definition=quote(column.name)+' '+column.type;
    if(column.generated){assert.equal(column.generated,'s');assert.equal(resource,'storage_objects');assert.equal(column.name,'path_tokens');assert.equal(column.default,"string_to_array(name, '/'::text)");definition+=' generated always as ('+column.default+') stored';}
    else if(column.identity){assert(['a','d'].includes(column.identity));definition+=' generated '+(column.identity==='a'?'always':'by default')+' as identity';}
    else if(column.default!==null&&column.default!==undefined){
     // Only defaults represented in the captured application schema; never run
     // arbitrary SQL embedded in an archive or accept a remote server target.
     assert(/^(?:gen_random_uuid\(\)|now\(\)|false|true|0|'(?:[^']|'')*'::(?:text|jsonb))$/.test(column.default),'Unexpected default expression');
     definition+=' default '+column.default;
    }
    if(column.not_null)definition+=' not null';return definition;
   });
   await db.exec('create table '+qualified(table)+'('+columns.join(',')+')');
   for(const constraint of table.constraints.filter(c=>c.type!=='f')){
    assert(['p','u','c'].includes(constraint.type),'Unexpected constraint kind');
    assert(!constraint.definition.includes(';')&&!/\b(?:select|copy|function|call|do|execute)\b/i.test(constraint.definition),'Unsafe constraint definition');
    await db.exec('alter table '+qualified(table)+' add constraint '+quote(constraint.name)+' '+constraint.definition);constraints++;
   }
  }
  const authIds=new Set(),bucketIds=new Set();
  for(const resource of RESOURCES){
   const table=tables.get(resource),rows=capture.rows[resource];assert(Array.isArray(rows));
   const allowed=new Set(table.columns.filter(c=>!c.generated).map(c=>c.name));
   for(const row of rows){assert(row&&typeof row==='object'&&!Array.isArray(row));assert(Object.keys(row).every(k=>allowed.has(k)),'Unknown archive column');}
   for(const constraint of table.constraints.filter(c=>c.type==='f')){
    const match=constraint.definition.match(/^FOREIGN KEY \(([a-z_]+)\) REFERENCES auth\.users\(id\)/);
    if(match)for(const row of rows)if(row[match[1]])authIds.add(row[match[1]]);
   }
   if(resource==='storage_objects')for(const row of rows)if(row.bucket_id)bucketIds.add(row.bucket_id);
  }
  for(const id of authIds)await db.query('insert into auth.users(id) values($1::uuid)',[id]);
  for(const id of bucketIds)await db.query('insert into storage.buckets(id) values($1)',[id]);
  for(const resource of RESOURCES){
   const table=tables.get(resource),rows=capture.rows[resource];
   if(!rows.length)continue;
   // Storage export is intentionally a projection; let absent Storage system
   // columns use their original defaults instead of importing fake values.
   const names=table.columns.filter(c=>!c.generated&&rows.some(r=>Object.hasOwn(r,c.name))).map(c=>c.name);
   const fields=names.map(quote).join(',');
   await db.query('insert into '+qualified(table)+'('+fields+') overriding system value select '+fields+' from jsonb_populate_recordset(null::'+qualified(table)+',$1::jsonb)',[JSON.stringify(rows)]);
  }
  for(const resource of RESOURCES){
   const table=tables.get(resource);
   for(const constraint of table.constraints.filter(c=>c.type==='f')){
    assert(/^FOREIGN KEY \([a-z_, ]+\) REFERENCES (?:auth\.users|storage\.buckets|(?:ca_private\.)?[a-z_]+)\([a-z_, ]+\)(?: ON DELETE (?:CASCADE|SET NULL|RESTRICT|NO ACTION))?$/.test(constraint.definition),'Unexpected foreign key shape');
    await db.exec('alter table '+qualified(table)+' add constraint '+quote(constraint.name)+' '+constraint.definition);constraints++;foreignKeys++;
   }
  }
  const migration=fs.readFileSync(path.join(__dirname,'../database/marketplace-backup.sql'),'utf8');
  const start=migration.indexOf('create or replace function ca_private.export_resource_sql('),end=migration.indexOf('\ncreate or replace function ca_private.admin_export_manifest()',start);
  assert(start>=0&&end>start);await db.exec(migration.slice(start,end));
  const resources=[];
  for(const expected of capture.manifest.resources){
   const fragment=(await db.query('select ca_private.export_resource_sql($1) sql',[expected.name])).rows[0].sql;
   const result=(await db.query("select count(*)::integer n,encode(sha256(convert_to(coalesce(string_agg(encode(sha256(convert_to(row_data::text,'UTF8')),'hex'),'' order by row_key),''),'UTF8')),'hex') fingerprint from ("+fragment+') source')).rows[0];
   assert.equal(result.n,expected.count,'Restored resource count mismatch: '+expected.name);
   assert.equal(result.fingerprint,expected.sha256,'Restored PostgreSQL row hash mismatch: '+expected.name);
   resources.push({name:expected.name,rows:result.n,sha256Matches:true});
  }
  for(const resource of RESOURCES){
   const table=tables.get(resource);
   for(const column of table.columns.filter(c=>c.identity)){
    const sequence=(await db.query('select pg_get_serial_sequence($1,$2) seq',[table.schema+'.'+table.table,column.name])).rows[0].seq;
    const next=(await db.query(identitySeedQuery(resource,table,column))).rows[0].next;
    await db.query('select setval($1::regclass,$2::bigint,false)',[sequence,next]);
    const probe=(await db.query('select nextval($1::regclass)::text value',[sequence])).rows[0].value;assert.equal(probe,next);
    await db.query('select setval($1::regclass,$2::bigint,false)',[sequence,next]);identities++;
   }
  }
  const version=(await db.query('show server_version')).rows[0].server_version;
  await db.exec('checkpoint');
  console.log(JSON.stringify({success:true,engine:'PGlite 0.5.16',postgresVersion:version,typedTablesRestored:RESOURCES.length,constraintsValidated:constraints,foreignKeysValidated:foreignKeys,identitySequencesReseeded:identities,placeholderAuthRows:authIds.size,resources,allPostgresRowHashesMatch:true}));
 }finally{await db.close();}
}
module.exports={identitySeedQuery};
if(require.main===module)main().catch(error=>{
 const folder=process.argv[4]&&path.dirname(process.argv[4]);
 if(folder&&fs.existsSync(folder)){try{fs.writeFileSync(path.join(folder,path.basename(process.argv[4])+'-private-error.json'),JSON.stringify({name:error.name,message:error.message,code:error.code,detail:error.detail}),{mode:0o600,flag:'wx'});}catch{}}
 console.error('Isolated PostgreSQL restore failed: '+error.name);process.exitCode=1;
});
