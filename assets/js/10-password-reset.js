// Standalone recovery. Credentials remain in memory and never replace a login.
(function(){
 'use strict';
 const API_URL='https://iqdtehqxusfiwokrzceo.supabase.co';
 const API_KEY='sb_publishable_i2YE7Nk-XcmmSQVi5-5_Tg_VAx1fSo7';
 const REDIRECT='https://dunumcebis-droid.github.io/cenub-avto/reset-password.html';
 const el=id=>document.getElementById(id);
 let epoch=0,recovery=null,state='request',requestBusy=false,resetBusy=false,closed=false;

 function message(text,error=false){
  el('resetMessage').textContent=text;
  el('resetMessage').setAttribute('role',error?'alert':'status');
 }
 function clearPasswords(){el('resetPassword').value='';el('resetPassword2').value='';}
 function forms(mode){
  state=mode;
  el('resetForm').hidden=mode!=='reset';
  el('recoveryRequestForm').hidden=mode!=='request';
  el('resetSuccess').hidden=mode!=='success';
  for(const id of ['resetPassword','resetPassword2','resetSubmit'])el(id).disabled=mode!=='reset';
  el('recoverySubmit').disabled=mode!=='request'||requestBusy;
  el('resetEmail').disabled=true;
 }
 function showRequest(text,error=false){
  recovery=null;resetBusy=false;clearPasswords();el('resetEmail').value='';
  forms('request');
  el('resetTitle').textContent='Parolun bərpası';
  el('resetIntro').textContent='Hesabının e-poçt ünvanını yaz və yeni bərpa linki istə.';
  message(text,error);
 }
 async function request(path,method='GET',body=null,token=null){
  const headers={'apikey':API_KEY,'Content-Type':'application/json'};
  if(token)headers.Authorization='Bearer '+token;
  const response=await fetch(API_URL+path,{method,headers,credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',body:body===null?undefined:JSON.stringify(body)});
  let data=null;try{data=await response.json();}catch(error){}
  if(!response.ok){const error=Error('Auth request failed');error.status=response.status;throw error;}
  return data;
 }
 function expiry(hash,query,verified){
  const now=Date.now();let end=now+3600000;
  const duration=verified?.expires_in??hash.get('expires_in')??query.get('expires_in');
  const absolute=verified?.expires_at??hash.get('expires_at')??query.get('expires_at');
  if(duration!==null&&duration!==undefined&&Number.isFinite(Number(duration)))end=Math.min(end,now+Math.max(0,Number(duration))*1000);
  if(absolute!==null&&absolute!==undefined&&Number.isFinite(Number(absolute)))end=Math.min(end,Number(absolute)*1000);
  return end;
 }
 window.caHandleAuthCallback=async function(){
  const callback=window.__caAuthCallback;delete window.__caAuthCallback;
  if(closed)return;
  if(!callback){
   if(!recovery&&state!=='success')showRequest('Yeni parol yaratmaq üçün bərpa məktubundakı linki aç və ya yeni link istə.');
   return;
  }
  const mine=++epoch;recovery=null;requestBusy=false;resetBusy=false;clearPasswords();
  const hash=new URLSearchParams(callback.hash),query=new URLSearchParams(callback.search);
  const typed=hash.get('type')==='recovery'||query.get('type')==='recovery'||hash.get('auth')==='recovery'||query.get('auth')==='recovery';
  if(!typed||hash.has('error')||query.has('error')){
   showRequest('Bərpa linki artıq istifadə olunub, etibarsızdır və ya vaxtı bitib. Yeni link istə.',true);return;
  }
  let token=hash.get('access_token')||query.get('access_token');
  const tokenHash=hash.get('token_hash')||query.get('token_hash');
  if(!token&&!tokenHash){showRequest('Bu bərpa linkində təsdiq məlumatı yoxdur. Yeni bərpa linki istə.',true);return;}
  const holder={user:null,token:null,expiresAt:0};recovery=holder;
  forms('checking');el('resetEmail').value='';
  el('resetTitle').textContent='Bərpa linki yoxlanılır';
  el('resetIntro').textContent='Hesab təsdiqləndikdən sonra yeni parol yarada biləcəksən.';message('');
  try{
   let verified=null;
   if(!token){
    verified=await request('/auth/v1/verify','POST',{type:'recovery',token_hash:tokenHash});
    if(closed||mine!==epoch||recovery!==holder)return;
    token=verified?.access_token;
   }
   if(!token)throw Error('Missing verified credential');
   const user=await request('/auth/v1/user','GET',null,token);
   if(closed||mine!==epoch||recovery!==holder)return;
   if(!user||typeof user.id!=='string'||!user.email)throw Error('Invalid verified user');
   holder.expiresAt=expiry(hash,query,verified);
   if(holder.expiresAt<=Date.now())throw Error('Expired credential');
   holder.user={id:user.id,email:user.email};holder.token=token;
   forms('reset');el('resetEmail').value=user.email;
   el('resetTitle').textContent='Yeni parol yarat';
   el('resetIntro').textContent='Yeni parolunu iki dəfə yaz və yadda saxla.';
   el('resetSubmit').textContent='Yeni parolu yadda saxla';message('');
   el('resetPassword').focus({preventScroll:true});
  }catch(error){
   if(!closed&&mine===epoch&&recovery===holder)showRequest('Bərpa linki artıq istifadə olunub, etibarsızdır və ya vaxtı bitib. Yeni link istə.',true);
  }
 };
 el('recoveryRequestForm').addEventListener('submit',async event=>{
  event.preventDefault();
  if(closed||state!=='request'||requestBusy)return;
  const email=el('recoveryEmail').value.trim().toLowerCase();
  if(!email||!el('recoveryEmail').checkValidity()){message('E-poçt ünvanını düzgün yaz.',true);return;}
  const mine=epoch;requestBusy=true;el('recoverySubmit').disabled=true;message('Bərpa linki göndərilir...');
  try{
   await request('/auth/v1/recover?redirect_to='+encodeURIComponent(REDIRECT),'POST',{email});
   if(!closed&&mine===epoch&&state==='request')message('Bu ünvan üçün bərpa mümkündürsə, link e-poçtuna göndərildi. Spam qovluğunu da yoxla.');
  }catch(error){
   if(!closed&&mine===epoch&&state==='request')message(error.status===429?'Çox sayda sorğu göndərilib. Bir az sonra yenidən yoxla.':'Məktubu göndərmək mümkün olmadı. Bir az sonra yenidən yoxla.',true);
  }finally{
   if(!closed&&mine===epoch&&state==='request'){requestBusy=false;el('recoverySubmit').disabled=false;}
  }
 });
 el('resetForm').addEventListener('submit',async event=>{
  event.preventDefault();
  if(closed||state!=='reset'||resetBusy||!recovery?.user||!recovery.token)return;
  const holder=recovery,mine=epoch,password=el('resetPassword').value;
  if(holder.expiresAt<=Date.now()){++epoch;showRequest('Linkin vaxtı bitib. Yeni bərpa linki istə.',true);return;}
  if(password.length<8){message('Parol ən azı 8 simvol olmalıdır.',true);return;}
  if(password!==el('resetPassword2').value){message('Parollar eyni deyil.',true);return;}
  resetBusy=true;el('resetSubmit').disabled=true;message('Yeni parol saxlanılır...');
  try{
   const user=await request('/auth/v1/user','PUT',{password},holder.token);
   if(closed||mine!==epoch||recovery!==holder)return;
   if(user?.id!==holder.user.id){++epoch;showRequest('Parol yenilənməsinin təsdiqi alınmadı. Hesabına girişini yoxla və lazım olsa yeni bərpa linki istə.',true);return;}
   recovery=null;resetBusy=false;clearPasswords();el('resetEmail').value='';
   forms('success');el('resetTitle').textContent='Parol yeniləndi';
   el('resetIntro').textContent='Yeni parolun saxlanıldı. Hesabına yeni parolunla daxil ola bilərsən.';
   message('Yeni parol uğurla saxlanıldı.');
   el('resetLogin').focus({preventScroll:true});
  }catch(error){
   if(closed||mine!==epoch||recovery!==holder)return;
   if(error.status===401||error.status===403){++epoch;showRequest('Linkin vaxtı bitib. Yeni bərpa linki istə.',true);}
   else message('Yeni parolu yadda saxlamaq mümkün olmadı. Bir az sonra yenidən yoxla.',true);
  }finally{
   if(!closed&&mine===epoch&&recovery===holder&&state==='reset'){resetBusy=false;el('resetSubmit').disabled=false;}
  }
 });
 window.addEventListener('pagehide',()=>{closed=true;++epoch;recovery=null;requestBusy=false;resetBusy=false;clearPasswords();el('resetEmail').value='';forms('checking');});
 window.addEventListener('pageshow',event=>{if(event.persisted){closed=false;++epoch;showRequest('Davam etmək üçün yeni bərpa linki istə.');}});
 window.caHandleAuthCallback();
})();
