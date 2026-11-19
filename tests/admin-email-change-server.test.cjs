'use strict';
// Auth and Admin API calls use injected fixtures; these tests cannot make real requests.
const test=require('node:test');
const assert=require('node:assert/strict');
const load=import('../supabase/functions/ca-admin-email-change/handler.mjs');
const BASE='https://email-fixture.supabase.co';
const USER='11111111-1111-4111-8111-111111111111';
const OTHER='22222222-2222-4222-8222-222222222222';
const TARGET='avtounvan@gmail.com';
const ORIGIN='https://dunumcebis-droid.github.io';
const ENV={SUPABASE_URL:BASE,SUPABASE_ANON_KEY:'fixture-anon-key',SUPABASE_SERVICE_ROLE_KEY:'fixture-service-key'};
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
async function fixture(options={}){
 const state={user:{id:USER,email:'owner@example.test',user_metadata:{role:'admin',id:OTHER}},admin:true,updated:{id:USER,email:TARGET},...options};
 const calls=[],envReads=[];
 const fetch=async(url,init={})=>{
  const call={url:String(url),method:init.method||'GET',headers:new Headers(init.headers),body:init.body,redirect:init.redirect};calls.push(call);
  if(call.url===BASE+'/auth/v1/user'){
   if(state.onAuth)await state.onAuth();
   if(state.authThrow)throw Error('fixture-private-auth-error');
   if(state.authInvalidJSON)return new Response('fixture-private-auth-detail');
   return response(state.user,state.authStatus||200);
  }
  if(call.url===BASE+'/rest/v1/rpc/cenub_admin_yoxla'){
   if(state.onAdmin)await state.onAdmin();
   if(state.adminThrow)throw Error('fixture-private-rpc-error');
   if(state.adminInvalidJSON)return new Response('fixture-private-rpc-detail');
   return response(state.admin,state.adminStatus||200);
  }
  if(call.url.startsWith(BASE+'/auth/v1/admin/users/')){
   if(state.updateThrow)throw Error('fixture-service-key fixture-private-update-error');
   if(state.updateInvalidJSON)return new Response('fixture-private-update-detail');
   return response(state.updated,state.updateStatus||200);
  }
  throw Error('Unexpected fixture URL: '+call.url);
 };
 const {createHandler}=await load;
 const handler=createHandler({env:name=>{envReads.push(name);return {...ENV,...state.env}[name];},fetch});
 const invoke=async({method='POST',headers={},body='{}',query=''}={})=>{
  const result=await handler(new Request(BASE+'/functions/v1/ca-admin-email-change'+query,{method,headers:{Authorization:'Bearer fixture-user-token',Origin:ORIGIN,'Content-Type':'application/json',...headers},body:['POST','PUT','PATCH'].includes(method)?body:undefined}));
  const raw=await result.text();return {status:result.status,headers:result.headers,data:raw?JSON.parse(raw):null,raw};
 };
 return {state,calls,envReads,handler,invoke};
}
const writes=calls=>calls.filter(call=>call.method==='PUT');
function noSecrets(result){assert.doesNotMatch(result.raw,/fixture-(?:service|anon)-key|fixture-user-token|fixture-private|owner@example\.test/);}

