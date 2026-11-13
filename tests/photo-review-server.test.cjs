'use strict';
// Provider/Auth/Storage are injected fixtures; these tests cannot make real HTTP calls.
const test=require('node:test');
const assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const load=import('../supabase/functions/ca-photo-review/handler.mjs');
const BASE='https://photo-fixture.supabase.co';
const OWNER='11111111-1111-4111-8111-111111111111';
const REVIEW='33333333-3333-4333-8333-333333333333';
const PATH=OWNER+'/checked/'+REVIEW+'-ca-wm1.jpg';
const JPEG=Uint8Array.from([255,216,255,224,0,16,74,70,73,70,0,1,2,3,255,217]);
const ENV={SUPABASE_URL:BASE,SUPABASE_ANON_KEY:'fixture-anon-key',SUPABASE_SERVICE_ROLE_KEY:'fixture-service-key',PHOTO_REVIEW_PROVIDER:'gemini',PHOTO_REVIEW_MODEL:'fixture-model',GEMINI_API_KEY:'fixture-gemini-key'};
const VERDICT={is_vehicle_photo:true,contains_screen_ui:false,category:'front',confidence:.97};
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
async function fixture(options={}){
 const state={enabled:true,authStatus:200,authUser:{id:OWNER,user_metadata:{role:'admin',id:'wrong-metadata'}},verdict:{...VERDICT},...options};
 const calls=[];
 const fetch=async(url,init={})=>{
  const call={url:String(url),method:init.method||'GET',headers:new Headers(init.headers),body:init.body};calls.push(call);
  if(call.url===BASE+'/auth/v1/user')return response(state.authUser,state.authStatus);
  if(call.url===BASE+'/rest/v1/rpc/ca_photo_review_service_status')return response(state.statusBody??{enabled:state.enabled});
  if(call.url===BASE+'/rest/v1/rpc/ca_photo_review_reserve')return state.reserveError?response(state.reserveError,state.reserveStatus||400):response(state.reservation??REVIEW);
  if(call.url.startsWith('https://generativelanguage.googleapis.com/')){
   if(state.providerThrow)throw Error('fixture-secret-provider-error');
   if(state.providerStatus)return response({error:{message:'fixture-private-vendor-detail'}},state.providerStatus);
   return response(state.providerBody??{candidates:[{finishReason:'STOP',content:{parts:[{text:JSON.stringify(state.verdict)}]}}]});
  }
  if(call.url==='https://api.openai.com/v1/chat/completions'){
   if(state.providerStatus)return response({error:{message:'fixture-private-vendor-detail'}},state.providerStatus);
   return response(state.providerBody??{choices:[{finish_reason:'stop',message:{content:JSON.stringify(state.verdict)}}]});
  }
  if(call.url===BASE+'/storage/v1/object/elan-sekilleri/'+PATH&&call.method==='POST'){
   if(state.uploadThrow)throw Error('Synthetic upload response lost');
   return response(state.uploadStatus?{message:'fixture-private-storage-detail'}:{Key:PATH},state.uploadStatus||200);
  }
  if(call.url===BASE+'/rest/v1/rpc/ca_photo_review_complete')return response(state.completeError??(Object.hasOwn(state,'completeResult')?state.completeResult:true),state.completeError?503:200);
  if(call.url===BASE+'/storage/v1/object/elan-sekilleri'&&call.method==='DELETE')return response([{name:PATH}]);
  throw Error('Unexpected fixture URL: '+call.url);
 };
 const {createHandler}=await load;
 const handler=createHandler({env:{...ENV,...state.env},fetch,crypto:webcrypto});
 const invoke=async({category='front',bytes=JPEG,mime='image/jpeg',name='car.jpg',headers={},method='POST',status=false,form,body}={})=>{
  if(method==='POST'&&!form&&!body){form=new FormData();form.append('file',new File([bytes],name,{type:mime}));form.append('category',category);}
  const req=new Request(BASE+'/functions/v1/ca-photo-review'+(status?'/status':''),{method,headers:{Authorization:'Bearer fixture-user-token',Origin:'https://dunumcebis-droid.github.io',...headers},body:method==='POST'?(body??form):undefined});
  const result=await handler(req);const raw=await result.text();return {status:result.status,headers:result.headers,data:raw?JSON.parse(raw):null,raw};
 };
 return {state,calls,invoke,handler};
}
const providerCalls=calls=>calls.filter(c=>c.url.startsWith('https://generativelanguage.googleapis.com/')||c.url.startsWith('https://api.openai.com/'));
const uploadCalls=calls=>calls.filter(c=>c.method==='POST'&&c.url.includes('/storage/v1/object/'));
const proofCalls=calls=>calls.filter(c=>c.url.endsWith('/ca_photo_review_complete'));

