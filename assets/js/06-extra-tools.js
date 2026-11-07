/* Additive enhancements. Existing catalog, filtering and listing functions remain intact. */
(function(){
const toolsBar=document.getElementById('caToolsBar');
const siteHeader=document.querySelector?.('body > header');
function syncToolsClearance(){
 if(siteHeader)document.documentElement.style.setProperty('--ca-header-clearance',Math.ceil(siteHeader.getBoundingClientRect().height+12)+'px');
 if(!toolsBar)return;
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
window.caShowBackup=function(){show('Məlumatların ehtiyat nüsxəsi','<p>Əsas elanlar Supabase-də saxlanır. Yerli nüsxə yalnız əlavə ehtiyatdır. Brauzer yaddaşını təmizləməzdən əvvəl ehtiyat nüsxə yarat.</p><p><strong>Diqqət:</strong> Nüsxəyə hesab məlumatları və şəxsi məlumatlar daxil ola bilər. Faylı heç kimə göndərmə və təhlükəsiz saxla. Bu, server və SMS təsdiqi əvəzi deyil.</p><button class="ca-tool" onclick="caExportBackup()">JSON nüsxəsini yüklə</button><p>İdxal funksiyası qəsdən aktiv deyil: təsadüfi və ya zərərli məlumatlarla mövcud hesabların üzərinə yazılmasının qarşısı alınır.</p>')};
window.caExportBackup=function(){try{const data={format:'cenub-avto-local-backup',version:1,created:new Date().toISOString(),cars:JSON.parse(localStorage.getItem('cenubCars')||'[]'),accounts:JSON.parse(localStorage.getItem('cenubAccounts')||'[]'),favorites:{}};for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(k&&k.startsWith('cenubFavorites_'))data.favorites[k]=localStorage.getItem(k)}const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='Cenub_Avto_ehtiyat_nusxe_'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000)}catch(e){alert('Nüsxə yaradıla bilmədi: '+e.message)}};
window.caShowPolicy=function(){show('İstifadə və təhlükəsizlik məlumatları','<p><strong>Demo statusu:</strong> Elanların yayımlanması üçün Supabase bağlantısı və təhlükəsizlik siyasətləri aktiv olmalıdır.</p><p><strong>Elan qaydaları:</strong> Yalnız sahib olduğun və ya satmağa səlahiyyətin olan nəqliyyat vasitəsini yerləşdir. Qiymət, yürüş, il və fotolar həqiqi olmalıdır. Aldadıcı, təkrar və qanunsuz elanlar yerləşdirilməməlidir.</p><p><strong>Məxfilik:</strong> Real istifadəyə başlamazdan əvvəl məlumatların saxlanması, silinməsi, istifadəçi hüquqları, əlaqə ünvanı və hüquqi məsuliyyət üzrə rəsmi məxfilik siyasəti hazırlanmalıdır.</p><p><strong>Ödəniş:</strong> 3, 5 və 15 AZN paketləri real bank ödənişi təsdiqlənmədən aktiv ödəniş xidməti kimi təqdim edilməməlidir.</p>')};
document.addEventListener('keydown',e=>{if(e.key==='Escape')caCloseDialog()});
})();