test('constructing the handler performs no environment access, calls or writes',async()=>{
 const f=await fixture();assert.deepEqual(f.calls,[]);assert.deepEqual(f.envReads,[]);
});
test('OPTIONS, unsupported methods, untrusted origins and absent bearer perform no calls',async()=>{
 for(const [request,status] of [[{method:'OPTIONS'},204],[{method:'GET'},405],[{method:'PUT'},405],[{headers:{Origin:'https://untrusted.invalid'}},403],[{headers:{Authorization:''}},401],[{headers:{Authorization:'Basic fixture-user-token'}},401]]){
  const f=await fixture();const result=await f.invoke(request);assert.equal(result.status,status);assert.deepEqual(f.calls,[]);assert.deepEqual(f.envReads,[]);noSecrets(result);
 }
 const f=await fixture();const preflight=await f.invoke({method:'OPTIONS'});
 assert.equal(preflight.headers.get('access-control-allow-origin'),ORIGIN);assert.equal(preflight.headers.get('access-control-allow-methods'),'POST,OPTIONS');
});
test('caller-supplied IDs, addresses, attributes, malformed JSON and oversized input are rejected before Auth',async()=>{
 const cases=[{body:JSON.stringify({user_id:OTHER})},{body:JSON.stringify({email:TARGET})},{body:JSON.stringify({user_metadata:{email:TARGET}})},{body:JSON.stringify({password:'fixture-password'})},{body:JSON.stringify({app_metadata:{admin:true}})},{body:'[]'},{body:'null'},{body:'true'},{body:'{'},{body:''},{body:' '.repeat(257)},{headers:{'Content-Length':'257'}},{headers:{'Content-Type':'text/plain'}},{query:'?user_id='+OTHER}];
 for(const request of cases){const f=await fixture();const result=await f.invoke(request);assert.equal(result.status,400);assert.deepEqual(f.calls,[]);assert.deepEqual(f.envReads,[]);noSecrets(result);}
});
test('missing server URL or anon configuration fails without any Auth or Admin call',async()=>{
 for(const env of [{SUPABASE_URL:''},{SUPABASE_URL:'http://unsafe.invalid'},{SUPABASE_ANON_KEY:''}]){
  const f=await fixture({env});const result=await f.invoke();assert.equal(result.status,503);assert.deepEqual(f.calls,[]);noSecrets(result);
 }
});
test('invalid or unavailable Auth never reaches admin check or privileged credentials',async()=>{
 const cases=[{authStatus:401},{authStatus:403},{authStatus:500},{authThrow:true},{authInvalidJSON:true},{user:{user_metadata:{id:USER}}},{user:{id:USER,email:null}},{user:{id:'../../another-user',email:'user@example.test'}}];
 for(const options of cases){const f=await fixture(options);const result=await f.invoke();assert.ok([401,503].includes(result.status));assert.equal(f.calls.length,1);assert.equal(writes(f.calls).length,0);assert.equal(f.envReads.includes('SUPABASE_SERVICE_ROLE_KEY'),false);noSecrets(result);}
});
test('editable admin metadata, false/malformed RPC, and RPC failures never authorize writes',async()=>{
 for(const options of [{admin:false},{admin:'true'},{admin:1},{admin:null},{admin:[true]},{admin:{admin:true}},{adminStatus:403},{adminStatus:500},{adminThrow:true},{adminInvalidJSON:true}]){
  const f=await fixture(options);const result=await f.invoke();assert.equal(result.status,options.admin===false?403:503);assert.equal(f.calls.length,2);assert.equal(writes(f.calls).length,0);assert.equal(f.envReads.includes('SUPABASE_SERVICE_ROLE_KEY'),false);noSecrets(result);
 }
});
test('both checks use the original user bearer; only then does the email-only own-user Admin write run',async()=>{
 const f=await fixture();const result=await f.invoke();
 assert.equal(result.status,200);assert.deepEqual(result.data,{status:'updated',user_id:USER,email:TARGET});
 assert.deepEqual(f.calls.map(call=>[call.method,call.url]),[['GET',BASE+'/auth/v1/user'],['POST',BASE+'/rest/v1/rpc/cenub_admin_yoxla'],['PUT',BASE+'/auth/v1/admin/users/'+USER]]);
 for(const call of f.calls.slice(0,2)){assert.equal(call.headers.get('authorization'),'Bearer fixture-user-token');assert.equal(call.headers.get('apikey'),ENV.SUPABASE_ANON_KEY);}
 assert.equal(f.calls[1].body,'{}');
 const write=writes(f.calls)[0];assert.equal(write.headers.get('authorization'),'Bearer '+ENV.SUPABASE_SERVICE_ROLE_KEY);assert.equal(write.headers.get('apikey'),ENV.SUPABASE_SERVICE_ROLE_KEY);assert.deepEqual(JSON.parse(write.body),{email:TARGET});
 assert.ok(f.calls.every(call=>call.redirect==='error'));assert.equal(result.headers.get('cache-control'),'no-store');assert.equal(result.headers.get('access-control-allow-origin'),ORIGIN);noSecrets(result);
});
test('neither unresolved Auth nor unresolved admin verification can reach privileged credentials or write',async()=>{
 const authGate=Promise.withResolvers(),adminGate=Promise.withResolvers();
 const f=await fixture({onAuth:()=>authGate.promise,onAdmin:()=>adminGate.promise});const pending=f.invoke();
 await new Promise(setImmediate);assert.equal(f.calls.length,1);assert.equal(writes(f.calls).length,0);assert.equal(f.envReads.includes('SUPABASE_SERVICE_ROLE_KEY'),false);
 authGate.resolve();await new Promise(setImmediate);assert.equal(f.calls.length,2);assert.equal(writes(f.calls).length,0);assert.equal(f.envReads.includes('SUPABASE_SERVICE_ROLE_KEY'),false);
 adminGate.resolve();assert.equal((await pending).status,200);assert.equal(writes(f.calls).length,1);
});
test('aborting a stalled request body cancels it before any Auth or privileged operation',async()=>{
 const f=await fixture(),controller=new AbortController();let cancelled=false;
 const body=new ReadableStream({start(stream){stream.enqueue(new TextEncoder().encode('{'));},cancel(){cancelled=true;}});
 const pending=f.handler(new Request(BASE+'/functions/v1/ca-admin-email-change',{method:'POST',headers:{Authorization:'Bearer fixture-user-token',Origin:ORIGIN,'Content-Type':'application/json'},body,duplex:'half',signal:controller.signal}));
 await new Promise(setImmediate);controller.abort();const result=await pending;
 assert.equal(result.status,400);assert.equal(cancelled,true);assert.deepEqual(f.calls,[]);assert.deepEqual(f.envReads,[]);
});
test('authenticated administrator already at the address succeeds without any Admin write',async()=>{
 const f=await fixture({user:{id:USER,email:TARGET.toUpperCase()}});const result=await f.invoke();
 assert.equal(result.status,200);assert.deepEqual(result.data,{status:'already_current',user_id:USER,email:TARGET});assert.equal(f.calls.length,2);assert.equal(writes(f.calls).length,0);assert.equal(f.envReads.includes('SUPABASE_SERVICE_ROLE_KEY'),false);
 const ordinary=await fixture({user:{id:USER,email:TARGET},admin:false});assert.equal((await ordinary.invoke()).status,403);assert.equal(writes(ordinary.calls).length,0);
});
test('an administrator using the former fixed address migrates to the current brand address without changing other attributes',async()=>{
 const f=await fixture({user:{id:USER,email:'former-admin@example.invalid',user_metadata:{role:'admin',id:OTHER},app_metadata:{provider:'email'}}});
 const result=await f.invoke();
 assert.equal(result.status,200);assert.deepEqual(result.data,{status:'updated',user_id:USER,email:TARGET});
 assert.equal(writes(f.calls).length,1);assert.equal(writes(f.calls)[0].url,BASE+'/auth/v1/admin/users/'+USER);
 assert.deepEqual(JSON.parse(writes(f.calls)[0].body),{email:'avtounvan@gmail.com'});
 assert.equal(f.state.user.email,'former-admin@example.invalid','The injected Auth fixture is never mutated by the handler');
 noSecrets(result);
});
test('stale metadata email is patched alone and a repeated clean request performs no additional Admin write',async()=>{
 const metadata={email:'former-admin@example.invalid',telefon:'+994000000000',preferences:{theme:'dark'},fixture:'preserve'};
 const user={id:USER,email:TARGET,user_metadata:metadata,app_metadata:{provider:'email',role:'preserve'},password:'fixture-unchanged-password'};
 const updated={...user,user_metadata:{...metadata,email:TARGET}};
 const f=await fixture({user,updated});const original=structuredClone(user);
 const result=await f.invoke();
 assert.equal(result.status,200);assert.deepEqual(result.data,{status:'updated',user_id:USER,email:TARGET,metadata_email_synced:true});
 assert.deepEqual(JSON.parse(writes(f.calls)[0].body),{user_metadata:{email:TARGET}});
 assert.equal(writes(f.calls)[0].url,BASE+'/auth/v1/admin/users/'+USER);
 assert.deepEqual(user,original,'No unrelated fixture metadata, app metadata or password is changed or sent');
 f.state.user=updated;
 const again=await f.invoke();
 assert.equal(again.status,200);assert.deepEqual(again.data,{status:'already_current',user_id:USER,email:TARGET,metadata_email_synced:true});
 assert.equal(writes(f.calls).length,1);assert.equal(f.envReads.filter(name=>name==='SUPABASE_SERVICE_ROLE_KEY').length,1);
 noSecrets(result);noSecrets(again);
});
test('an absent or non-string metadata email is never created or rewritten',async()=>{
 for(const metadata of [undefined,null,{},[],{fixture:'preserve'},{email:null},{email:123},{email:{fixture:'preserve'}}]){
  const user={id:USER,email:TARGET,...(metadata===undefined?{}:{user_metadata:metadata})};
  const original=structuredClone(user),f=await fixture({user});const result=await f.invoke();
  assert.equal(result.status,200);assert.deepEqual(result.data,{status:'already_current',user_id:USER,email:TARGET});
  assert.equal(writes(f.calls).length,0);assert.equal(f.envReads.includes('SUPABASE_SERVICE_ROLE_KEY'),false);assert.deepEqual(user,original);
 }
});
test('an unverified metadata repair response never claims success',async()=>{
 const user={id:USER,email:TARGET,user_metadata:{email:'former-admin@example.invalid',fixture:'preserve'}};
 for(const metadata of [undefined,null,{},[],{email:'former-admin@example.invalid'},{email:null},{email:123}]){
  const f=await fixture({user,updated:{id:USER,email:TARGET,...(metadata===undefined?{}:{user_metadata:metadata})}});
  const result=await f.invoke();assert.equal(result.status,503);assert.equal(result.data.status,undefined);assert.equal(result.data.metadata_email_synced,undefined);
  assert.deepEqual(JSON.parse(writes(f.calls)[0].body),{user_metadata:{email:TARGET}});noSecrets(result);
 }
});
test('missing privileged credentials fail after authorization without issuing a write',async()=>{
 const f=await fixture({env:{SUPABASE_SERVICE_ROLE_KEY:''}});const result=await f.invoke();assert.equal(result.status,503);assert.equal(f.calls.length,2);assert.equal(writes(f.calls).length,0);noSecrets(result);
});
test('email collisions and upstream failures return only safe errors',async()=>{
 for(const options of [{updateStatus:422,updated:{code:'email_exists',message:'fixture-private-email-detail'}},{updateStatus:409,updated:{message:'fixture-private-detail'}},{updateStatus:401},{updateStatus:500},{updateThrow:true},{updateInvalidJSON:true}]){
  const f=await fixture(options);const result=await f.invoke();assert.equal(result.status,options.updateStatus===409||options.updated?.code==='email_exists'?409:503);assert.equal(writes(f.calls).length,1);noSecrets(result);
 }
});
test('mismatched or malformed successful Admin responses never claim the change succeeded',async()=>{
 for(const updated of [null,{id:OTHER,email:TARGET},{id:USER,email:'unexpected@example.test'},{id:USER},{user:{id:USER,email:TARGET}}]){
  const f=await fixture({updated});const result=await f.invoke();assert.equal(result.status,503);assert.equal(result.data.status,undefined);noSecrets(result);
 }
});
