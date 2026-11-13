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
const statusValue=(enabled,configured)=>({enabled,configured,batch_supported:true,batch_max:6});
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
async function fixture(options={}){
 const state={enabled:true,authStatus:200,authUser:{id:OWNER,user_metadata:{role:'admin',id:'wrong-metadata'}},verdict:{...VERDICT},...options};
 const calls=[];let reserveIndex=0;
 const fetch=async(url,init={})=>{
  const call={url:String(url),method:init.method||'GET',headers:new Headers(init.headers),body:init.body};calls.push(call);
  if(call.url===BASE+'/auth/v1/user')return response(state.authUser,state.authStatus);
  if(call.url===BASE+'/rest/v1/rpc/ca_photo_review_service_status')return response(state.statusBody??{enabled:state.enabled});
  if(call.url===BASE+'/rest/v1/rpc/cenub_admin_yoxla')return response(Object.hasOwn(state,'adminResult')?state.adminResult:false,state.adminStatus||200);
  if(call.url===BASE+'/rest/v1/rpc/ca_photo_review_reserve'){const index=reserveIndex++;if(state.onReserve)await state.onReserve(index);return state.reserveError?response(state.reserveError,state.reserveStatus||400):response(state.reservations?.[index]??state.reservation??(state.batch?'33333333-3333-4333-8333-'+String(index+1).padStart(12,'0'):REVIEW));}
  if(call.url.startsWith('https://generativelanguage.googleapis.com/')){
   if(state.providerWait){await new Promise((resolve,reject)=>{const timer=setTimeout(resolve,state.providerWait);init.signal.addEventListener('abort',()=>{clearTimeout(timer);state.providerAborted=true;reject(new DOMException('Aborted','AbortError'));},{once:true});});}
   if(state.providerThrow)throw Error('fixture-secret-provider-error');
   if(state.providerStatus)return response({error:{message:'fixture-private-vendor-detail'}},state.providerStatus);
   return response(state.providerBody??{candidates:[{finishReason:'STOP',content:{parts:[{text:JSON.stringify(state.batch?{reviews:state.batchVerdicts??(state.batchCategories??['front','rear','side','interior','engine','other']).map((category,input_index)=>({...VERDICT,category,input_index}))}:state.verdict)}]}}]});
  }
  if(call.url==='https://api.openai.com/v1/chat/completions'){
   if(state.providerStatus)return response({error:{message:'fixture-private-vendor-detail'}},state.providerStatus);
   return response(state.providerBody??{choices:[{finish_reason:'stop',message:{content:JSON.stringify(state.verdict)}}]});
  }
  if(call.url.startsWith(BASE+'/storage/v1/object/elan-sekilleri/'+OWNER+'/checked/')&&call.method==='POST'){
   if(state.onUpload)await state.onUpload();
   if(state.uploadThrow)throw Error('Synthetic upload response lost');
   const id=call.url.split('/').at(-1).replace('-ca-wm1.jpg','');const status=state.failUploadId===id?503:state.uploadStatus;return response(status?{message:'fixture-private-storage-detail'}:{Key:call.url},status||200);
  }
  if(call.url===BASE+'/rest/v1/rpc/ca_photo_review_complete'){const data=JSON.parse(call.body);const error=state.failProofId===data.p_review_id?{message:'fixture-private-proof-detail'}:state.completeError;return response(error??(Object.hasOwn(state,'completeResult')?state.completeResult:true),error?503:200);}
  if(call.url===BASE+'/storage/v1/object/elan-sekilleri'&&call.method==='DELETE')return response([{name:PATH}]);
  throw Error('Unexpected fixture URL: '+call.url);
 };
 const {createHandler}=await load;
 const handler=createHandler({env:{...ENV,...state.env},fetch,crypto:webcrypto,timeouts:state.timeouts});
 const invoke=async({category='front',bytes=JPEG,mime='image/jpeg',name='car.jpg',headers={},method='POST',status=false,batch=false,form,body,categories=state.batchCategories??['front','rear','side','interior','engine','other']}={})=>{
  if(method==='POST'&&!form&&!body){form=new FormData();if(batch){form.append('categories',JSON.stringify(categories));categories.forEach((_,index)=>form.append('file_'+index,new File([bytes],name,{type:mime})));}else{form.append('file',new File([bytes],name,{type:mime}));form.append('category',category);}}
  const req=new Request(BASE+'/functions/v1/ca-photo-review'+(status?'/status':batch?'/batch':''),{method,headers:{Authorization:'Bearer fixture-user-token',Origin:'https://dunumcebis-droid.github.io',...headers},body:method==='POST'?(body??form):undefined});
  const result=await handler(req);const raw=await result.text();return {status:result.status,headers:result.headers,data:raw?JSON.parse(raw):null,raw};
 };
 return {state,calls,invoke,handler};
}
const providerCalls=calls=>calls.filter(c=>c.url.startsWith('https://generativelanguage.googleapis.com/')||c.url.startsWith('https://api.openai.com/'));
const uploadCalls=calls=>calls.filter(c=>c.method==='POST'&&c.url.includes('/storage/v1/object/'));
const proofCalls=calls=>calls.filter(c=>c.url.endsWith('/ca_photo_review_complete'));

