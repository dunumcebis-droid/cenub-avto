/* Public listing links and server-backed numbered pages. */
(function(){
'use strict';
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
let linkSequence=0,linkController=null,linkLoading=false,requestedId=null,shareId=null,sharing=false;
const idOf=car=>String(car?._id||car?.id||'');
const publicCar=car=>car&&uuid.test(idOf(car))&&(car.veziyyet||car.status)==='aktiv';
function pageNumbers(current,last){
 if(last<=7)return Array.from({length:last},(_,i)=>i+1);
 const values=new Set([1,last,current-1,current,current+1]);
 if(current<=3)for(let p=2;p<=4;p++)values.add(p);
 if(current>=last-2)for(let p=last-3;p<last;p++)values.add(p);
 const sorted=[...values].filter(p=>p>=1&&p<=last).sort((a,b)=>a-b),result=[];
 for(const p of sorted){const previous=result.at(-1);if(typeof previous==='number'&&p-previous===2)result.push(previous+1);else if(typeof previous==='number'&&p-previous>2)result.push('…');result.push(p);}
 return result;
}
function drawPages(){
 const element=document.getElementById('caPagination');if(!element||typeof caBrowseState==='undefined')return;
 const state=caBrowseState,current=state.page,last=state.totalPages;
 element.hidden=!state.loaded||last<2;element.style.display=element.hidden?'none':'flex';
 if(element.hidden){element.replaceChildren();return;}
 element.innerHTML=`<button type="button" id="caPagePrev" onclick="caGoToPage(${current-1})" ${state.loading||current<=1?'disabled':''}>← Əvvəlki</button>${pageNumbers(current,last).map(p=>p==='…'?'<span class="ca-page-ellipsis" aria-hidden="true">…</span>':`<button type="button" class="ca-page-number${p===current?' is-current':''}" data-page="${p}" aria-label="Səhifə ${p}" ${p===current?'aria-current="page"':''} onclick="caGoToPage(${p})" ${state.loading||p===current?'disabled':''}>${p}</button>`).join('')}<button type="button" id="caPageNext" onclick="caGoToPage(${current+1})" ${state.loading||current>=last?'disabled':''}>Növbəti →</button><span id="caPageLabel" class="ca-page-summary" aria-live="polite">${current} / ${last}</span>`;
}
window.caRenderPagination=drawPages;
window.caGoToPage=function(number){
 const page=Number(number),state=caBrowseState;
 if(!Number.isSafeInteger(page)||state.loading||page<1||page>state.totalPages||page===state.page)return false;
 cancelPendingLink();
 const pending=caFetchListings(page);document.getElementById('elanlar')?.scrollIntoView({behavior:'smooth',block:'start'});return pending;
};
const previousRender=window.render;
if(typeof previousRender==='function')window.render=function(...args){const result=previousRender.apply(this,args);drawPages();return result;};
drawPages();

function shareable(){return publicCar(activeDetailCar)&&document.getElementById('detailOverlay')?.dataset.privatePreview!=='true'&&document.getElementById('detailOverlay')?.dataset.adminPreview!=='true';}
function listingUrl(id){const url=new URL('./',location.href);url.search='';url.hash='';url.searchParams.set('ad',id);return url.href;}
function shareUi(){
 const contact=document.getElementById('detailContact');if(!contact)return;
 let panel=document.getElementById('caDetailShare');
 if(!panel){panel=document.createElement('div');panel.id='caDetailShare';panel.className='ca-detail-share';panel.innerHTML='<button type="button" id="caShareListingBtn">↗ Elanı paylaş</button><div id="caShareListingStatus" role="status" aria-live="polite"></div>';contact.append(panel);}
 const allowed=shareable(),id=allowed?idOf(activeDetailCar):null;
 panel.hidden=!allowed;const button=panel.querySelector('#caShareListingBtn');button.onclick=window.caShareListing;
 if(id!==shareId){shareId=id;panel.querySelector('#caShareListingStatus').replaceChildren();}
 if(linkLoading&&activeDetailCar&&idOf(activeDetailCar)!==requestedId){linkSequence++;linkController?.abort();linkLoading=false;setLinkNotice('');}
}
function shareStatus(id,text,manual){
 if(!shareable()||idOf(activeDetailCar)!==id)return;
 const status=document.getElementById('caShareListingStatus');if(!status)return;
 status.replaceChildren();const label=document.createElement('p');label.textContent=text;status.append(label);
 if(manual){const input=document.createElement('input');input.id='caListingLinkManual';input.readOnly=true;input.value=manual;input.setAttribute('aria-label','Elanın paylaşım linki');input.addEventListener('click',()=>input.select());status.append(input);input.focus({preventScroll:true});input.select();}
}
window.caShareListing=async function(){
 if(!shareable()||sharing)return false;
 const car=activeDetailCar,id=idOf(car),url=listingUrl(id),button=document.getElementById('caShareListingBtn');
 sharing=true;if(button)button.disabled=true;
 try{
  if(typeof navigator.share==='function'){
   try{await navigator.share({title:caCarName(car),text:caCarName(car)+' · Cənub Avto',url});shareStatus(id,'Paylaşım pəncərəsi bağlandı.');return true;}
   catch(error){if(error?.name==='AbortError'){shareStatus(id,'Paylaşım ləğv edildi.');return false;}}
  }
  if(navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(url);shareStatus(id,'Elanın linki kopyalandı.');return true;}catch(error){}}
  shareStatus(id,'Bu linki seçib kopyalaya bilərsən.',url);return false;
 }finally{sharing=false;if(button?.isConnected)button.disabled=false;}
};
const detail=document.getElementById('detailOverlay'),contact=document.getElementById('detailContact');
if(typeof MutationObserver==='function'){
 const observer=new MutationObserver(shareUi);
 if(detail)observer.observe(detail,{attributes:true,attributeFilter:['class','data-private-preview','data-admin-preview']});
 if(contact)observer.observe(contact,{childList:true});
}
shareUi();

function setLinkNotice(text,error=false,retry=false){
 let notice=document.getElementById('caListingLinkNotice');
 if(!notice){notice=document.createElement('div');notice.id='caListingLinkNotice';notice.className='ca-link-notice';document.getElementById('allGrid')?.before(notice);}
 notice.replaceChildren();notice.hidden=!text;notice.setAttribute('role',error?'alert':'status');
 if(text){const paragraph=document.createElement('p');paragraph.textContent=text;notice.append(paragraph);}
 if(retry){const button=document.createElement('button');button.type='button';button.textContent='Yenidən yoxla';button.onclick=resolveLink;notice.append(button);}
 return notice;
}
// A shared link is an initial intent, not permission to override later actions.
// Cancel only explicit navigation functions/user input, never background renders.
function cancelPendingLink(){
 if(!linkLoading)return false;
 linkSequence++;linkController?.abort();linkController=null;linkLoading=false;requestedId=null;setLinkNotice('');return true;
}
window.caCancelListingLink=cancelPendingLink;
for(const name of ['searchCars','clearCarSearch','setFilter','caToggleFilters','quickBrand','showBMWSeries','openVehiclePicker','openSellPage','openCabinet','showBuyerFavorites','showSellerCabinet','openAuth','openCarDetailKey','openCarDetail','caAdminOpen','caShowCompare','caShowBackup','caShowPolicy']){
 const original=window[name];
 if(typeof original==='function')window[name]=function(...args){cancelPendingLink();return original.apply(this,args);};
}
const sort=document.getElementById('sortListings');
if(sort)sort.addEventListener('change',cancelPendingLink,true);
function cancelForSearchInput(event){
 if(!event.isTrusted)return;
 const target=event.target;
 if(target?.closest?.('.search,#caAdvanced')||target?.matches?.('#searchMake,#searchModel,#searchPrice,#searchCity'))cancelPendingLink();
}
document.addEventListener('input',cancelForSearchInput,true);
document.addEventListener('change',cancelForSearchInput,true);
document.addEventListener('click',event=>{if(event.target?.closest?.('a[href="#elanlar"]'))cancelPendingLink();},true);
async function resolveLink(){
 const ids=new URL(location.href).searchParams.getAll('ad');if(!ids.length)return false;
 if(document.getElementById('authOverlay')?.classList.contains('open')&&['recover','reset'].includes(authMode))return false;
 const id=String(ids[0]).toLowerCase();
 if(ids.length!==1||!uuid.test(id)){setLinkNotice('Elan linki düzgün deyil.',true).scrollIntoView({block:'center'});return false;}
 linkController?.abort();linkController=new AbortController();const sequence=++linkSequence;requestedId=id;linkLoading=true;
 setLinkNotice('Elan açılır…');
 try{
  // The explicit active filter and anonymous request also protect signed-in owners.
  const rows=await caRequest('/rest/v1/elanlar?select='+CA_LISTING_COLUMNS+'&id=eq.'+encodeURIComponent(id)+'&veziyyet=eq.aktiv&limit=1','GET',null,null,{},linkController.signal);
  if(sequence!==linkSequence)return false;
  linkLoading=false;
  if(!Array.isArray(rows)||rows.length!==1||rows[0].id!==id||rows[0].veziyyet!=='aktiv'){
   setLinkNotice('Bu elan tapılmadı və ya artıq yayımdan çıxarılıb.',true).scrollIntoView({block:'center'});return false;
  }
  if(document.getElementById('authOverlay')?.classList.contains('open')){setLinkNotice('Elana baxmaq üçün giriş pəncərəsini bağlayıb yenidən yoxla.',false,true);return false;}
  const car=caRemoteToCar(rows[0]);
  if(!publicCar(car)||typeof window.caOpenCarRecord!=='function')throw Error('Listing view unavailable');
  setLinkNotice('');window.caOpenCarRecord(car,{privatePreview:false});shareUi();return true;
 }catch(error){
  if(sequence!==linkSequence||error?.name==='AbortError')return false;
  linkLoading=false;setLinkNotice('Elanı açmaq mümkün olmadı. Yenidən yoxla.',true,true).scrollIntoView({block:'center'});return false;
 }
}
window.caResolveListingLink=resolveLink;
resolveLink();
})();
