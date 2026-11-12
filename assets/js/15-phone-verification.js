/* Optional phone verification. Email login and recovery keep their own flows. */
(function(){
'use strict';
let panel,phoneForm,otpForm,status,phoneInput,otpInput,sendButton,resendButton,verifyButton;
let owner=null,epoch=0,controller=null,loaded=false,provider=false,verifiedPhone='',pendingPhone='',busy=false,cooldownUntil=0,timer=null;
const stale=()=>Object.assign(new Error('Hesab dəyişib. Yenidən daxil ol.'),{name:'AbortError'});
function normalize(value){
 let number=String(value||'').trim().replace(/[\s()-]/g,'');
 if(/^0\d{9}$/.test(number))number='+994'+number.slice(1);
 else if(/^994\d{9}$/.test(number))number='+'+number;
 else if(/^\d{9}$/.test(number))number='+994'+number;
 return /^\+994\d{9}$/.test(number)?number:null;
}
function current(expected,sequence){return Boolean(expected&&currentUser?.id===expected&&owner===expected&&epoch===sequence);}
function tell(text,error=false){status.textContent=text;status.setAttribute('role',error?'alert':'status');}
function ensurePanel(){
 if(panel)return true;
 const cabinet=document.getElementById('cabinetPage');if(!cabinet)return false;
 panel=document.createElement('section');panel.id='caPhoneVerification';panel.className='ca-phone-verification';panel.hidden=true;
 panel.setAttribute('aria-labelledby','caPhoneVerificationTitle');
 panel.innerHTML='<h3 id="caPhoneVerificationTitle">Telefon nömrəsinin təsdiqi</h3><p id="caPhoneVerificationStatus" role="status" aria-live="polite"></p><form id="caPhoneForm" class="ca-phone-form"><label for="caPhoneNumber">Telefon nömrəsi</label><input id="caPhoneNumber" type="tel" inputmode="tel" autocomplete="tel" maxlength="24" placeholder="+994 70 123 45 67" required><button id="caPhoneSend" type="submit">SMS kodu göndər</button></form><form id="caPhoneOtpForm" class="ca-phone-form" hidden><label id="caPhoneOtpLabel" for="caPhoneOtp">SMS kodu</label><input id="caPhoneOtp" type="text" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" placeholder="6 rəqəmli kod" required><button id="caPhoneVerify" type="submit">Kodu təsdiqlə</button><button id="caPhoneResend" type="button">Yenidən göndər</button></form><p class="ca-phone-help">Kodunu heç kimlə paylaşma. E-poçtla giriş və parol bərpası əvvəlki kimi işləyir.</p>';
 const before=cabinet.querySelector('.cabinet-stats')||cabinet.firstChild;cabinet.insertBefore(panel,before);
 phoneForm=panel.querySelector('#caPhoneForm');otpForm=panel.querySelector('#caPhoneOtpForm');status=panel.querySelector('#caPhoneVerificationStatus');
 phoneInput=panel.querySelector('#caPhoneNumber');otpInput=panel.querySelector('#caPhoneOtp');sendButton=panel.querySelector('#caPhoneSend');resendButton=panel.querySelector('#caPhoneResend');verifyButton=panel.querySelector('#caPhoneVerify');
 phoneForm.addEventListener('submit',event=>{event.preventDefault();send(false);});
 otpForm.addEventListener('submit',event=>{event.preventDefault();verify();});
 resendButton.addEventListener('click',()=>send(true));
 return true;
}
function controls(){
 if(!panel)return;
 const seconds=Math.max(0,Math.ceil((cooldownUntil-Date.now())/1000)),enabled=loaded&&provider&&Boolean(owner);
 phoneForm.hidden=!enabled;otpForm.hidden=!enabled||!pendingPhone;
 phoneInput.disabled=busy;sendButton.disabled=!enabled||busy||seconds>0;
 verifyButton.disabled=!enabled||busy||!pendingPhone;otpInput.disabled=busy;
 resendButton.disabled=!enabled||busy||!pendingPhone||seconds>0;
 resendButton.textContent=seconds?'Yenidən göndər ('+seconds+' san.)':'Yenidən göndər';
 sendButton.textContent=seconds?'Yeni kod üçün '+seconds+' san. gözlə':'SMS kodu göndər';
}
function cooldown(seconds=60){
 cooldownUntil=Date.now()+Math.max(60,Math.min(3600,Number(seconds)||60))*1000;
 clearInterval(timer);timer=setInterval(()=>{controls();if(Date.now()>=cooldownUntil){clearInterval(timer);timer=null;}},1000);controls();
}
async function request(path,method,body,token,signal){
 const response=await fetch(CA_URL+path,{method,signal,cache:'no-store',headers:{apikey:CA_KEY,'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:body===null?undefined:JSON.stringify(body)});
 const raw=await response.text();let data;try{data=raw?JSON.parse(raw):null;}catch(error){data=null;}
 if(!response.ok){
  const error=new Error(data?.msg||data?.error_description||data?.message||'Sorğu tamamlanmadı. Yenidən yoxla.');error.status=response.status;
  const retry=response.headers.get('retry-after');error.retryAfter=retry&&/^\d+$/.test(retry)?Number(retry):60;throw error;
 }
 return data;
}
function trustedPhone(user,expected){
 const phone=normalize(user?.phone);
 return user?.id===expected&&phone&&Number.isFinite(Date.parse(user.phone_confirmed_at||''))?phone:'';
}
async function load(){
 if(!owner||loaded||busy||!document.body.classList.contains('cabinet-open'))return;
 const expected=owner,sequence=epoch;controller?.abort();controller=new AbortController();const signal=controller.signal;busy=true;tell('Telefonun təsdiq vəziyyəti yoxlanılır…');controls();
 try{
  const token=await caToken();if(!token||!current(expected,sequence))throw stale();
  const [settings,user]=await Promise.all([request('/auth/v1/settings','GET',null,null,signal),request('/auth/v1/user','GET',null,token,signal)]);
  if(!current(expected,sequence))return;
  if(user?.id!==expected)throw Error('Hesabın təsdiq vəziyyəti alınmadı. Yenidən daxil ol.');
  provider=settings?.external?.phone===true;verifiedPhone=trustedPhone(user,expected);loaded=true;
  phoneInput.value=verifiedPhone||currentUser.phone||'';
  tell(verifiedPhone?'✓ '+verifiedPhone+' nömrəsi SMS ilə təsdiqlənib.':provider?'Telefon nömrənə göndərilən kodla təsdiq et.':'SMS təsdiqi hazırda aktiv deyil. Hesabına e-poçt və parolla daxil ola bilərsən.');
 }catch(error){if(current(expected,sequence)&&error.name!=='AbortError'){tell(error.message,true);const button=document.createElement('button');button.type='button';button.textContent='Yenidən yoxla';button.addEventListener('click',load);status.append(' ',button);}}
 finally{if(current(expected,sequence)){busy=false;controls();}}
}
async function send(resend){
 if(!owner||!loaded||!provider||busy||Date.now()<cooldownUntil)return;
 const number=resend?pendingPhone:normalize(phoneInput.value);
 if(!number){tell('Nömrəni +994 və ya 0701234567 formasında düzgün yaz.',true);return;}
 if(number===verifiedPhone&&!pendingPhone){tell('Bu telefon nömrəsi artıq təsdiqlənib.');return;}
 const expected=owner,sequence=epoch;controller?.abort();controller=new AbortController();const signal=controller.signal;busy=true;controls();tell('SMS kodu göndərilir…');
 try{
  const token=await caToken();if(!token||!current(expected,sequence))throw stale();
  const response=await request('/auth/v1/user','PUT',{phone:number},token,signal);
  if(!current(expected,sequence))return;
  const user=response?.user||response;if(user?.id&&user.id!==expected)throw Error('Kod bu hesab üçün göndərilmədi. Yenidən daxil ol.');
  pendingPhone=number;otpInput.value='';panel.querySelector('#caPhoneOtpLabel').textContent=number+' üçün SMS kodu';cooldown();
  tell('SMS kodu '+number+' nömrəsinə göndərildi. Gələn 6 rəqəmli kodu yaz.');
  busy=false;controls();otpInput.focus({preventScroll:true});
 }catch(error){if(current(expected,sequence)&&error.name!=='AbortError'){if(error.status===429)cooldown(error.retryAfter);tell(error.status===429?'Çox tez sorğu göndərildi. Bir qədər gözlə və yenidən yoxla.':error.message,true);}}
 finally{if(current(expected,sequence)){busy=false;controls();}}
}
async function verify(){
 if(!owner||!provider||!pendingPhone||busy)return;
 const code=otpInput.value.trim();if(!/^\d{6}$/.test(code)){tell('SMS kodu 6 rəqəmdən ibarət olmalıdır.',true);return;}
 const expected=owner,sequence=epoch,number=pendingPhone;controller?.abort();controller=new AbortController();const signal=controller.signal;busy=true;controls();tell('SMS kodu yoxlanılır…');
 try{
  const token=await caToken();if(!token||!current(expected,sequence))throw stale();
  const result=await request('/auth/v1/verify','POST',{phone:number,token:code,type:'phone_change'},token,signal);
  if(!current(expected,sequence))return;
  if(result?.user?.id&&result.user.id!==expected)throw Error('Kod bu hesaba aid deyil. Yenidən daxil ol.');
  // Verify against the current logged-in account; never install verify's session.
  const user=await request('/auth/v1/user','GET',null,token,signal);
  if(!current(expected,sequence))return;
  if(trustedPhone(user,expected)!==number)throw Error('Nömrənin təsdiqi serverdə tamamlanmayıb. Kodu yenidən yoxla.');
  verifiedPhone=number;pendingPhone='';otpInput.value='';phoneInput.value=number;
  let updatedUser;
  try{
   const response=await request('/auth/v1/user','PUT',{data:{telefon:number}},token,signal);updatedUser=response?.user||response;
   if(!current(expected,sequence))return;
   if(trustedPhone(updatedUser,expected)!==number)throw Error('Hesab məlumatları yenilənmədi.');
   // UUID-scoped favorites stay with the account when its phone changes.
   await caPersistSession({...caSession,user:updatedUser});
   if(!current(expected,sequence))return;
   await caSaveProfile();
   if(!current(expected,sequence))return;
   tell('✓ '+number+' nömrəsi SMS ilə təsdiqləndi.');
  }catch(error){if(current(expected,sequence)&&error.name!=='AbortError')tell('✓ '+number+' nömrəsi təsdiqlənib. Əlaqə məlumatının yenilənməsi tamamlanmadı; dəstək xidməti ilə əlaqə saxla.',true);}
 }catch(error){if(current(expected,sequence)&&error.name!=='AbortError'){if(error.status===429)cooldown(error.retryAfter);tell(error.status===429?'Çox tez sorğu göndərildi. Bir qədər gözlə.':error.message,true);}}
 finally{if(current(expected,sequence)){busy=false;controls();}}
}
function sessionChanged(){
 if(!ensurePanel())return;
 const next=currentUser?.id||null;
 if(next!==owner){
  epoch++;controller?.abort();controller=null;owner=next;loaded=false;provider=false;verifiedPhone='';pendingPhone='';busy=false;cooldownUntil=0;clearInterval(timer);timer=null;
  phoneInput.value='';otpInput.value='';tell('');
 }
 panel.hidden=!owner;controls();if(owner&&document.body.classList.contains('cabinet-open'))load();
}
window.caPhoneVerificationSessionChanged=sessionChanged;
if(typeof MutationObserver==='function')new MutationObserver(sessionChanged).observe(document.body,{attributes:true,attributeFilter:['class']});
sessionChanged();
})();
