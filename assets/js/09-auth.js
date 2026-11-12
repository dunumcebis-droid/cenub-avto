// Browser-only Supabase recovery uses the documented implicit email flow.
// A recovery token is verified against Auth and held only in memory; it never
// replaces an existing account session or enters localStorage.
let caAuthEpoch=0,caRecovery=null;
let caAuthReturnFocus=null,caAuthPreviousOverflow='',caAuthOwnsScrollLock=false,caAuthPreviousModalLock=false;
const CA_RECOVERY_REDIRECT='https://dunumcebis-droid.github.io/cenub-avto/reset-password.html';
function caAuthMessage(message,error=false){const el=document.getElementById('authMessage');el.textContent=message;el.setAttribute('role',error?'alert':'status');}
function caAuthVisibleControl(element){return Boolean(element?.isConnected&&element.matches('a[href],button,input,select,textarea,[tabindex],[contenteditable="true"]')&&element.getClientRects().length&&!element.disabled&&!element.closest('[inert]'));}
function caAuthControls(container=document.getElementById('authOverlay')){
 return [...container.querySelectorAll('input:not(:disabled),button:not(:disabled),a[href],[tabindex="0"]')].filter(caAuthVisibleControl);
}
function caAuthFocusFirst(){
 const controls=caAuthControls(),input=controls.find(element=>element.tagName==='INPUT');
 (input||controls[0]||document.getElementById('authOverlay')).focus({preventScroll:true});
}
function caAuthOtherScrollLock(){
 return ['detailOverlay','vehiclePicker','generationPicker','listingFeedback','caPhotoViewer'].some(id=>document.getElementById(id)?.classList.contains('open'));
}
function caAuthCloseCoveredViews(){
 if(window.caPhotoViewerIsOpen?.())window.caClosePhotoViewer({returnToDetail:false});
 if(document.getElementById('detailOverlay')?.classList.contains('open'))closeCarDetail();
 if(document.getElementById('vehiclePicker')?.classList.contains('open'))closeVehiclePicker();
 if(document.getElementById('generationPicker')?.classList.contains('open'))closeGenerationPicker();
 if(document.getElementById('caOverlay')?.classList.contains('ca-open'))window.caCloseDialog?.();
}
function openAuth(mode='register'){
 if(!['register','login','recover','reset'].includes(mode))mode='login';
 if(mode==='reset'&&!caRecovery)mode='recover';
 caAuthCloseCoveredViews();
 if(!caAuthOwnsScrollLock){
  caAuthReturnFocus=document.activeElement;caAuthPreviousOverflow=document.body.style.overflow;
  caAuthPreviousModalLock=caAuthOtherScrollLock();caAuthOwnsScrollLock=true;
 }
 document.body.style.overflow='hidden';
 caAuthEpoch++;if(mode!=='reset')caRecovery=null;authMode=mode;
 const register=mode==='register',recover=mode==='recover',reset=mode==='reset';
 const field=id=>document.getElementById(id);
 field('authOverlay').classList.add('open');field('authOverlay').setAttribute('aria-hidden','false');caAuthMessage('');
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
 field('authOverlay').scrollTop=0;field('authOverlay').querySelector('.auth-box').scrollTop=0;
 caAuthFocusFirst();
}
function closeAuth(){
 caAuthEpoch++;caRecovery=null;
 const overlay=document.getElementById('authOverlay');overlay.classList.remove('open');overlay.setAttribute('aria-hidden','true');
 document.getElementById('authPassword').value='';document.getElementById('authPassword2').value='';
 if(!caAuthOwnsScrollLock)return;
 document.body.style.overflow=caAuthOtherScrollLock()?'hidden':caAuthPreviousModalLock&&caAuthPreviousOverflow==='hidden'?'':caAuthPreviousOverflow;
 const remaining=['listingFeedback','detailOverlay','vehiclePicker','generationPicker','caOverlay','caAdminPanel'].map(id=>document.getElementById(id)).filter(element=>element&&getComputedStyle(element).display!=='none').sort((a,b)=>(parseInt(getComputedStyle(b).zIndex)||0)-(parseInt(getComputedStyle(a).zIndex)||0))[0];
 let target=caAuthVisibleControl(caAuthReturnFocus)?caAuthReturnFocus:null;
 if(remaining&&(!target||!remaining.contains(target)))target=caAuthControls(remaining)[0]||null;
 if(!target)target=document.querySelector('header .header-actions .back-btn');
 caAuthOwnsScrollLock=false;caAuthReturnFocus=null;caAuthPreviousOverflow='';caAuthPreviousModalLock=false;
 if(caAuthVisibleControl(target))target.focus({preventScroll:true});
}
document.addEventListener('keydown',event=>{
 const overlay=document.getElementById('authOverlay');
 if(!overlay.classList.contains('open')||event.isComposing||event.ctrlKey||event.altKey||event.metaKey)return;
 if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();closeAuth();return;}
 if(event.key!=='Tab')return;
 const controls=caAuthControls(),first=controls[0],last=controls.at(-1);
 if(!controls.length){event.preventDefault();return;}
 if(!overlay.contains(document.activeElement)||event.shiftKey&&document.activeElement===first||!event.shiftKey&&document.activeElement===last){event.preventDefault();(event.shiftKey?last:first).focus();}
 event.stopImmediatePropagation();
},true);
document.addEventListener('focusin',event=>{
 const overlay=document.getElementById('authOverlay');
 if(overlay.classList.contains('open')&&!overlay.contains(event.target))caAuthFocusFirst();
},true);
if(typeof MutationObserver==='function')new MutationObserver(()=>{
 if(caAuthOwnsScrollLock&&document.getElementById('authOverlay').classList.contains('open')&&document.body.style.overflow!=='hidden')document.body.style.overflow='hidden';
}).observe(document.body,{attributes:true,attributeFilter:['style']});
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
