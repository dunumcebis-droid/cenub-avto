(function(){
const el=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let owner=null,authorized=false,verifySequence=0,busy=false,sessionEpoch=0;
let previewSequence=0,previewActive=false;
const state=()=>({page:1,total:0,pages:0,rows:[],status:'all',query:'',sequence:0,loading:false,loaded:false,linked:null});
let ads=state(),payments=state();
function reset(){closePreview();sessionEpoch++;verifySequence++;owner=currentUser?.id||null;authorized=false;busy=false;ads.sequence++;payments.sequence++;ads=state();payments=state();el('caAdminLaunch').style.display='none';if(el('caBackupLaunch'))el('caBackupLaunch').style.display='none';el('caAdminPanel').style.display='none';for(const id of ['caAdminList','caPayList','caAdminMsg','caPayMsg','caAdminPager','caPayPager'])el(id).replaceChildren();if(el('caPayLinkedNotice')){el('caPayLinkedNotice').replaceChildren();el('caPayLinkedNotice').hidden=true;}el('caAdminSearch').value='';el('caPaySearch').value='';el('caPayFilter').value='all';el('caAdminActionMsg').textContent='';}
window.caAdminSessionChanged=()=>{if(owner!==(currentUser?.id||null))reset();};
async function rpc(name,body,expected=owner){
 const t=await caToken();
 if(!expected||currentUser?.id!==expected||owner!==expected||!t)throw Error('Hesab dəyişib və ya sessiya bitib. Yenidən daxil ol.');
 return caRequest('/rest/v1/rpc/'+name,'POST',body,t);
}
async function verify(){
 window.caAdminSessionChanged();if(!owner)return false;
 const expected=owner,seq=++verifySequence;
 try{const ok=await rpc('cenub_admin_yoxla',{},expected);if(seq!==verifySequence||owner!==expected||currentUser?.id!==expected)return false;authorized=ok===true;el('caAdminLaunch').style.display=authorized?'block':'none';if(el('caBackupLaunch'))el('caBackupLaunch').style.display=authorized?'block':'none';if(!authorized){closePreview();el('caAdminPanel').style.display='none';}return authorized;}
 catch(error){if(seq===verifySequence&&owner===expected){authorized=false;closePreview();el('caAdminLaunch').style.display='none';if(el('caBackupLaunch'))el('caBackupLaunch').style.display='none';el('caAdminPanel').style.display='none';}return false;}
}
// Preview records stay out of public listing collections and are discarded on close.
function closePreview(closeDetail=true){
 previewSequence++;
 if(el('caAdminActionMsg')?.textContent==='Elanın tam məlumatları yüklənir...')el('caAdminActionMsg').textContent='';
 const wasActive=previewActive;previewActive=false;
 if(closeDetail&&wasActive&&el('detailOverlay')?.dataset.adminPreview==='true')closeCarDetail();
}
window.caCloseAdminPreview=()=>closePreview();
window.caAdminPreviewClosed=()=>closePreview(false);
async function previewListing(button){
 if(!authorized||!owner||el('caAdminPanel').style.display==='none')return false;
 const id=button.dataset.previewId;
 if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id||'')||!ads.rows.some(row=>row.id===id))return false;
 const expected=owner,epoch=sessionEpoch,sequence=++previewSequence,listSequence=ads.sequence;
 button.disabled=true;el('caAdminActionMsg').textContent='Elanın tam məlumatları yüklənir...';
 try{
  const row=await rpc('ca_admin_listing_detail',{p_id:id},expected);
  if(sequence!==previewSequence||epoch!==sessionEpoch||expected!==owner||currentUser?.id!==expected||!authorized||listSequence!==ads.sequence||el('caAdminPanel').style.display==='none')return false;
  if(!row){el('caAdminActionMsg').textContent='Elan tapılmadı və ya artıq baxış üçün əlçatan deyil.';return false;}
  if(Array.isArray(row)||row.id!==id||typeof window.caOpenCarRecord!=='function')throw Error('Elanın tam məlumatları düzgün gəlmədi.');
  const car=caRemoteToCar(row);
  button.disabled=false;if(button.isConnected)button.focus({preventScroll:true});
  window.caOpenCarRecord(car,{adminPreview:true});
  previewActive=true;
  el('caAdminActionMsg').textContent='';return true;
 }catch(error){
  if(sequence===previewSequence&&epoch===sessionEpoch&&expected===owner&&currentUser?.id===expected){
   previewActive=false;el('caAdminActionMsg').textContent='Elan açılmadı: '+error.message;
  }
  return false;
 }finally{if(button.isConnected)button.disabled=false;}
}
function pager(s,id,handler){el(id).innerHTML=s.pages>1?`<div class="ca-actions"><button type="button" onclick="${handler}(-1)" ${s.loading||s.page<=1?'disabled':''}>← Əvvəlki</button><span>${s.page} / ${s.pages}</span><button type="button" onclick="${handler}(1)" ${s.loading||s.page>=s.pages?'disabled':''}>Növbəti →</button></div>`:'';}
function packageInfo(x){
 const names=['VIP','Premium','Standart','Pulsuz'];
 const requested=names.includes(x.requested_package)?x.requested_package:'Pulsuz';
 const approved=names.includes(x.approved_package)?x.approved_package:null;
 const status=['free','pending','confirmed','rejected','legacy_unrequested'].includes(x.package_status)?x.package_status:'unknown';
 const labels={free:'Pulsuz elan',pending:requested+' sorğusu · paket təsdiqi gözləyir',confirmed:requested+' sorğusu · paket təsdiqlənib',rejected:requested+' sorğusu · paket rədd edilib',legacy_unrequested:requested+' · sorğu tarixçəsi tapılmadı',unknown:'Paket məlumatı yüklənməyib'};
 const hints={pending:'Əvvəl aşağıdakı paket sorğusunu yoxlayıb təsdiqlə, sonra elanı ayrıca yayımla.',confirmed:x.veziyyet==='aktiv'?'Paket təsdiqi qeyd olunub. Elan yayımdadır.':'Paket təsdiqi qeyd olunub. Elanı ayrıca təsdiqləyərək yayımla.',rejected:'Paket sorğusu rədd edilib. Elanı yayımlamadan əvvəl paket sorğusunu həll et.',legacy_unrequested:'Bu paket üçün təsdiq sorğusu tapılmadı. Paket tarixçəsini yoxla.',unknown:'Elanı yayımlamadan əvvəl siyahını yenilə və paket məlumatını yoxla.'};
 return {status,label:labels[status],hint:hints[status]||'',approved,canPublish:status==='free'||status==='confirmed'};
}
function packageMarkup(x){
 const info=packageInfo(x),request=typeof x.package_request_id==='string'?x.package_request_id:'';
 return `<div class="ca-package-box"><span class="ca-package-badge ca-package-${info.status}" data-package-status="${info.status}">${esc(info.label)}</span>${info.approved&&info.approved!=='Pulsuz'?`<p class="ca-package-recorded">Qeydiyyatdakı paket: ${esc(info.approved)}</p>`:''}${info.hint?`<p class="ca-package-hint">${esc(info.hint)}</p>`:''}${request?`<button type="button" class="ca-package-link" data-package-request-id="${esc(request)}" data-listing-id="${esc(x.id)}">↓ Paket sorğusuna bax</button>`:''}</div>`;
}
function drawPaymentLink(){
 let notice=el('caPayLinkedNotice');
 if(!notice){notice=document.createElement('div');notice.id='caPayLinkedNotice';notice.setAttribute('role','status');el('caPayList').before(notice);}
 notice.innerHTML=payments.linked?`<p>${esc(payments.linked.label)} üçün seçilmiş paket sorğusu.</p><button type="button" onclick="caPayClearLinked()">Bütün sorğulara qayıt</button>`:'';
 notice.hidden=!payments.linked;
}
function drawAds(){
 el('caAdminList').innerHTML=ads.rows.map(x=>{
  const info=packageInfo(x),isSold=x.veziyyet==='satilib'||x.is_sold===true;
  const status=isSold?'Satılıb':x.veziyyet;
  const actions=isSold?'<span class="ca-status-sold" role="status">✓ Satılıb · Şəxsi arxiv</span>':
   (x.veziyyet==='aktiv'?'<span class="ca-status-confirmed" role="status">✓ Təsdiqlənib</span>':`<button class="ca-yes" data-id="${esc(x.id)}" data-status="aktiv" ${info.canPublish?'':'disabled aria-disabled="true" title="Əvvəl paket sorğusunu yoxla və təsdiqlə"'}>✓ Təsdiqlə</button>`)+
   (x.veziyyet!=='reddedildi'?`<button class="ca-no" data-id="${esc(x.id)}" data-status="reddedildi">✕ Rədd et</button>`:'<span class="ca-status-rejected">✕ Rədd edilib</span>')+
   (x.veziyyet!=='gozlemede'?`<button data-id="${esc(x.id)}" data-status="gozlemede">↶ Gözləməyə qaytar</button>`:'');
  return `<article class="ca-item" data-ad-row-id="${esc(x.id)}"><strong>${esc(x.marka)} ${esc(x.model)} · ${esc(x.il)}</strong><p>${esc(x.qiymet)} AZN · ${esc(x.seher)} · Status: ${esc(status)}</p>${packageMarkup(x)}<p>${esc(String(x.tesvir||'').slice(0,250))}</p><button type="button" class="ca-admin-preview" data-preview-id="${esc(x.id)}">Şəkillər və tam məlumat</button><div class="ca-actions">${actions}</div></article>`;
 }).join('')||'<p>Bu axtarışa uyğun elan yoxdur.</p>';pager(ads,'caAdminPager','caAdminPage');
}
function drawPayments(){
 drawPaymentLink();
 el('caPayList').innerHTML=payments.rows.map(x=>`<article class="ca-item${payments.linked?.requestId===x.id?' ca-payment-linked':''}" data-pay-row-id="${esc(x.id)}"><strong>${esc(x.marka)} ${esc(x.model)} · ${esc(x.paket_adi)}</strong><p>Ödəniş: ${esc(x.odenis_veziyyeti)} · ${esc(x.yaradilib?new Date(x.yaradilib).toLocaleString('az-AZ'):'')}</p>${x.odenis_veziyyeti==='gozlemede'?`<div class="ca-actions"><button class="ca-yes" data-pay-id="${esc(x.id)}" data-pay-action="approve">✓ Ödənişi təsdiqlə</button><button class="ca-no" data-pay-id="${esc(x.id)}" data-pay-action="reject">✕ Ödənişi rədd et</button></div>`:''}</article>`).join('')||'<p>Ödəniş sorğusu yoxdur.</p>';pager(payments,'caPayPager','caPayPage');
}
function validPage(d){return d&&Array.isArray(d.items)&&['total','pending_total','page','page_size','total_pages'].every(k=>Number.isSafeInteger(d[k])&&d[k]>=0)&&d.page>=1&&d.page_size===24&&d.total_pages===Math.ceil(d.total/24)&&d.page<=Math.max(1,d.total_pages)&&d.items.length===Math.min(24,Math.max(0,d.total-(d.page-1)*24))&&d.items.every(x=>x&&typeof x.id==='string');}
async function load(kind,page){
 const s=kind==='ads'?ads:payments,expected=owner,seq=++s.sequence;
 const msg=el(kind==='ads'?'caAdminMsg':'caPayMsg'),draw=kind==='ads'?drawAds:drawPayments;
 if(!authorized||!expected)return false;
 s.loading=true;msg.textContent='Yüklənir...';pager(s,kind==='ads'?'caAdminPager':'caPayPager',kind==='ads'?'caAdminPage':'caPayPage');
 try{
  const d=await rpc(kind==='ads'?'ca_admin_browse_listings':'ca_admin_browse_payments',{p_status:s.status,p_query:s.query,p_page:page||s.page,p_page_size:24},expected);
  if(expected!==owner||currentUser?.id!==expected||seq!==s.sequence||s!==(kind==='ads'?ads:payments))return false;
  if(!validPage(d))throw Error('Natamam cavab alındı. Yenidən yoxla.');
  Object.assign(s,{rows:d.items,total:d.total,pages:d.total_pages,page:d.page,loaded:true,loading:false});
  msg.textContent=d.total+' '+(kind==='ads'?'elan':'sorğu')+' · '+d.pending_total+' gözləyir · '+(d.total?(d.page-1)*24+1:0)+'–'+(d.total?(d.page-1)*24+d.items.length:0)+' göstərilir';draw();return true;
 }catch(error){if(expected===owner&&currentUser?.id===expected&&seq===s.sequence){s.loading=false;msg.textContent='Yenilənmədi: '+error.message+(s.loaded?' Əvvəlki nəticələr saxlanılır.':'');pager(s,kind==='ads'?'caAdminPager':'caPayPager',kind==='ads'?'caAdminPage':'caPayPage');}return false;}
}
window.caAdminLoad=()=>load('ads');window.caAdminPaymentsLoad=()=>load('payments');
window.caAdminFilter=v=>{ads.status=v;return load('ads',1);};
window.caAdminSearch=()=>{ads.query=el('caAdminSearch').value.trim();return load('ads',1);};
window.caPaySearch=()=>{payments.query=el('caPaySearch').value.trim();payments.status=el('caPayFilter').value;if(payments.linked?.requestId!==payments.query)payments.linked=null;drawPaymentLink();return load('payments',1);};
window.caPayClearLinked=()=>{payments.linked=null;payments.query='';payments.status='all';el('caPaySearch').value='';el('caPayFilter').value='all';drawPaymentLink();return load('payments',1);};
async function jumpToPackage(button){
 if(!authorized)return;
 const row=ads.rows.find(x=>x.id===button.dataset.listingId&&x.package_request_id===button.dataset.packageRequestId);
 if(!row)return;
 const expected=owner,requestId=row.package_request_id;
 payments.linked={requestId,listingId:row.id,label:[row.marka,row.model].filter(Boolean).join(' ')};
 payments.query=requestId;payments.status='all';el('caPaySearch').value=requestId;el('caPayFilter').value='all';drawPaymentLink();
 const loaded=await load('payments',1);
 if(!loaded||expected!==owner||currentUser?.id!==expected||payments.linked?.requestId!==requestId)return;
 const card=[...el('caPayList').querySelectorAll('[data-pay-row-id]')].find(x=>x.dataset.payRowId===requestId);
 if(card){card.tabIndex=-1;card.focus({preventScroll:true});card.scrollIntoView({behavior:'smooth',block:'center'});}
 else{el('caPayMsg').textContent='Bu paket sorğusu tapılmadı. Siyahını yeniləyib yenidən yoxla.';el('caPayMsg').scrollIntoView({behavior:'smooth',block:'center'});}
}
window.caAdminPage=delta=>ads.loading||ads.page+delta<1||ads.page+delta>ads.pages?false:load('ads',ads.page+delta);
window.caPayPage=delta=>payments.loading||payments.page+delta<1||payments.page+delta>payments.pages?false:load('payments',payments.page+delta);
window.caAdminOpen=async()=>{if(!await verify())return alert('Admin girişi təsdiqlənmədi. Hesabına yenidən daxil ol.');el('caAdminPanel').style.display='block';await Promise.all([load('ads'),load('payments')]);};
window.caAdminClose=()=>{closePreview();el('caAdminPanel').style.display='none';};
async function refreshPublic(){const results=await Promise.allSettled([caFetchListings(1),...(currentUser?[caFetchMyListings(),caFetchFavoriteListings()]:[])]);return results.every(r=>r.status==='fulfilled'&&r.value!==false);}
async function mutate(button,name,body,confirmation){
 if(busy||button.disabled||!authorized||!confirm(confirmation))return;
 const expected=owner,epoch=sessionEpoch;busy=true;button.disabled=true;el('caAdminActionMsg').textContent='Dəyişiklik saxlanılır...';
 try{await rpc(name,body,expected);}catch(error){if(epoch===sessionEpoch&&expected===owner&&currentUser?.id===expected){el('caAdminActionMsg').textContent='Dəyişiklik saxlanmadı: '+error.message;busy=false;button.disabled=false;}return;}
 // The confirmed mutation succeeded even if refreshing a list later fails.
 const refreshed=await Promise.allSettled([refreshPublic(),...(epoch===sessionEpoch&&expected===owner&&currentUser?.id===expected?[load('ads'),load('payments')]:[])]);
 if(epoch!==sessionEpoch||expected!==owner||currentUser?.id!==expected)return;
 const ok=refreshed.every(r=>r.status==='fulfilled'&&r.value!==false);
 el('caAdminActionMsg').textContent=ok?'Dəyişiklik saxlanıldı. Elanlar və sayğaclar yeniləndi.':'Dəyişiklik saxlanıldı. Bəzi siyahılar yenilənmədi; «Yenilə» düyməsi ilə təkrar yoxla.';busy=false;button.disabled=false;
}
el('caAdminList').addEventListener('click',e=>{const preview=e.target.closest('button[data-preview-id]');if(preview){previewListing(preview);return;}const link=e.target.closest('button[data-package-request-id]');if(link){jumpToPackage(link);return;}const b=e.target.closest('button[data-id]');if(b)mutate(b,'ca_admin_status',{p_id:b.dataset.id,p_status:b.dataset.status},'Bu elanın vəziyyəti dəyişdirilsin?');});
el('caPayList').addEventListener('click',e=>{const b=e.target.closest('button[data-pay-id]');if(!b)return;const approve=b.dataset.payAction==='approve';mutate(b,approve?'ca_admin_paket_tesdiq':'ca_admin_paket_reddet',{p_sorgu_id:b.dataset.payId},approve?'SINAQ TƏSDİQİ: Real kart ödənişi qoşulmayıb. Yalnız öz sınaq sorğunu təsdiqlə. Davam edilsin?':'Ödəniş sorğusu rədd edilsin?');});
reset();setInterval(verify,12000);window.addEventListener('load',()=>setTimeout(verify,1200));document.addEventListener('visibilitychange',()=>{if(!document.hidden)verify();});
})();
