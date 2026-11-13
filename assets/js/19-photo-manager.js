/* Individual photo deletion, category-preserving order and cover selection. */
(function(){
'use strict';
const cats=['front','rear','side','interior','engine','other'];
const names={front:'Ön görünüş',rear:'Arxa görünüş',side:'Yan görünüş',interior:'Salon',engine:'Mühərrik',other:'Digər'};
const form=document.getElementById('listingForm');if(!form)return;
const fileKeys=new WeakMap(),previews=new Map();let serial=0,owner=null,draft=undefined,rows=null,order=[],cover=null,rendering=false;
const input=cat=>document.getElementById('photos-'+cat);
const busy=()=>form.getAttribute('aria-busy')==='true';
function dispose(){for(const url of previews.values())URL.revokeObjectURL(url);previews.clear();}
function reset(){dispose();rows=null;order=[];cover=null;draft=undefined;}
function ensure(){
 const who=currentUser?.id||null;
 if(rows&&who===owner&&draft===editingCarId)return;
 dispose();owner=who;draft=editingCarId;rows=Object.fromEntries(cats.map(cat=>[cat,[]]));order=[];cover=null;
 for(const cat of cats)for(const url of editingOriginalPhotos?.[cat]||[])rows[cat].push({key:'old-'+(++serial),category:cat,url,file:null});
 const car=editingCarId?myCars().find(c=>c._id===editingCarId):null,all=Object.values(rows).flat(),used=new Set();
 for(const url of car?._photoOrder||[]){const item=all.find(r=>r.url===url&&!used.has(r.key));if(item){order.push(item.key);used.add(item.key);}}
 for(const item of all)if(!used.has(item.key))order.push(item.key);
 cover=all.find(item=>item.url===car?.photo)?.key||order[0]||null;
}
function sync(){
 ensure();
 for(const cat of cats){
  const files=[...(input(cat)?.files||[])],keys=new Map();
  for(const file of files){if(!fileKeys.has(file))fileKeys.set(file,++serial);keys.set(cat+'-file-'+fileKeys.get(file),file);}
  rows[cat]=rows[cat].filter(item=>!item.file||keys.has(item.key));
  for(const [key,file] of keys)if(!rows[cat].some(item=>item.key===key))rows[cat].push({key,category:cat,file,url:null});
 }
 const valid=new Set(Object.values(rows).flat().map(item=>item.key));order=order.filter(key=>valid.has(key));
 for(const item of Object.values(rows).flat())if(!order.includes(item.key))order.push(item.key);
 if(!valid.has(cover))cover=order[0]||null;
 for(const [key,url] of previews)if(!valid.has(key)){URL.revokeObjectURL(url);previews.delete(key);}
}
function fileList(cat){const transfer=new DataTransfer();for(const item of rows[cat])if(item.file)transfer.items.add(item.file);input(cat).files=transfer.files;}
function act(cat,key,kind){
 if(busy())return;sync();const items=rows[cat],index=items.findIndex(item=>item.key===key);if(index<0)return;
 if(kind==='cover')cover=key;
 else if(kind==='remove'){items.splice(index,1);order=order.filter(k=>k!==key);if(cover===key)cover=order[0]||null;fileList(cat);}
 else{
  const next=index+(kind==='previous'?-1:1);if(next<0||next>=items.length)return;
  const other=items[next].key,first=order.indexOf(key),second=order.indexOf(other);[items[index],items[next]]=[items[next],items[index]];[order[first],order[second]]=[order[second],order[first]];fileList(cat);
 }
 render();
}
function button(text,label,fn,disabled=false){const b=document.createElement('button');b.type='button';b.textContent=text;b.setAttribute('aria-label',label);b.disabled=disabled||busy();b.addEventListener('click',fn);return b;}
function render(){
 if(rendering)return;rendering=true;
 try{
  sync();
  for(const cat of cats){
   const box=document.getElementById('preview-'+cat);if(!box)continue;
   clearPhotoPreview(cat);box.classList.add('ca-managed-photos');
   rows[cat].forEach((item,index)=>{
    const card=document.createElement('figure');card.className='ca-managed-photo';card.dataset.photoKey=item.key;
    let src=item.url;if(item.file){if(!previews.has(item.key))previews.set(item.key,URL.createObjectURL(item.file));src=previews.get(item.key);}
    const image=document.createElement('img');image.src=src;image.alt=names[cat]+' · '+(index+1);image.loading='lazy';image.decoding='async';
    const label=document.createElement('figcaption');label.textContent=(cover===item.key?'★ Əsas şəkil · ':'')+(index+1);
    const actions=document.createElement('div');actions.className='ca-photo-actions';
    actions.append(button('★','Əsas şəkil seç',()=>act(cat,item.key,'cover'),cover===item.key),button('←','Şəkli əvvələ keçir',()=>act(cat,item.key,'previous'),index===0),button('→','Şəkli sonraya keçir',()=>act(cat,item.key,'next'),index===rows[cat].length-1),button('Sil','Şəkli sil',()=>act(cat,item.key,'remove')));
    card.append(image,label,actions);box.append(card);
   });
  }
  const all=Object.values(rows).flat(),fresh=all.filter(item=>item.file).length;
  document.getElementById('photoTotal').textContent=all.length+' / 36 şəkil (yeni: '+fresh+', saxlanılan: '+(all.length-fresh)+'). Hər bölmədə yeni və saxlanılan birlikdə maksimum 6 şəkil. ★ ilə əsas şəkli seç.';
 }finally{rendering=false;}
}
window.caPhotoManagerProject=function(){sync();return Object.fromEntries(cats.filter(cat=>rows[cat].length).map(cat=>[cat,rows[cat].map(item=>item.file?'new':item.url)]));};
window.caPhotoManagerFinalize=function(data){
 sync();const mapped=new Map();data.photos={};
 for(const cat of cats){
  const urls=[];
  for(const item of rows[cat]){
   const stored=item.file?caPhotoUploadCache.get(item.file):null;
   const url=item.file?(stored?.owner===owner&&stored.category===cat?stored.url:null):item.url;
   if(!url)throw Error('Şəklin yüklənməsi tamamlanmayıb. Yenidən yoxla.');urls.push(url);mapped.set(item.key,url);
  }
  if(urls.length)data.photos[cat]=urls;
 }
 const keys=[cover,...order.filter(key=>key!==cover)].filter(key=>mapped.has(key));data._photoOrder=keys.map(key=>mapped.get(key));
 if(new Set(data._photoOrder).size!==data._photoOrder.length)throw Error('Eyni şəkil bir neçə dəfə seçilib. Təkrar şəkli sil.');
 data.photo=data._photoOrder[0]||'';
};
window.caPhotoManagerSessionChanged=()=>{if(owner!==(currentUser?.id||null)){reset();render();}};
const oldEdit=window.editCar,oldClear=window.caClearListingDraft,oldResume=window.caResumeSavedListingDraft;
window.editCar=function(...args){const value=oldEdit.apply(this,args);render();return value;};
window.caClearListingDraft=function(...args){reset();const value=oldClear.apply(this,args);render();return value;};
window.caResumeSavedListingDraft=function(...args){
 // The current Files already refer to their cached uploads. Keep those records
 // when a lost create response is recovered, instead of adding saved URLs again.
 sync();const value=oldResume.apply(this,args);draft=editingCarId;return value;
};
window.updatePhotoTotal=render;
for(const cat of cats)input(cat)?.addEventListener('change',render);
form.addEventListener('reset',()=>{reset();queueMicrotask(render);});
window.caRenderPhotoManager=render;render();
})();
