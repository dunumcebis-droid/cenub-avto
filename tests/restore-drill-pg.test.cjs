'use strict';
// Real isolated PostgreSQL queries. No HTTP, account API or production database.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {identitySeedQuery}=require('../tools/restore-drill-pg.cjs');
const candidates=[process.env.CA_PGLITE_MODULE,path.resolve(__dirname,'../tools/restore-drill/node_modules/@electric-sql/pglite'),'/tmp/ca-marketplace-backup-pg/node_modules/@electric-sql/pglite'].filter(Boolean);
const modulePath=candidates.find(p=>fs.existsSync(path.join(p,'package.json')));
const table={schema:'ca_private',table:'approved_listing_events'},column={name:'seq'};
async function fixture(){
 assert.equal(require(path.join(modulePath,'package.json')).version,'0.5.16');
 const {PGlite}=require(modulePath);const db=new PGlite();
 await db.exec('create schema ca_private;create table ca_private.approved_listing_events(seq bigint generated always as identity primary key);create table ca_private.notification_progress(cursor_seq bigint);create table ca_private.saved_searches(start_seq bigint);');
 return db;
}
async function next(db){return (await db.query(identitySeedQuery('approved_listing_events',table,column))).rows[0].next;}
const options={skip:!modulePath&&'Install tools/restore-drill test dependency or set CA_PGLITE_MODULE'};
test('restored empty approval queue starts above every retained notification/search watermark',options,async()=>{
 const db=await fixture();try{
  await db.exec('insert into ca_private.notification_progress values(250);insert into ca_private.saved_searches values(400);');
  const seed=await next(db);assert.equal(seed,'401');
  await db.query("select setval('ca_private.approved_listing_events_seq_seq',$1::bigint,false)",[seed]);
  assert.equal((await db.query('insert into ca_private.approved_listing_events default values returning seq::text')).rows[0].seq,'401');
 }finally{await db.close();}
});
test('restored populated queue keeps generated approvals above both rows and cursors',options,async()=>{
 const db=await fixture();try{
  await db.exec('insert into ca_private.approved_listing_events(seq) overriding system value values(700);insert into ca_private.notification_progress values(900);insert into ca_private.saved_searches values(800);');
  assert.equal(await next(db),'901');
  await db.exec('delete from ca_private.notification_progress;delete from ca_private.saved_searches;');
  assert.equal(await next(db),'701');
 }finally{await db.close();}
});
test('new empty application restore begins with approval identity one',options,async()=>{
 const db=await fixture();try{assert.equal(await next(db),'1');}finally{await db.close();}
});
test('maximum bigint watermark refuses a restore instead of wrapping or skipping notifications',options,async()=>{
 const db=await fixture();try{
  await db.exec("insert into ca_private.notification_progress values('9223372036854775807');");
  await assert.rejects(()=>next(db),error=>error.code==='22003');
 }finally{await db.close();}
});
