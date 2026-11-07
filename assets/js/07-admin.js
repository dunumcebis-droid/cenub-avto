(function(){
const el=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let owner=null,authorized=false,verifySequence=0,busy=false,sessionEpoch=0;
const state=()=>({page:1,total:0,pages:0,rows:[],status:'all',query:'',sequence:0,loading:false,loaded:false});
let ads=state(),payments=state();
function reset(){sessionEpoch++;verifySequence++;owner=currentUser?.id||null;authorized=false;busy=false;ads.sequence++;payments.sequence++;ads=state();payments=state();el('caAdminLaunch').style.display='none';el('caAdminPanel').style.display='none';for(const id of ['caAdminList','caPayList','caAdminMsg','caPayMsg','caAdminPager','caPayPager'])el(id).replaceChildren();el('caAdminSearch').value='';el('caPaySearch').value='';el('caPayFilter').value='all';el('caAdminActionMsg').textContent='';}
window.caAdminSessionChanged=()=>{if(owner!==(currentUser?.id||null))reset();};
async function rpc(name,body,expected=owner){
 const t=await caToken();
 if(!expected||currentUser?.id!==expected||owner!==expected||!t)throw Error('Hesab dəyişib və ya sessiya bitib. Yenidən daxil ol.');
 return caRequest('/rest/v1/rpc/'+name,'POST',body,t);
}
async function verify(){
 window.caAdminSessionChanged();if(!owner)return false;
 const expected=owner,seq=++verifySequence;
 try{const ok=await rpc('cenub_admin_yoxla',{},expected);if(seq!==verifySequence||owner!==expected||currentUser?.id!==expected)return false;authorized=ok===true;el('caAdminLaunch').style.display=authorized?'block':'none';if(!authorized)el('caAdminPanel').style.display='none';return authorized;}
 catch(error){if(seq===verifySequence&&owner===expected){authorized=false;el('caAdminLaunch').style.display='none';el('caAdminPanel').style.display='none';}return false;}
}
function pager(s,id,handler){el(id).innerHTML=s.pages>1?`<div class="ca-actions"><button type="button" onclick="${handler}(-1)" ${s.loading||s.page<=1?'disabled':''}>← Əvvəlki</button><span>${s.page} / ${s.pages}</span><button type="button" onclick="${handler}(1)" ${s.loading||s.page>=s.pages?'disabled':''}>Növbəti →</button></div>`:'';}
function drawAds(){
 el('caAdminList').innerHTML=ads.rows.map(x=>`<article class="ca-item"><strong>${esc(x.marka)} ${esc(x.model)} · ${esc(x.il)}</strong><p>${esc(x.qiymet)} AZN · ${esc(x.seher)} · Status: ${esc(x.veziyyet)}</p><p>${esc(String(x.tesvir||'').slice(0,250))}</p><div class="ca-actions">${x.veziyyet==='aktiv'?'<span class="ca-status-confirmed" role="status">✓ Təsdiqlənib</span>':`<button class="ca-yes" data-id="${esc(x.id)}" data-status="aktiv">✓ Təsdiqlə</button>`}${x.veziyyet!=='reddedildi'?`<button class="ca-no" data-id="${esc(x.id)}" data-status="reddedildi">✕ Rədd et</button>`:'<span class="ca-status-rejected">✕ Rədd edilib</span>'}${x.veziyyet!=='gozlemede'?`<button data-id="${esc(x.id)}" data-status="gozlemede">↶ Gözləməyə qaytar</button>`:''}</div></article>`).join('')||'<p>Bu axtarışa uyğun elan yoxdur.</p>';pager(ads,'caAdminPager','caAdminPage');
}
function drawPayments(){
 el('caPayList').innerHTML=payments.rows.map(x=>`<article class="ca-item"><strong>${esc(x.marka)} ${esc(x.model)} · ${esc(x.paket_adi)}</strong><p>Ödəniş: ${esc(x.odenis_veziyyeti)} · ${esc(x.yaradilib?new Date(x.yaradilib).toLocaleString('az-AZ'):'')}</p>${x.odenis_veziyyeti==='gozlemede'?`<div class="ca-actions"><button class="ca-yes" data-pay-id="${esc(x.id)}" data-pay-action="approve">✓ Ödənişi təsdiqlə</button><button class="ca-no" data-pay-id="${esc(x.id)}" data-pay-action="reject">✕ Ödənişi rədd et</button></div>`:''}</article>`).join('')||'<p>Ödəniş sorğusu yoxdur.</p>';pager(payments,'caPayPager','caPayPage');
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
window.caPaySearch=()=>{payments.query=el('caPaySearch').value.trim();payments.status=el('caPayFilter').value;return load('payments',1);};
window.caAdminPage=delta=>ads.loading||ads.page+delta<1||ads.page+delta>ads.pages?false:load('ads',ads.page+delta);
window.caPayPage=delta=>payments.loading||payments.page+delta<1||payments.page+delta>payments.pages?false:load('payments',payments.page+delta);
window.caAdminOpen=async()=>{if(!await verify())return alert('Admin girişi təsdiqlənmədi. Hesabına yenidən daxil ol.');el('caAdminPanel').style.display='block';await Promise.all([load('ads'),load('payments')]);};
window.caAdminClose=()=>{el('caAdminPanel').style.display='none';};
async function refreshPublic(){const results=await Promise.allSettled([caFetchListings(1),...(currentUser?[caFetchMyListings(),caFetchFavoriteListings()]:[])]);return results.every(r=>r.status==='fulfilled'&&r.value!==false);}
async function mutate(button,name,body,confirmation){
 if(busy||!authorized||!confirm(confirmation))return;
 const expected=owner,epoch=sessionEpoch;busy=true;button.disabled=true;el('caAdminActionMsg').textContent='Dəyişiklik saxlanılır...';
 try{await rpc(name,body,expected);}catch(error){if(epoch===sessionEpoch&&expected===owner&&currentUser?.id===expected){el('caAdminActionMsg').textContent='Dəyişiklik saxlanmadı: '+error.message;busy=false;button.disabled=false;}return;}
 // The confirmed mutation succeeded even if refreshing a list later fails.
 const refreshed=await Promise.allSettled([refreshPublic(),...(epoch===sessionEpoch&&expected===owner&&currentUser?.id===expected?[load('ads'),load('payments')]:[])]);
 if(epoch!==sessionEpoch||expected!==owner||currentUser?.id!==expected)return;
 const ok=refreshed.every(r=>r.status==='fulfilled'&&r.value!==false);
 el('caAdminActionMsg').textContent=ok?'Dəyişiklik saxlanıldı. Elanlar və sayğaclar yeniləndi.':'Dəyişiklik saxlanıldı. Bəzi siyahılar yenilənmədi; «Yenilə» düyməsi ilə təkrar yoxla.';busy=false;button.disabled=false;
}
el('caAdminList').addEventListener('click',e=>{const b=e.target.closest('button[data-id]');if(b)mutate(b,'ca_admin_status',{p_id:b.dataset.id,p_status:b.dataset.status},'Bu elanın vəziyyəti dəyişdirilsin?');});
el('caPayList').addEventListener('click',e=>{const b=e.target.closest('button[data-pay-id]');if(!b)return;const approve=b.dataset.payAction==='approve';mutate(b,approve?'ca_admin_paket_tesdiq':'ca_admin_paket_reddet',{p_sorgu_id:b.dataset.payId},approve?'SINAQ TƏSDİQİ: Real kart ödənişi qoşulmayıb. Yalnız öz sınaq sorğunu təsdiqlə. Davam edilsin?':'Ödəniş sorğusu rədd edilsin?');});
reset();setInterval(verify,12000);window.addEventListener('load',()=>setTimeout(verify,1200));document.addEventListener('visibilitychange',()=>{if(!document.hidden)verify();});
})();
