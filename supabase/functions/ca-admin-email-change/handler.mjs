/** Changes only the authenticated administrator's own login to the approved address. */
const TARGET_EMAIL='azavto44@gmail.com';
const ALLOWED_ORIGIN='https://dunumcebis-droid.github.io';
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_BODY_BYTES=256;
const messages={
 origin_denied:'Bu ünvandan sorğu qəbul edilmir.',
 method_not_allowed:'Sorğu üsulu dəstəklənmir.',
 invalid_request:'Sorğu düzgün deyil.',
 auth_required:'Sessiya bitib. Hesabına yenidən daxil ol.',
 admin_required:'Bu əməliyyat üçün administrator girişi lazımdır.',
 email_unavailable:'Bu e-poçt ünvanı başqa hesabda istifadə olunur.',
 service_unavailable:'E-poçtu hazırda dəyişmək mümkün deyil. Bir qədər sonra yenidən yoxla.'
};
function json(value,status,headers){return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',...headers}});}
function configValue(env,name){const value=typeof env==='function'?env(name):env?.[name];return typeof value==='string'?value:'';}
async function emptyInput(req,signal){
 if(!/^application\/json(?:\s*;|\s*$)/i.test(req.headers.get('content-type')||''))return false;
 const declared=req.headers.get('content-length');
 if(declared&&(!/^\d+$/.test(declared)||Number(declared)>MAX_BODY_BYTES))return false;
 if(!req.body)return false;
 const reader=req.body.getReader(),chunks=[];let length=0;
 const abort=()=>{reader.cancel().catch(()=>{});};signal.addEventListener('abort',abort,{once:true});
 try{
  while(true){signal.throwIfAborted();const part=await reader.read();signal.throwIfAborted();if(part.done)break;length+=part.value.byteLength;if(length>MAX_BODY_BYTES){await reader.cancel();return false;}chunks.push(part.value);}
  const bytes=new Uint8Array(length);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
  const value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
  return value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).length===0;
 }catch{return false;}finally{signal.removeEventListener('abort',abort);reader.releaseLock();}
}
export function createHandler({env={},fetch:fetcher=globalThis.fetch}={}){
 return async function handler(req){
  const origin=req.headers.get('Origin');
  const cors={...(origin===ALLOWED_ORIGIN?{'Access-Control-Allow-Origin':origin}:{}),'Vary':'Origin','Access-Control-Allow-Headers':'authorization,apikey,content-type,x-client-info','Access-Control-Allow-Methods':'POST,OPTIONS','Access-Control-Max-Age':'600'};
  const fail=(status,code,headers={})=>json({code,message:messages[code]},status,{...cors,...headers});
  if(origin&&origin!==ALLOWED_ORIGIN)return fail(403,'origin_denied');
  if(req.method==='OPTIONS')return new Response(null,{status:204,headers:cors});
  if(req.method!=='POST')return fail(405,'method_not_allowed',{'Allow':'POST,OPTIONS'});
  const authorization=req.headers.get('Authorization')||'';
  if(!/^Bearer [A-Za-z0-9._~-]{8,8192}$/.test(authorization))return fail(401,'auth_required');
  const signal=AbortSignal.any([req.signal,AbortSignal.timeout(15000)]);
  // The caller cannot supply a user ID, replacement address, or any update attributes.
  if(new URL(req.url).search||!await emptyInput(req,signal))return fail(400,'invalid_request');
  const base=configValue(env,'SUPABASE_URL').replace(/\/$/,''),anon=configValue(env,'SUPABASE_ANON_KEY');
  if(!/^https:\/\/[A-Za-z0-9.-]+$/.test(base)||!anon)return fail(503,'service_unavailable');
  const userHeaders={'Authorization':authorization,'apikey':anon,'Content-Type':'application/json'};
  try{
   // Resolve the principal from Auth, never from caller input or editable metadata.
   const authResponse=await fetcher(base+'/auth/v1/user',{method:'GET',headers:userHeaders,signal,redirect:'error'});
   if(!authResponse.ok)return fail(authResponse.status===401||authResponse.status===403?401:503,authResponse.status===401||authResponse.status===403?'auth_required':'service_unavailable');
   const user=await authResponse.json();
   if(!UUID.test(user?.id||'')||typeof user.email!=='string'||!user.email)return fail(401,'auth_required');
   // This RPC runs with exactly that user's JWT; the service role cannot stand in for it.
   const adminResponse=await fetcher(base+'/rest/v1/rpc/cenub_admin_yoxla',{method:'POST',headers:userHeaders,body:'{}',signal,redirect:'error'});
   if(!adminResponse.ok)return fail(503,'service_unavailable');
   const admin=await adminResponse.json();
   if(admin===false)return fail(403,'admin_required');
   if(admin!==true)return fail(503,'service_unavailable');
   if(user.email.toLowerCase()===TARGET_EMAIL)return json({status:'already_current',user_id:user.id,email:TARGET_EMAIL},200,cors);
   // Privileged credentials and the write are reachable only after both checks succeed.
   const service=configValue(env,'SUPABASE_SERVICE_ROLE_KEY');
   if(!service)return fail(503,'service_unavailable');
   // Same endpoint and email-only payload used by auth.admin.updateUserById.
   const updatedResponse=await fetcher(base+'/auth/v1/admin/users/'+user.id,{method:'PUT',headers:{'Authorization':'Bearer '+service,'apikey':service,'Content-Type':'application/json'},body:JSON.stringify({email:TARGET_EMAIL}),signal,redirect:'error'});
   if(!updatedResponse.ok){
    let error;try{error=await updatedResponse.json();}catch{/* Never return upstream response text. */}
    return updatedResponse.status===409||error?.code==='email_exists'?fail(409,'email_unavailable'):fail(503,'service_unavailable');
   }
   const updated=await updatedResponse.json();
   if(updated?.id!==user.id||typeof updated.email!=='string'||updated.email.toLowerCase()!==TARGET_EMAIL)return fail(503,'service_unavailable');
   return json({status:'updated',user_id:user.id,email:TARGET_EMAIL},200,cors);
  }catch{return fail(503,'service_unavailable');}
 };
}
