/* Saved cars belong to the immutable account ID, never an editable phone number.
   Legacy device lists are preserved and imported only after an explicit choice. */
(function(){
'use strict';
const USER_PREFIX='cenubFavorites_user_',LEGACY_OWNER_PREFIX='cenubFavorites_legacy_owner_';
let currentOwner=null,messageOwner=null,migrationMessage='';
const accountId=user=>typeof user?.id==='string'?user.id.trim():'';
function readList(key){
 if(!key)return [];
 try{const value=JSON.parse(localStorage.getItem(key)||'[]');return Array.isArray(value)?[...new Set(value.filter(item=>typeof item==='string'&&item.length>0&&item.length<=512))]:[];}catch(error){return [];}
}
function keyFor(user=currentUser){const id=accountId(user);return id?USER_PREFIX+encodeURIComponent(id):'';}
window.caFavoriteStorageKey=keyFor;
window.favoriteKeys=function(){return readList(keyFor());};
function legacy(){
 const id=accountId(currentUser),phone=String(currentUser?.phone||'');
 // A phone cannot be used to address another account's new UUID storage key.
 if(!id||!/^\+?\d{9,15}$/.test(phone))return null;
 const key='cenubFavorites_'+phone,binding=LEGACY_OWNER_PREFIX+encodeURIComponent(key);
 try{
  const bound=localStorage.getItem(binding);
  if(bound&&bound!==id)return null;
  const values=readList(key);return values.length?{id,key,binding,bound,values}:null;
 }catch(error){return null;}
}
function ensureLegacyUi(){
 const parent=document.getElementById('buyerFavoritesPanel');if(!parent)return null;
 let panel=document.getElementById('caLegacyFavoritesNotice');
 if(!panel){
  panel=document.createElement('section');panel.id='caLegacyFavoritesNotice';panel.className='ca-legacy-favorites';panel.hidden=true;
  const text=document.createElement('p');text.id='caLegacyFavoritesText';
  const button=document.createElement('button');button.type='button';button.id='caImportLegacyFavorites';button.className='back-btn';button.textContent='Köhnə seçilmişləri gətir';button.addEventListener('click',importLegacy);
  const status=document.createElement('p');status.id='caLegacyFavoritesStatus';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  panel.append(text,button,status);parent.insertBefore(panel,document.getElementById('buyerFavoritesList'));
 }
 return panel;
}
function syncLegacyUi(){
 const panel=ensureLegacyUi();if(!panel)return;
 const id=accountId(currentUser),old=legacy(),offer=Boolean(old&&!old.bound),message=id&&messageOwner===id?migrationMessage:'';
 panel.hidden=!id||!offer&&!message;
 panel.querySelector('#caLegacyFavoritesText').textContent=offer?'Bu cihazda köhnə seçilmişlər siyahısı var. Öz siyahındırsa, hesabına əlavə edə bilərsən.':'';
 panel.querySelector('#caImportLegacyFavorites').hidden=!offer;
 panel.querySelector('#caLegacyFavoritesStatus').textContent=message;
}
function refresh(){
 render();renderBuyerFavorites();
 const panel=document.getElementById('buyerFavoritesPanel');
 if(currentUser&&panel&&panel.style.display!=='none')caFetchFavoriteListings();
}
function importLegacy(){
 const old=legacy(),key=keyFor();
 if(!old||!key)return false;
 // Repeated clicks do not resurrect cars removed after a completed import.
 if(old.bound===old.id){syncLegacyUi();return true;}
 try{
  localStorage.setItem(old.binding,old.id);
  if(localStorage.getItem(old.binding)!==old.id)throw Error('Köhnə siyahının hesabı dəyişib.');
  try{localStorage.setItem(key,JSON.stringify([...new Set([...readList(key),...old.values])]));}
  catch(error){if(localStorage.getItem(old.binding)===old.id)localStorage.removeItem(old.binding);throw error;}
  messageOwner=old.id;migrationMessage='Köhnə seçilmişlər hesabına əlavə olundu.';
  refresh();syncLegacyUi();return true;
 }catch(error){
  messageOwner=old.id;migrationMessage='Köhnə seçilmişlər gətirilmədi. Brauzer yaddaşını yoxla.';syncLegacyUi();return false;
 }
}
window.caImportLegacyFavorites=importLegacy;
window.toggleFavorite=function(key,event){
 if(event){event.preventDefault();event.stopPropagation();}
 if(!currentUser){pendingAction='favorite:'+key;openAuth('register');return;}
 if(typeof key!=='string'||!key||key.length>512)return;
 const storageKey=keyFor();if(!storageKey)return;
 const keys=favoriteKeys(),next=keys.includes(key)?keys.filter(value=>value!==key):[...keys,key];
 try{localStorage.setItem(storageKey,JSON.stringify(next));}
 catch(error){alert('Seçilmişlər yadda saxlanmadı. Telefon yaddaşını yoxla.');return;}
 refresh();
};
const originalRender=window.renderBuyerFavorites;
if(typeof originalRender==='function')window.renderBuyerFavorites=function(...args){const result=originalRender.apply(this,args);syncLegacyUi();return result;};
window.caAccountFavoritesSessionChanged=function(){
 const id=accountId(currentUser);
 if(id!==currentOwner){currentOwner=id;messageOwner=null;migrationMessage='';renderBuyerFavorites();}
 syncLegacyUi();
};
window.addEventListener('storage',event=>{
 const old=legacy();
 if(event.key===keyFor()||old&&(event.key===old.key||event.key===old.binding)){
  render();renderBuyerFavorites();syncLegacyUi();
 }
});
if(typeof MutationObserver==='function')new MutationObserver(syncLegacyUi).observe(document.body,{attributes:true,attributeFilter:['class']});
window.caAccountFavoritesSessionChanged();render();renderBuyerFavorites();
})();
