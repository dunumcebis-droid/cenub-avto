/* Additive enhancements. Existing catalog, filtering and listing functions remain intact. */
(function(){
const toolsBar=document.getElementById('caToolsBar');
const siteHeader=document.querySelector?.('body > header');
function syncToolsClearance(){
 if(siteHeader)document.documentElement.style.setProperty('--ca-header-clearance',Math.ceil(siteHeader.getBoundingClientRect().height+12)+'px');
 if(!toolsBar||toolsBar.hidden)return;
 const clearance=Math.max(0,window.innerHeight-toolsBar.getBoundingClientRect().top)+16;
 document.documentElement.style.setProperty('--ca-tools-clearance',Math.ceil(clearance)+'px');
}
if(toolsBar){
 if(typeof ResizeObserver==='function'){const observer=new ResizeObserver(syncToolsClearance);observer.observe(toolsBar);if(siteHeader)observer.observe(siteHeader);}
 else if(typeof MutationObserver==='function'){const observer=new MutationObserver(syncToolsClearance);const options={attributes:true,subtree:true,attributeFilter:['style','class','hidden']};observer.observe(toolsBar,options);if(siteHeader)observer.observe(siteHeader,{...options,childList:true,characterData:true});}
 window.addEventListener('resize',syncToolsClearance);
 document.fonts?.ready.then(syncToolsClearance);
 syncToolsClearance();
}
// Floating page tools must not cover or take focus from an open dialog.
if(toolsBar){
 const modalIds=['detailOverlay','authOverlay','vehiclePicker','generationPicker','listingFeedback','caOverlay','caAdminPanel','caPhotoViewer','caMarketOverlay'];
 const observedModals=new WeakSet();
 let modalObserver;
 function syncModalTools(){
  const modals=modalIds.map(id=>document.getElementById(id)).filter(Boolean);
  for(const modal of modals)if(modalObserver&&!observedModals.has(modal)){
   modalObserver.observe(modal,{attributes:true,attributeFilter:['class','style','hidden']});observedModals.add(modal);
  }
  const blocked=modals.some(modal=>modal.classList.contains('open')||modal.classList.contains('ca-open')||modal.id==='caAdminPanel'&&modal.style.display&&modal.style.display!=='none');
  if(toolsBar.hidden!==blocked)toolsBar.hidden=blocked;
  if(toolsBar.inert!==blocked)toolsBar.inert=blocked;
  const aria=blocked?'true':'false';if(toolsBar.getAttribute('aria-hidden')!==aria)toolsBar.setAttribute('aria-hidden',aria);
  if(document.body.classList.contains('ca-content-modal-open')!==blocked)document.body.classList.toggle('ca-content-modal-open',blocked);
  if(!blocked)syncToolsClearance();
 }
 if(typeof MutationObserver==='function'){
  modalObserver=new MutationObserver(syncModalTools);modalObserver.observe(document.body,{childList:true});
 }
 window.caSyncToolsModalState=syncModalTools;syncModalTools();
}
let comparison=[],comparisonOpen=false,comparisonOwner=currentUser?.id||null;
const comparisonRows=new Map();
const unavailableComparisons=new Set();
const comparisonFields=['make','model','price','year','mileage','city','engine','horsepower','fuel','gear','body','color','equipment'];
const isPublic=c=>c&&(c.veziyyet||c.status)==='aktiv';
function rememberComparison(key,car){
 if(!isPublic(car)){comparisonRows.delete(key);return false;}
 // Keep only displayed public fields when another page evicts the main cache.
 comparisonRows.set(key,Object.fromEntries(comparisonFields.map(field=>[field,Array.isArray(car[field])?car[field].slice():car[field]])));
 return true;
}
function syncComparison(fresh=[]){
 const rows=new Map(fresh.map(car=>[listingKey(car),car]));
 for(const [key,car] of rows){if(isPublic(car))unavailableComparisons.delete(key);else unavailableComparisons.add(key);}
 comparison=comparison.filter(key=>{if(unavailableComparisons.has(key)){comparisonRows.delete(key);return false;}const known=rows.get(key)||caListingCache.get(key);return known?rememberComparison(key,known):comparisonRows.has(key);});
 document.getElementById('caCompareCount').textContent=comparison.length;
}
function refreshComparison(){if(comparisonOpen&&document.getElementById('caOverlay').classList.contains('ca-open'))caShowCompare();}
function removeComparison(key){
 if(typeof key==='string')unavailableComparisons.add(key);
 if(!comparison.includes(key))return;
 comparison=comparison.filter(selected=>selected!==key);comparisonRows.delete(key);render();
}
const originalRender=window.render;
window.render=function(...args){syncComparison();const result=originalRender.apply(this,args);refreshComparison();return result;};
const originalRemember=window.caRememberListings;
window.caRememberListings=function(cars){const result=originalRemember.apply(this,arguments);syncComparison(cars);refreshComparison();return result;};
const originalAccountUI=window.updateAccountUI;
window.updateAccountUI=function(...args){
 const owner=currentUser?.id||null,changed=owner!==comparisonOwner;
 if(changed){comparisonOwner=owner;comparison=[];comparisonRows.clear();if(comparisonOpen){caCloseDialog();comparisonOpen=false;document.getElementById('caDialogBody').replaceChildren();}}
 const result=originalAccountUI.apply(this,args);if(changed)render();return result;
};
const originalDelete=window.caDeleteRemoteCar;
window.caDeleteRemoteCar=async function(...args){const id=await originalDelete.apply(this,args);removeComparison(id);return id;};
const originalSave=window.caSaveRemoteCar;
window.caSaveRemoteCar=async function(...args){const id=await originalSave.apply(this,args);if(args[1])removeComparison(id);return id;};
const originalRequest=window.caRequest;
window.caRequest=async function(path,method,body,...args){
 const result=await originalRequest.call(this,path,method,body,...args);
 if(path.split('?')[0]==='/rest/v1/rpc/ca_admin_status'&&method==='POST'&&body?.p_status!=='aktiv')removeComparison(body?.p_id);
 return result;
};
const originalCard=window.card;
if(typeof originalCard==='function'){
 window.card=function(c){let html=originalCard(c);const key=encodeURIComponent(listingKey(c));const selected=comparison.includes(listingKey(c));const btn='<button class="ca-compare" type="button" aria-label="Avtomobili müqayisəyə əlavə et" onclick="event.stopPropagation();caToggleCompare(decodeURIComponent(\''+key+'\'),event)">'+(selected?'✓ Müqayisədən çıxar':'⚖ Müqayisə et')+'</button>';return html.replace('</article>',btn+'</article>');};
}
window.caToggleCompare=function(key,event){if(event){event.preventDefault();event.stopPropagation()}syncComparison();const i=comparison.indexOf(key);if(i>=0){comparison.splice(i,1);comparisonRows.delete(key);}else{const c=allCars().find(x=>listingKey(x)===key);if(unavailableComparisons.has(key)||!isPublic(c))return;if(comparison.length>=3){alert('Maksimum 3 avtomobil müqayisə oluna bilər.');return}comparison.push(key);rememberComparison(key,c);}render()};
window.caCloseDialog=function(){document.getElementById('caOverlay').classList.remove('ca-open')};
function show(title,html,isComparison=false){comparisonOpen=isComparison;document.getElementById('caDialogTitle').textContent=title;document.getElementById('caDialogBody').innerHTML=html;document.getElementById('caOverlay').classList.add('ca-open')}
window.caShowCompare=function(){syncComparison();if(!comparison.length){show('Avtomobil müqayisəsi','<p>Elan kartlarında “Müqayisə et” düyməsinə toxun. Üç avtomobilədək seçə bilərsən.</p>',true);return}const fields=[['Marka / model',caCarName],['Qiymət',c=>caFormatPrice(c.price)],['İl',c=>c.year],['Yürüş',c=>caFormatMileage(c.mileage)],['Şəhər',c=>c.city],['Mühərrik',c=>c.engine],['At gücü',c=>c.horsepower],['Yanacaq',c=>c.fuel],['Sürətlər qutusu',c=>c.gear],['Ban növü',c=>c.body],['Rəng',c=>c.color],['Təchizat',c=>Array.isArray(c.equipment)?c.equipment.join(', '):c.equipment]];const safe=x=>String(x??'—').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));show('Avtomobillərin müqayisəsi','<div class="ca-compare-scroll"><table class="ca-compare-table"><tbody>'+fields.map(([label,fn])=>'<tr><th>'+label+'</th>'+comparison.map(key=>'<td>'+safe(caValue(fn(comparisonRows.get(key)))??'—')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div><p>Bu müqayisə yalnız açıq səhifə müddətində saxlanılır.</p><button class="ca-tool" onclick="caClearCompare()">Müqayisəni təmizlə</button>',true)};
window.caClearCompare=function(){comparison=[];comparisonRows.clear();render();caShowCompare()};
window.caShowBackup=function(){if(typeof window.caShowServerBackup==='function')return window.caShowServerBackup();show('Ehtiyat nüsxə','<p>Ehtiyat nüsxə bölməsi yüklənmədi. Səhifəni yeniləyib təkrar yoxla.</p>')};
window.caShowPolicy=function(){show('Qaydalar və məxfilik','<p>Elan yerləşdirmə və xidmətdən istifadə şərtləri ilə tanış ol.</p><p><a class="ca-info-primary" href="terms.html">İstifadə qaydaları</a></p><p><a class="ca-info-primary" href="privacy.html">Məxfilik siyasəti</a></p><p>Suallar üçün <a href="mailto:cenubavtoelan@gmail.com">cenubavtoelan@gmail.com</a> və ya <a href="tel:+994709091997">0709091997</a>.</p>')};
document.addEventListener('keydown',e=>{if(e.key==='Escape')caCloseDialog()});
})();