test('status verifies Auth identity and reports disabled/configured without provider calls',async()=>{
 const f=await fixture({enabled:false});const r=await f.invoke({method:'GET',status:true});
 assert.equal(r.status,200);assert.deepEqual(r.data,{enabled:false,configured:true});assert.equal(providerCalls(f.calls).length,0);assert.equal(f.calls.length,2);
 assert.equal(f.calls[0].headers.get('authorization'),'Bearer fixture-user-token');assert.equal(f.calls[0].headers.get('apikey'),ENV.SUPABASE_ANON_KEY);
 assert.equal(f.calls[1].headers.get('authorization'),'Bearer '+ENV.SUPABASE_SERVICE_ROLE_KEY);
 assert.equal(r.headers.get('cache-control'),'no-store');assert.equal(r.headers.get('access-control-allow-origin'),'https://dunumcebis-droid.github.io');
});
test('missing/expired Auth and fake metadata never reach provider or storage',async()=>{
 for(const config of [{headers:{Authorization:''}},{options:{authStatus:401}},{options:{authUser:{user_metadata:{id:OWNER}}}}]){
  const f=await fixture(config.options);const r=await f.invoke(config);assert.equal(r.status,401);assert.equal(providerCalls(f.calls).length,0);assert.equal(uploadCalls(f.calls).length,0);
 }
});
test('wrong origin and unsupported methods are denied before Auth',async()=>{
 const f=await fixture();assert.equal((await f.invoke({headers:{Origin:'https://untrusted.invalid'}})).status,403);assert.equal((await f.invoke({method:'GET'})).status,405);assert.equal(f.calls.length,0);
 const preflight=await f.handler(new Request(BASE+'/functions/v1/ca-photo-review',{method:'OPTIONS',headers:{Origin:'https://dunumcebis-droid.github.io'}}));assert.equal(preflight.status,204);assert.equal(f.calls.length,0);
});
test('disabled or unconfigured mode fails closed for POST before reservation/provider',async()=>{
 for(const options of [{enabled:false},{env:{GEMINI_API_KEY:''}},{env:{PHOTO_REVIEW_MODEL:''}},{env:{PHOTO_REVIEW_PROVIDER:'unsupported'}}]){
  const f=await fixture(options);const r=await f.invoke();assert.equal(r.status,503);assert.equal(r.data.code,'provider_unavailable');assert.equal(f.calls.length,2);assert.equal(providerCalls(f.calls).length,0);
 }
});
test('status exposes unconfigured state without leaking keys',async()=>{
 const f=await fixture({env:{PHOTO_REVIEW_MODEL:''}});const r=await f.invoke({method:'GET',status:true});assert.deepEqual(r.data,{enabled:true,configured:false});assert.doesNotMatch(r.raw,/fixture-(?:service|gemini|anon)-key/);
});
test('unknown malformed service status fails closed',async()=>{
 const f=await fixture({statusBody:{enabled:'true'}});const r=await f.invoke();assert.equal(r.status,503);assert.equal(providerCalls(f.calls).length,0);
});
test('invalid categories, spoofed JPEG, wrong MIME, duplicate fields and oversized body are rejected before reservation',async()=>{
 const duplicate=new FormData();duplicate.append('file',new File([JPEG],'car.jpg',{type:'image/jpeg'}));duplicate.append('category','front');duplicate.append('category','rear');
 const unexpected=new FormData();unexpected.append('file',new File([JPEG],'car.jpg',{type:'image/jpeg'}));unexpected.append('category','front');unexpected.append('url','https://127.0.0.1/private');
 for(const request of [{category:'Front'},{bytes:new TextEncoder().encode('not an image')},{mime:'image/png'},{form:duplicate},{form:unexpected},{headers:{'Content-Length':String(6*1024*1024)}}]){
  const f=await fixture();const r=await f.invoke(request);assert.ok([400,413].includes(r.status));assert.equal(f.calls.length,2);assert.equal(providerCalls(f.calls).length,0);
 }
});
test('chunked oversized requests are bounded without trusting Content-Length',async()=>{
 const {MAX_IMAGE_BYTES}=await load;const f=await fixture();const r=await f.invoke({body:new Uint8Array(MAX_IMAGE_BYTES+64*1024+1),headers:{'Content-Type':'multipart/form-data; boundary=oversized'}});assert.equal(r.status,413);assert.equal(f.calls.length,2);
});
test('rate limit reservation is atomic gate before provider and returns Retry-After',async()=>{
 const f=await fixture({reserveError:{code:'P0001',message:'CA_PHOTO_REVIEW_RATE_LIMIT'}});const r=await f.invoke();assert.equal(r.status,429);assert.equal(r.headers.get('retry-after'),'60');assert.equal(providerCalls(f.calls).length,0);assert.equal(uploadCalls(f.calls).length,0);
});
test('screenshots, nonvehicle, wrong view and uncertainty return distinct warnings with no stored approval',async()=>{
 const cases=[{verdict:{...VERDICT,contains_screen_ui:true},code:'screenshot'},{verdict:{...VERDICT,is_vehicle_photo:false,category:'not_vehicle'},code:'not_vehicle'},{verdict:{...VERDICT,category:'rear'},code:'category_mismatch'},{verdict:{...VERDICT,category:'uncertain'},code:'uncertain'},{verdict:{...VERDICT,confidence:.849},code:'uncertain'}];
 for(const item of cases){const f=await fixture(item);const r=await f.invoke();assert.equal(r.status,422);assert.equal(r.data.code,item.code);assert.equal(uploadCalls(f.calls).length,0);assert.equal(proofCalls(f.calls).length,0);assert.equal(providerCalls(f.calls).length,1);}
});
test('all six categories require matching high confidence visual classification',async()=>{
 for(const category of ['front','rear','side','interior','engine','other']){
  const f=await fixture({verdict:{...VERDICT,category}});const r=await f.invoke({category});assert.equal(r.status,200);assert.equal(r.data.category,category);assert.equal(proofCalls(f.calls).length,1);
 }
});
test('strict schema rejects extra keys, wrong types, NaN-like strings and unknown categories',async()=>{
 const invalid=[{...VERDICT,extra:'ignored?'},{...VERDICT,confidence:'0.99'},{...VERDICT,confidence:1.01},{...VERDICT,category:'back'},{...VERDICT,is_vehicle_photo:'true'},null];
 for(const verdict of invalid){const f=await fixture({verdict});const r=await f.invoke();assert.equal(r.status,503);assert.equal(uploadCalls(f.calls).length,0);assert.equal(proofCalls(f.calls).length,0);}
});
test('provider errors, refusals, truncated and non-JSON responses cannot approve bytes or leak raw provider details',async()=>{
 const cases=[{providerStatus:429},{providerThrow:true},{providerBody:{candidates:[{finishReason:'MAX_TOKENS',content:{parts:[{text:JSON.stringify(VERDICT)}]}}]}},{providerBody:{candidates:[{finishReason:'STOP',content:{parts:[{text:'not JSON'}]}}]}},{env:{PHOTO_REVIEW_PROVIDER:'openai',OPENAI_API_KEY:'fixture-openai-key'},providerBody:{choices:[{finish_reason:'stop',message:{refusal:'private refusal'}}]}}];
 for(const options of cases){const f=await fixture(options);const r=await f.invoke();assert.equal(r.status,503);assert.equal(uploadCalls(f.calls).length,0);assert.equal(proofCalls(f.calls).length,0);assert.doesNotMatch(r.raw,/fixture-private|private refusal|fixture-secret/);}
});
test('approved bytes are stored immutably in server-derived owner/reservation namespace then bound to SHA and category',async()=>{
 const f=await fixture();const r=await f.invoke({name:'screenshot_claim_but_pixels_are_reviewed.jpg'});assert.equal(r.status,200);
 assert.deepEqual(r.data,{url:BASE+'/storage/v1/object/public/elan-sekilleri/'+PATH,review_id:REVIEW,category:'front'});
 const upload=uploadCalls(f.calls)[0];assert.equal(upload.headers.get('x-upsert'),'false');assert.equal(upload.headers.get('authorization'),'Bearer '+ENV.SUPABASE_SERVICE_ROLE_KEY);assert.deepEqual(new Uint8Array(upload.body),JPEG);
 const proof=JSON.parse(proofCalls(f.calls)[0].body);assert.equal(proof.p_owner,OWNER);assert.equal(proof.p_review_id,REVIEW);assert.equal(proof.p_path,PATH);assert.equal(proof.p_category,'front');assert.deepEqual(proof.p_verdict,VERDICT);
 const expected=Buffer.from(await webcrypto.subtle.digest('SHA-256',JPEG)).toString('hex');assert.equal(proof.p_sha256,expected);
 assert.ok(f.calls.findIndex(c=>c.url.endsWith('/ca_photo_review_reserve'))<f.calls.findIndex(c=>c.url.startsWith('https://generativelanguage')));assert.ok(f.calls.indexOf(upload)<f.calls.indexOf(proofCalls(f.calls)[0]));
 const provider=providerCalls(f.calls)[0];assert.equal(provider.headers.get('x-goog-api-key'),ENV.GEMINI_API_KEY);const body=JSON.parse(provider.body);assert.equal(body.contents[0].parts[1].inlineData.data,Buffer.from(JPEG).toString('base64'));assert.match(body.systemInstruction.parts[0].text,/untrusted/);assert.doesNotMatch(r.raw,/fixture-(?:service|gemini|anon)-key/);
});
test('OpenAI provider uses strict structured schema and approved images follow same trusted path',async()=>{
 const f=await fixture({env:{PHOTO_REVIEW_PROVIDER:'openai',OPENAI_API_KEY:'fixture-openai-key'}});const r=await f.invoke();assert.equal(r.status,200);const provider=providerCalls(f.calls)[0];assert.equal(provider.url,'https://api.openai.com/v1/chat/completions');assert.equal(provider.headers.get('authorization'),'Bearer fixture-openai-key');const body=JSON.parse(provider.body);assert.equal(body.messages[1].content[1].image_url.detail,'high');assert.equal(body.response_format.json_schema.strict,true);assert.equal(body.response_format.json_schema.schema.additionalProperties,false);assert.equal(proofCalls(f.calls).length,1);
});
test('failed proof creation deletes only this newly uploaded object and never returns URL',async()=>{
 const f=await fixture({completeError:{message:'fixture-private-proof-detail'}});const r=await f.invoke();assert.equal(r.status,503);assert.equal(r.data.url,undefined);const deleted=f.calls.filter(c=>c.method==='DELETE');assert.equal(deleted.length,1);assert.deepEqual(JSON.parse(deleted[0].body),{prefixes:[PATH]});assert.doesNotMatch(r.raw,/fixture-private/);
});
test('false proof response is rejected and cleaned rather than returning an unbound URL',async()=>{
 const f=await fixture({completeResult:false});const r=await f.invoke();assert.equal(r.status,503);assert.equal(r.data.url,undefined);assert.equal(f.calls.filter(c=>c.method==='DELETE').length,1);
});
test('failed upload response never creates a DB proof or approved URL',async()=>{
 const f=await fixture({uploadStatus:503});const r=await f.invoke();assert.equal(r.status,503);assert.equal(proofCalls(f.calls).length,0);assert.equal(r.data.url,undefined);assert.equal(f.calls.filter(c=>c.method==='DELETE').length,1);
});
