// Browser-only Supabase recovery uses the documented implicit email flow.
// A recovery token is verified against Auth and held only in memory; it never
// replaces an existing account session or enters localStorage.
let caAuthEpoch=0,caRecovery=null;
const CA_RECOVERY_REDIRECT='https://dunumcebis-droid.github.io/cenub-avto/';
function caAuthMessage(message,error=false){const el=document.getElementById('authMessage');el.textContent=message;el.setAttribute('role',error?'alert':'status');}
function openAuth(mode='register'){
 if(!['register','login','recover','reset'].includes(mode))mode='login';
 if(mode==='reset'&&!caRecovery)mode='recover';
 caAuthEpoch++;if(mode!=='reset')caRecovery=null;authMode=mode;
 const register=mode==='register',recover=mode==='recover',reset=mode==='reset';
 const field=id=>document.getElementById(id);
 field('authOverlay').classList.add('open');caAuthMessage('');
 field('authTitle').textContent=register?'Qeydiyyat':recover?'Parolun bərpası':reset?'Yeni parol yarat':'Şəxsi kabinetə giriş';
 field('authIntro').textContent=register?'Telefon, e-poçt və parolla qeydiyyat. SMS tələb olunmur.':recover?'Hesabının e-poçt ünvanını yaz. Bərpa linkini həmin ünvana göndərmək üçün sorğu yaradılacaq.':reset?(caRecovery.user?'Parolunu dəyişəcəyin hesab: '+caRecovery.user.email:'Bərpa linki yoxlanılır...'):'E-poçt və parolla daxil ol.';
 for(const [id,show] of [['authPhone',register],['authPassword',!recover],['authPassword2',register||reset]]){
  field(id).style.display=show?'block':'none';field(id).required=show;field(id).disabled=!show||(reset&&!caRecovery.user);
 }
 field('authPassword').value='';field('authPassword2').value='';
 field('authPassword').autocomplete=register||reset?'new-password':'current-password';
 field('authEmail').disabled=reset;field('authEmail').required=!reset;
 if(reset)field('authEmail').value=caRecovery.user?.email||'';
 field('authSubmit').disabled=reset&&!caRecovery.user;
 field('authSubmit').textContent=register?'Qeydiyyatdan keç':recover?'Bərpa linki göndər':reset?'Yeni parolu yadda saxla':'Daxil ol';
 field('authModeSwitch').textContent=register?'Artıq hesabım var — daxil ol':mode==='login'?'Yeni hesab yarat':'Girişə qayıt';
 field('authForgot').hidden=mode!=='login';
}
function closeAuth(){caAuthEpoch++;caRecovery=null;document.getElementById('authOverlay').classList.remove('open');document.getElementById('authPassword').value='';document.getElementById('authPassword2').value='';}
function toggleAuthMode(){openAuth(authMode==='login'?'register':'login');}
async function caAfterLogin(owner=currentUser?.id){
 try{await caSaveProfile();}catch(error){console.warn('Profil saxlanmadı; giriş davam edir.');}
 if(currentUser?.id!==owner)return;
 closeAuth();updateAccountUI();
 if(pendingAction==='sell'){pendingAction='';openSellPage();}
 else if(pendingAction==='cabinet'){pendingAction='';openCabinet();}
 else if(pendingAction.startsWith('favorite:')){const key=pendingAction.slice(9);pendingAction='';toggleFavorite(key,null);}
 else{pendingAction='';alert('Hesabına uğurla daxil oldun.');}
}
async function caHandleAuthCallback(){
 const callback=window.__caAuthCallback;delete window.__caAuthCallback;if(!callback)return;
 const hash=new URLSearchParams(callback.hash),query=new URLSearchParams(callback.search);
 const recovery=hash.get('type')==='recovery'||query.get('type')==='recovery'||query.get('auth')==='recovery'||hash.get('auth')==='recovery';
 if(!recovery&&!hash.has('error')&&!query.has('error'))return;
 if(hash.has('error')||query.has('error')||!recovery){openAuth('recover');caAuthMessage('Bərpa linki artıq istifadə olunub, etibarsızdır və ya vaxtı bitib. Yeni link istə.',true);return;}
 if(!hash.get('access_token')&&!query.get('access_token')&&!query.get('token_hash')&&!hash.get('token_hash')){openAuth('recover');caAuthMessage('Bu bərpa linkində təsdiq məlumatı yoxdur. Yeni bərpa linki istə.',true);return;}
 const holder={user:null,token:null,expiresAt:0};caRecovery=holder;openAuth('reset');const epoch=caAuthEpoch;
 try{
  let token=hash.get('access_token')||query.get('access_token');
  if(!token&&(query.get('token_hash')||hash.get('token_hash'))){const r=await caRequest('/auth/v1/verify','POST',{type:'recovery',token_hash:query.get('token_hash')||hash.get('token_hash')});token=r?.access_token;}
  if(!token)throw Error('Missing recovery token');
  const user=await caRequest('/auth/v1/user','GET',null,token);
  if(epoch!==caAuthEpoch||caRecovery!==holder)return;
  if(!user||typeof user.id!=='string'||!user.email)throw Error('Invalid verified user');
  holder.user=user;holder.token=token;holder.expiresAt=Date.now()+Math.min(3600,Math.max(1,Number(hash.get('expires_in'))||3600))*1000;
  openAuth('reset');
 }catch(error){if(epoch===caAuthEpoch&&caRecovery===holder){openAuth('recover');caAuthMessage('Bərpa linki etibarsızdır və ya vaxtı bitib. Yeni link istə.',true);}}
}
document.getElementById('authForm').addEventListener('submit',async event=>{
 event.preventDefault();
 const epoch=caAuthEpoch,mode=authMode,owner=currentUser?.id||null,session=caSession,recovery=caRecovery;
 const field=id=>document.getElementById(id),btn=field('authSubmit');
 const email=field('authEmail').value.trim().toLowerCase(),phone=normalizePhone(field('authPhone').value),password=field('authPassword').value;
 const active=()=>epoch===caAuthEpoch&&mode===authMode&&(currentUser?.id||null)===owner;
 if(btn.disabled)return;
 caAuthMessage('');
 if(mode!=='recover'&&password.length<8){caAuthMessage('Parol ən azı 8 simvol olmalıdır.',true);return;}
 if((mode==='register'||mode==='reset')&&password!==field('authPassword2').value){caAuthMessage('Parollar eyni deyil.',true);return;}
 if(mode==='register'&&phone.replace(/\D/g,'').length<9){caAuthMessage('Telefon nömrəsini düzgün daxil et.',true);return;}
 btn.disabled=true;
 try{
  if(mode==='recover'){
   await caRequest('/auth/v1/recover?redirect_to='+encodeURIComponent(CA_RECOVERY_REDIRECT),'POST',{email});
   if(active())caAuthMessage('Bu ünvan üçün bərpa mümkündürsə, link e-poçtuna göndərildi. Spam qovluğunu da yoxla.');
  }else if(mode==='reset'){
   if(!recovery?.user||!recovery.token||recovery.expiresAt<=Date.now())throw Error('Linkin vaxtı bitib. Yeni bərpa linki istə.');
   const user=await caRequest('/auth/v1/user','PUT',{password},recovery.token);
   if(!active()||caRecovery!==recovery)return;
   if(user?.id!==recovery.user.id)throw Error('Hesab təsdiqi alınmadı. Yeni bərpa linki istə.');
   if(currentUser?.id===user.id&&caSession===session){
    caDismissListingFeedback(false);caClearListingDraft();caClearPrivateListings();localStorage.removeItem(CA_SESSION_KEY);caSession=null;currentUser=null;updateAccountUI();render();closeCabinet();closeSellPage();
   }
   openAuth('login');field('authEmail').value=recovery.user.email;caAuthMessage('Parol yeniləndi. Yeni parolunla daxil ol.');
  }else{
   const r=await caRequest(mode==='register'?'/auth/v1/signup':'/auth/v1/token?grant_type=password','POST',mode==='register'?{email,password,data:{telefon:phone}}:{email,password});
   if(!active()||caSession!==session)return;
   if(r?.access_token){await caPersistSession(r);await caAfterLogin(r.user.id);}
   else if(mode==='register'){openAuth('login');caAuthMessage('E-poçtuna gələn təsdiq linkinə toxun, sonra hesabına daxil ol.');}
   else throw Error('Giriş təsdiqi alınmadı.');
  }
 }catch(error){if(active())caAuthMessage((mode==='recover'?'Bərpa linki göndərilmədi: ':mode==='reset'?'Parol yenilənmədi: ':'Giriş / qeydiyyat alınmadı: ')+error.message,true);}
 finally{if(active())btn.disabled=false;}
});
caHandleAuthCallback();