test('status verifies Auth identity and reports disabled/configured without provider calls',async()=>{
 const f=await fixture({enabled:false});const r=await f.invoke({method:'GET',status:true});
 assert.equal(r.status,200);assert.deepEqual(r.data,statusValue(false,true));assert.equal(providerCalls(f.calls).length,0);assert.equal(f.calls.length,2);
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
 for(const options of [{enabled:false},{env:{GEMINI_API_KEY:''}},{env:{PHOTO_REVIEW_MODEL:'invalid model'}},{env:{PHOTO_REVIEW_PROVIDER:'unsupported'}}]){
  const f=await fixture(options);const r=await f.invoke();assert.equal(r.status,503);assert.equal(r.data.code,'provider_unavailable');assert.equal(f.calls.length,2);assert.equal(providerCalls(f.calls).length,0);
 }
});
test('status exposes unconfigured state without leaking keys',async()=>{
 const f=await fixture({env:{GEMINI_API_KEY:''}});const r=await f.invoke({method:'GET',status:true});assert.deepEqual(r.data,statusValue(true,false));assert.doesNotMatch(r.raw,/fixture-(?:service|gemini|anon)-key/);
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
 const cases=[{providerStatus:500},{providerThrow:true},{providerBody:{candidates:[{finishReason:'MAX_TOKENS',content:{parts:[{text:JSON.stringify(VERDICT)}]}}]}},{providerBody:{candidates:[{finishReason:'STOP',content:{parts:[{text:'not JSON'}]}}]}},{env:{PHOTO_REVIEW_PROVIDER:'openai',OPENAI_API_KEY:'fixture-openai-key'},providerBody:{choices:[{finish_reason:'stop',message:{refusal:'private refusal'}}]}}];
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

// The preview cohort uses existing admin authorization, never a special endpoint.
test('Gemini defaults to the current stable model and omits deprecated sampling parameters',async()=>{
 for(const model of [undefined,'']){
  const f=await fixture({env:{PHOTO_REVIEW_MODEL:model}});const r=await f.invoke();assert.equal(r.status,200);
  const provider=providerCalls(f.calls)[0],body=JSON.parse(provider.body);
  assert.equal(provider.url,'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent');
  assert.equal(body.generationConfig.maxOutputTokens,1024);assert.equal(body.generationConfig.responseMimeType,'application/json');
  assert.equal(Object.hasOwn(body.generationConfig,'temperature'),false);assert.equal(Object.hasOwn(body.generationConfig,'thinkingConfig'),false);
 }
});
test('OpenAI remains unconfigured without an explicit model or key',async()=>{
 for(const env of [{PHOTO_REVIEW_MODEL:'',OPENAI_API_KEY:'fixture-openai-key'},{PHOTO_REVIEW_MODEL:'fixture-model',OPENAI_API_KEY:''}]){
  const f=await fixture({env:{...env,PHOTO_REVIEW_PROVIDER:'openai'}});const r=await f.invoke({method:'GET',status:true});
  assert.equal(r.status,200);assert.deepEqual(r.data,statusValue(true,false));assert.equal(providerCalls(f.calls).length,0);
 }
});
test('admin preview uses only the confirmed user bearer and anon key for existing admin RPC',async()=>{
 const f=await fixture({statusBody:{enabled:false,admin_preview:true},adminResult:true});
 const status=await f.invoke({method:'GET',status:true});assert.deepEqual(status.data,statusValue(true,true));
 const check=f.calls.find(c=>c.url.endsWith('/cenub_admin_yoxla'));assert.ok(check);
 assert.equal(check.headers.get('authorization'),'Bearer fixture-user-token');assert.equal(check.headers.get('apikey'),ENV.SUPABASE_ANON_KEY);assert.equal(check.body,'{}');
 assert.notEqual(check.headers.get('authorization'),'Bearer '+ENV.SUPABASE_SERVICE_ROLE_KEY);
 assert.equal(providerCalls(f.calls).length,0);assert.equal((await f.invoke()).status,200);
});
test('admin preview never enables ordinary users despite editable admin metadata',async()=>{
 const f=await fixture({statusBody:{enabled:false,admin_preview:true},adminResult:false});
 assert.deepEqual((await f.invoke({method:'GET',status:true})).data,statusValue(false,true));
 const r=await f.invoke();assert.equal(r.status,503);assert.equal(providerCalls(f.calls).length,0);
 assert.equal(f.calls.filter(c=>c.url.endsWith('/ca_photo_review_reserve')).length,0);
});
test('malformed or failed admin preview authorization fails closed without provider requests',async()=>{
 for(const config of [{adminResult:'true'},{adminResult:{admin:true}},{adminResult:[true]},{adminStatus:403},{adminStatus:500},{statusBody:{enabled:false,admin_preview:'true'},adminResult:true}]){
  const f=await fixture({statusBody:{enabled:false,admin_preview:true},...config});
  const r=await f.invoke({method:'GET',status:true});assert.equal(r.status,503);assert.equal(r.data.enabled,undefined);assert.equal(providerCalls(f.calls).length,0);
 }
});
test('admin authorization is not queried when preview is off or globally enabled',async()=>{
 for(const statusBody of [{enabled:false,admin_preview:false},{enabled:false},{enabled:true,admin_preview:true}]){
  const f=await fixture({statusBody});const r=await f.invoke({method:'GET',status:true});assert.equal(r.status,200);
  assert.equal(f.calls.some(c=>c.url.endsWith('/cenub_admin_yoxla')),false);
 }
});
test('provider quota and denied access return safe distinct codes without revealing upstream content',async()=>{
 for(const [providerStatus,status,code] of [[429,429,'provider_quota'],[401,503,'provider_denied'],[403,503,'provider_denied']]){
  const f=await fixture({providerStatus});const r=await f.invoke();assert.equal(r.status,status);assert.equal(r.data.code,code);
  assert.equal(uploadCalls(f.calls).length,0);assert.equal(proofCalls(f.calls).length,0);
  assert.doesNotMatch(r.raw,/fixture-private|fixture-secret|fixture-(?:service|gemini|anon)-key/);
  if(providerStatus===429)assert.equal(r.headers.get('retry-after'),'60');
 }
});

const BATCH_CATEGORIES=['front','rear','side','interior','engine','other'];
function batchForm(categories,images=categories.map(()=>JPEG)){
 const form=new FormData();form.append('categories',JSON.stringify(categories));
 images.forEach((bytes,index)=>form.append('file_'+index,new File([bytes],'photo-'+index+'.jpg',{type:'image/jpeg'})));
 return form;
}
const reservationId=index=>'33333333-3333-4333-8333-'+String(index+1).padStart(12,'0');

test('six separate photos use one provider call and preserve their own index, category, bytes, hash and immutable proof',async()=>{
 const images=BATCH_CATEGORIES.map((_,index)=>Uint8Array.from([...JPEG.slice(0,-2),index,255,217]));
 const batchVerdicts=BATCH_CATEGORIES.map((category,input_index)=>({...VERDICT,category,input_index})).reverse();
 const f=await fixture({batch:true,batchVerdicts});
 const r=await f.invoke({batch:true,form:batchForm(BATCH_CATEGORIES,images)});
 assert.equal(r.status,200);assert.equal(r.data.results.length,6);assert.equal(providerCalls(f.calls).length,1);
 assert.equal(f.calls.filter(c=>c.url.endsWith('/ca_photo_review_reserve')).length,6);assert.equal(uploadCalls(f.calls).length,6);assert.equal(proofCalls(f.calls).length,6);
 const body=JSON.parse(providerCalls(f.calls)[0].body),parts=body.contents[0].parts;
 assert.equal(parts.length,12);assert.match(body.systemInstruction.parts[0].text,/independently/);assert.equal(body.generationConfig.maxOutputTokens,2048);
 for(let index=0;index<6;index++){
  const result=r.data.results[index],expectedPath=OWNER+'/checked/'+reservationId(index)+'-ca-wm1.jpg';
  assert.deepEqual(result,{index,ok:true,url:BASE+'/storage/v1/object/public/elan-sekilleri/'+expectedPath,review_id:reservationId(index),category:BATCH_CATEGORIES[index]});
  assert.match(parts[index*2].text,new RegExp('input_index '+index+'$'));
  assert.equal(parts[index*2+1].inlineData.data,Buffer.from(images[index]).toString('base64'));
  const upload=uploadCalls(f.calls).find(c=>c.url.endsWith(expectedPath));assert.deepEqual(new Uint8Array(upload.body),images[index]);assert.equal(upload.headers.get('x-upsert'),'false');
  const proof=proofCalls(f.calls).map(c=>JSON.parse(c.body)).find(p=>p.p_review_id===reservationId(index));
  assert.equal(proof.p_owner,OWNER);assert.equal(proof.p_category,BATCH_CATEGORIES[index]);assert.equal(proof.p_path,expectedPath);
  assert.deepEqual(proof.p_verdict,{...VERDICT,category:BATCH_CATEGORIES[index]});
  assert.equal(proof.p_sha256,Buffer.from(await webcrypto.subtle.digest('SHA-256',images[index])).toString('hex'));
 }
});
test('mixed batch independently rejects unsafe photos while keeping correctly approved siblings',async()=>{
 const batchVerdicts=BATCH_CATEGORIES.map((category,input_index)=>({...VERDICT,category,input_index}));
 batchVerdicts[1].contains_screen_ui=true;batchVerdicts[2].category='rear';batchVerdicts[3].confidence=.8;
 const f=await fixture({batch:true,batchVerdicts});const r=await f.invoke({batch:true});
 assert.equal(r.status,200);assert.deepEqual(r.data.results.map(item=>item.ok),[true,false,false,false,true,true]);
 assert.equal(r.data.results[1].code,'screenshot');assert.equal(r.data.results[2].code,'category_mismatch');assert.equal(r.data.results[3].code,'uncertain');
 assert.equal(providerCalls(f.calls).length,1);assert.equal(uploadCalls(f.calls).length,3);assert.equal(proofCalls(f.calls).length,3);
 for(const item of r.data.results.filter(item=>!item.ok)){assert.equal(item.url,undefined);assert.equal(item.review_id,undefined);}
});
test('every batch verdict and unique index must validate before any object or proof is written',async()=>{
 const valid=BATCH_CATEGORIES.map((category,input_index)=>({...VERDICT,category,input_index}));
 const invalid=[
  {reviews:valid.slice(1)},
  {reviews:[valid[0],valid[0],...valid.slice(2)]},
  {reviews:valid.map((item,index)=>index===0?{...item,input_index:6}:item)},
  {reviews:valid.map((item,index)=>index===0?{...item,input_index:.5}:item)},
  {reviews:valid.map((item,index)=>index===5?{...item,confidence:'0.99'}:item)},
  {reviews:valid.map((item,index)=>index===5?{...item,extra:'not allowed'}:item)},
  {reviews:valid,approved:true},
  valid,
  {reviews:valid.map(({input_index,...item},index)=>index===0?item:{input_index,...item})}
 ];
 for(const value of invalid){
  const f=await fixture({batch:true,providerBody:{candidates:[{finishReason:'STOP',content:{parts:[{text:JSON.stringify(value)}]}}]}});
  const r=await f.invoke({batch:true});assert.equal(r.status,503);assert.equal(uploadCalls(f.calls).length,0);assert.equal(proofCalls(f.calls).length,0);
 }
});
test('batch rejects duplicate reservation IDs before asking the provider',async()=>{
 const f=await fixture({batch:true,reservation:REVIEW});const r=await f.invoke({batch:true});
 assert.equal(r.status,503);assert.equal(providerCalls(f.calls).length,0);assert.equal(uploadCalls(f.calls).length,0);
});
test('batch multipart requires one category per exact file field and caps six images',async()=>{
 const duplicate=batchForm(['front']);duplicate.append('file_0',new File([JPEG],'duplicate.jpg',{type:'image/jpeg'}));
 const extra=batchForm(['front']);extra.append('url','https://127.0.0.1/private');
 const missing=new FormData();missing.append('categories','["front"]');
 const malformed=batchForm(['front']);malformed.set('categories','not JSON');
 const multipleCategories=batchForm(['front']);multipleCategories.append('categories','["rear"]');
 for(const form of [batchForm([]),batchForm(Array(7).fill('front')),batchForm(['wrong']),duplicate,extra,missing,malformed,multipleCategories]){
  const f=await fixture({batch:true});const r=await f.invoke({batch:true,form});assert.equal(r.status,400);assert.equal(f.calls.length,2);assert.equal(providerCalls(f.calls).length,0);
 }
});
test('batch per-image type, magic and 5MiB limit are enforced independently of aggregate bounds',async()=>{
 for(const file of [new File(['not JPEG'],'image.jpg',{type:'image/jpeg'}),new File([JPEG],'image.png',{type:'image/png'}),new File([new Uint8Array(5*1024*1024+1)],'oversized.jpg',{type:'image/jpeg'})]){
  const form=batchForm(['front']);form.set('file_0',file);
  const f=await fixture({batch:true});const r=await f.invoke({batch:true,form});assert.equal(r.status,400);assert.equal(providerCalls(f.calls).length,0);
 }
});
test('batch streamed aggregate is bounded at 8MiB plus multipart allowance without trusting Content-Length',async()=>{
 const {MAX_BATCH_IMAGE_BYTES}=await load;
 const f=await fixture({batch:true});const r=await f.invoke({batch:true,body:new Uint8Array(MAX_BATCH_IMAGE_BYTES+64*1024+1),headers:{'Content-Type':'multipart/form-data; boundary=oversized'}});
 assert.equal(r.status,413);assert.equal(f.calls.length,2);assert.equal(providerCalls(f.calls).length,0);
 const declared=await f.invoke({batch:true,headers:{'Content-Length':String(9*1024*1024)}});assert.equal(declared.status,413);
});
test('batch Auth, configuration, cohort and quota gates run before any provider or storage access',async()=>{
 for(const config of [{headers:{Authorization:''},status:401},{options:{authStatus:401},status:401},{options:{enabled:false},status:503},{options:{statusBody:{enabled:false,admin_preview:true},adminResult:false},status:503},{options:{reserveError:{code:'P0001',message:'CA_PHOTO_REVIEW_RATE_LIMIT'}},status:429}]){
  const f=await fixture({batch:true,...config.options});const r=await f.invoke({batch:true,headers:config.headers});assert.equal(r.status,config.status);assert.equal(providerCalls(f.calls).length,0);assert.equal(uploadCalls(f.calls).length,0);
 }
});
test('batch storage or proof failure cleans only the failed reservation and preserves the other approvals',async()=>{
 for(const failure of [{failUploadId:reservationId(1)},{failProofId:reservationId(1)}]){
  const f=await fixture({batch:true,...failure});const r=await f.invoke({batch:true});assert.equal(r.status,200);
  assert.equal(r.data.results.filter(item=>item.ok).length,5);assert.equal(r.data.results[1].ok,false);assert.equal(r.data.results[1].url,undefined);assert.equal(r.data.results[1].code,'provider_unavailable');
  const deleted=f.calls.filter(c=>c.method==='DELETE');assert.equal(deleted.length,1);assert.deepEqual(JSON.parse(deleted[0].body),{prefixes:[OWNER+'/checked/'+reservationId(1)+'-ca-wm1.jpg']});
  assert.equal(proofCalls(f.calls).length,failure.failUploadId?5:6);
 }
});
test('batch reserve and storage workers are bounded to three and overlap rather than serializing six items',async()=>{
 let reserves=0,uploads=0,maxReserves=0,maxUploads=0;
 const f=await fixture({batch:true,onReserve:async()=>{reserves++;maxReserves=Math.max(reserves,maxReserves);await new Promise(resolve=>setTimeout(resolve,4));reserves--;},onUpload:async()=>{uploads++;maxUploads=Math.max(uploads,maxUploads);await new Promise(resolve=>setTimeout(resolve,4));uploads--;}});
 const r=await f.invoke({batch:true});assert.equal(r.status,200);assert.equal(maxReserves,3);assert.equal(maxUploads,3);assert.equal(reserves,0);assert.equal(uploads,0);
});
test('short injected single/batch provider deadlines abort stalled requests before any upload',async()=>{
 for(const batch of [false,true]){
  const f=await fixture({batch,providerWait:1000,timeouts:{single:15,batch:15,request:1000}});
  const r=await f.invoke({batch});assert.equal(r.status,503);assert.equal(r.data.code,'provider_unavailable');assert.equal(f.state.providerAborted,true);assert.equal(uploadCalls(f.calls).length,0);assert.equal(proofCalls(f.calls).length,0);
 }
});
test('batch provider quota and access errors retain safe codes and never return unchecked URLs',async()=>{
 for(const [providerStatus,status,code] of [[429,429,'provider_quota'],[403,503,'provider_denied'],[500,503,'provider_unavailable']]){
  const f=await fixture({batch:true,providerStatus});const r=await f.invoke({batch:true});assert.equal(r.status,status);assert.equal(r.data.code,code);assert.equal(uploadCalls(f.calls).length,0);assert.doesNotMatch(r.raw,/fixture-private|fixture-(?:service|gemini)-key/);
 }
});
test('OpenAI batch keeps every image separate and uses an exact indexed structured result schema',async()=>{
 const reviews=BATCH_CATEGORIES.map((category,input_index)=>({...VERDICT,category,input_index}));
 const f=await fixture({batch:true,env:{PHOTO_REVIEW_PROVIDER:'openai',OPENAI_API_KEY:'fixture-openai-key'},providerBody:{choices:[{finish_reason:'stop',message:{content:JSON.stringify({reviews})}}]}});
 const r=await f.invoke({batch:true});assert.equal(r.status,200);assert.equal(r.data.results.filter(item=>item.ok).length,6);
 const body=JSON.parse(providerCalls(f.calls)[0].body);assert.equal(body.messages[1].content.length,12);assert.equal(body.response_format.json_schema.strict,true);assert.equal(body.response_format.json_schema.schema.properties.reviews.minItems,6);
 assert.equal(body.messages[1].content.filter(part=>part.type==='image_url').length,6);assert.ok(body.messages[1].content.filter(part=>part.type==='image_url').every(part=>part.image_url.detail==='high'));
});
test('multipart allowance cannot be used to exceed the actual aggregate image-byte cap',async()=>{
 const bytes=new Uint8Array(4*1024*1024+128);bytes.set(JPEG.subarray(0,4));
 const f=await fixture({batch:true,batchCategories:['front','rear']});
 const r=await f.invoke({batch:true,form:batchForm(['front','rear'],[bytes,bytes])});
 assert.equal(r.status,413);assert.equal(providerCalls(f.calls).length,0);assert.equal(uploadCalls(f.calls).length,0);
});
test('a failed reservation drains in-flight siblings without starting another batch item or provider call',async()=>{
 let active=0;
 const f=await fixture({batch:true,onReserve:async index=>{active++;await new Promise(resolve=>setTimeout(resolve,index===1?1:8));active--;if(index===1)throw Error('Synthetic failed reservation');}});
 const r=await f.invoke({batch:true});assert.equal(r.status,503);assert.equal(active,0);
 assert.equal(f.calls.filter(c=>c.url.endsWith('/ca_photo_review_reserve')).length,3);assert.equal(providerCalls(f.calls).length,0);assert.equal(uploadCalls(f.calls).length,0);
});

test('single and batch review instructions allow damaged vehicles without bypassing view and screenshot checks',async()=>{
 for(const batch of [false,true]){
  const f=await fixture({batch,batchCategories:['front']});const r=await f.invoke({batch,categories:['front']});assert.equal(r.status,200);
  const prompt=JSON.parse(providerCalls(f.calls)[0].body).systemInstruction.parts[0].text;
  assert.match(prompt,/Damage alone must never cause rejection/);assert.match(prompt,/intact headlights, grille, bumper or body panels are not required/);assert.match(prompt,/visible screenshot interfaces/);
 }
});
