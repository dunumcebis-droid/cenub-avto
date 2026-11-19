/* Public search metadata and crawlable links; no account or listing writes. */
(function(){
'use strict';
if(typeof document==='undefined'||!document.head||!document.querySelector)return;
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const metaSelector={description:'meta[name="description"]',robots:'meta[name="robots"]',type:'meta[property="og:type"]',url:'meta[property="og:url"]',title:'meta[property="og:title"]',socialDescription:'meta[property="og:description"]',image:'meta[property="og:image"]',imageType:'meta[property="og:image:type"]',imageAlt:'meta[property="og:image:alt"]',imageWidth:'meta[property="og:image:width"]',imageHeight:'meta[property="og:image:height"]',twitterTitle:'meta[name="twitter:title"]',twitterDescription:'meta[name="twitter:description"]',twitterImage:'meta[name="twitter:image"]',twitterImageAlt:'meta[name="twitter:image:alt"]'};
const defaults={title:document.title};
for(const [key,selector] of Object.entries(metaSelector))defaults[key]=document.querySelector(selector)?.content||'';
let base;try{base=new URL(defaults.url);base.search='';base.hash='';}catch{return;}
const runtimeBase=new URL('./',location.href);runtimeBase.search='';runtimeBase.hash='';
function route(){const query=new URLSearchParams(location.search),pages=query.getAll('page'),page=pages.length===1&&/^[1-9]\d{0,8}$/.test(pages[0])?Number(pages[0]):1;return {query,ad:query.has('ad'),page,invalidPage:pages.length>1||(pages.length===1&&(!/^[1-9]\d{0,8}$/.test(pages[0])||!Number.isSafeInteger(page))),privateEntry:!!window.__caAuthCallback||['admin-email','auth','access_token','refresh_token','token_hash','code','error_description'].some(key=>query.has(key))};}
const idOf=car=>String(car?._id||car?.id||'');
let publicDetailSeen=false;
const isPublic=car=>car&&uuid.test(idOf(car))&&(car.veziyyet||car.status)==='aktiv'&&car.isSold!==true&&car.is_sold!==true;
const filtered=()=>(document.getElementById('sortListings')?.value||'newest')!=='newest'||typeof currentFilter!=='undefined'&&currentFilter!=='all'||typeof currentSearch!=='undefined'&&!!currentSearch&&Object.values(currentSearch).some(v=>Array.isArray(v)?v.length>0:v!==''&&v!==null&&v!==undefined&&v!==false);
const routeUrl=(id,page=1)=>{const url=new URL(base);if(id)url.searchParams.set('ad',id.toLowerCase());else if(page>1)url.searchParams.set('page',String(page));return url.href;};
function setMeta(key,value){const element=document.querySelector(metaSelector[key]);if(element&&element.content!==value)element.content=value;}
function setCanonical(value){let element=document.getElementById('canonical-url');if(!element){element=document.createElement('link');element.id='canonical-url';element.rel='canonical';document.head.append(element);}if(element.href!==value)element.href=value;}
function clearListingData(){document.getElementById('ca-seo-listing-data')?.remove();}
function baseMetadata(noindex=false,page=1){
 const title=page>1?'Avtomobil elanları — Səhifə '+page+' | AvtoUnvan':defaults.title;
 document.title=title;for(const key of Object.keys(metaSelector))setMeta(key,defaults[key]);
 setMeta('title',title);setMeta('twitterTitle',title);setMeta('url',routeUrl(null,page));setCanonical(routeUrl(null,page));
 setMeta('robots',noindex?'noindex, follow':defaults.robots||'index, follow');clearListingData();
}
function imageUrl(value){if(typeof value!=='string'||!value.trim())return null;try{const url=new URL(value,base);return url.protocol==='https:'?url.href:null;}catch{return null;}}
function publicMetadata(car){
 const id=idOf(car),url=routeUrl(id),name=String(caCarName(car)||'Avtomobil elanı').replace(/\s+/g,' ').trim().slice(0,120);
 const year=Number.isInteger(Number(car.year))&&Number(car.year)>=1950?String(car.year):'';
 const price=typeof car.price==='number'&&Number.isFinite(car.price)&&car.price>=0?car.price:null;
 const title=[name,year,price===null?'':caFormatPrice(price)].filter(Boolean).join(' · ')+' | AvtoUnvan';
 const facts=[name,year,price===null?'':caFormatPrice(price),car.city,typeof car.mileage==='number'?caFormatMileage(car.mileage):'',car.fuel,car.gear].filter(v=>v!==null&&v!==undefined&&String(v).trim()).map(v=>String(v).trim());
 const description=(facts.join(' · ')+'. Avtomobilin şəkillərinə və elan məlumatlarına AvtoUnvan-da baxın.').slice(0,300);
 const photo=imageUrl(car.photo||firstCarPhoto(car)),image=photo||defaults.image;
 document.title=title;setCanonical(url);setMeta('robots','index, follow');setMeta('type','product');setMeta('url',url);setMeta('title',title);setMeta('twitterTitle',title);
 setMeta('description',description);setMeta('socialDescription',description);setMeta('twitterDescription',description);setMeta('image',image);setMeta('twitterImage',image);setMeta('imageAlt',name);setMeta('twitterImageAlt',name);
 // Uploaded vehicle images have no verified dimensions; do not reuse logo sizes.
 setMeta('imageWidth','');setMeta('imageHeight','');setMeta('imageType',photo?'':defaults.imageType);
 const data={'@context':'https://schema.org','@type':'Car','@id':url+'#vehicle',name,url};
 if(car.make)data.brand={'@type':'Brand',name:String(car.make)};
 if(car.model)data.model=String(car.model);
 if(year)data.vehicleModelDate=year;
 if(photo)data.image=[photo];
 if(typeof car.mileage==='number'&&Number.isFinite(car.mileage)&&car.mileage>=0)data.mileageFromOdometer={'@type':'QuantitativeValue',value:car.mileage,unitCode:'KMT'};
 if(car.fuel)data.fuelType=String(car.fuel);
 if(car.gear)data.vehicleTransmission=String(car.gear);
 if(price!==null)data.offers={'@type':'Offer',price,priceCurrency:'AZN',availability:'https://schema.org/InStock',url};
 let script=document.getElementById('ca-seo-listing-data');if(!script){script=document.createElement('script');script.id='ca-seo-listing-data';script.type='application/ld+json';document.head.append(script);}
 const serialized=JSON.stringify(data).replace(/</g,'\\u003c');if(script.textContent!==serialized)script.textContent=serialized;
}
function linkCards(){
 for(const article of document.querySelectorAll('#allGrid .car-card,#vipGrid .car-card,#buyerFavoritesList .car-card')){
  const id=article.dataset.listingKey,heading=article.querySelector('.ca-visible-car-name');
  if(!uuid.test(id||'')||!heading||heading.querySelector('a.ca-seo-listing-link'))continue;
  const anchor=document.createElement('a'),url=new URL(runtimeBase);url.searchParams.set('ad',id.toLowerCase());anchor.href=url.href;anchor.className='ca-seo-listing-link';
  anchor.addEventListener('click',event=>{if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button!==0)event.stopPropagation();else event.preventDefault();});
  while(heading.firstChild)anchor.append(heading.firstChild);heading.append(anchor);
 }
}
function sync(){
 linkCards();
 const state=route(),query=state.query,adIntent=state.ad,privateEntry=state.privateEntry;
 const detail=document.getElementById('detailOverlay'),car=typeof activeDetailCar==='undefined'?null:activeDetailCar;
 const privateView=privateEntry||document.body.classList.contains('cabinet-open')||document.body.classList.contains('sell-open')||document.getElementById('authOverlay')?.classList.contains('open')||document.getElementById('caAdminPanel')?.style.display==='block';
 const open=detail?.classList.contains('open');
 if(open&&!privateView&&detail.dataset.privatePreview!=='true'&&detail.dataset.adminPreview!=='true'&&isPublic(car)){publicDetailSeen=true;publicMetadata(car);return;}
 if(!open&&publicDetailSeen&&adIntent){const url=new URL(location.href);url.searchParams.delete('ad');if(typeof caBrowseState!=='undefined'&&caBrowseState.loaded&&!filtered()&&caBrowseState.page>1)url.searchParams.set('page',String(caBrowseState.page));history.replaceState(history.state,'',url.href);sync();return;}
 const invalidAd=adIntent&&(query.getAll('ad').length!==1||!uuid.test(query.get('ad')||''));
 const failedLink=document.getElementById('caListingLinkNotice');
 const failure=adIntent&&failedLink&&!failedLink.hidden&&failedLink.getAttribute('role')==='alert';
 const hasFilters=!!filtered();
 const page=hasFilters?1:typeof caBrowseState!=='undefined'&&caBrowseState.loaded?caBrowseState.page:(!adIntent?state.page:1);
 baseMetadata(privateView||!!open||invalidAd||!!failure||state.invalidPage||hasFilters,page);
 if(privateView||open)setMeta('robots','noindex, nofollow');
 if(hasFilters&&!adIntent&&query.has('page')){const url=new URL(location.href);url.searchParams.delete('page');history.replaceState(history.state,'',url.href);}
 // Keep valid shared URLs self-canonical while they load; no private data is used.
 if(adIntent&&!invalidAd&&!failure&&!privateView&&!hasFilters&&!open){setCanonical(routeUrl(query.get('ad')));setMeta('url',routeUrl(query.get('ad')));}
}
if(typeof MutationObserver==='function'){
 const observer=new MutationObserver(sync);
 for(const id of ['allGrid','vipGrid','buyerFavoritesList','countLabel','caListingLinkNotice']){const element=document.getElementById(id);if(element)observer.observe(element,{childList:true,subtree:id==='caListingLinkNotice',attributes:id==='caListingLinkNotice'});}
 for(const id of ['detailOverlay','authOverlay','caAdminPanel']){const element=document.getElementById(id);if(element)observer.observe(element,{attributes:true,attributeFilter:['class','style','data-private-preview','data-admin-preview']});}
 observer.observe(document.body,{attributes:true,attributeFilter:['class']});
 // Shared-link notices are created after the initial scripts start.
 observer.observe(document.getElementById('allGrid')?.parentElement||document.body,{childList:true});
}
window.addEventListener('popstate',sync);window.addEventListener('ca:page-route',sync);sync();
const initial=route();
if(!initial.ad&&!initial.privateEntry&&!initial.invalidPage&&initial.page>1&&typeof caFetchListings==='function')caFetchListings(initial.page).then(sync);
})();
