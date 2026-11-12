/* Full-viewport viewing uses the original photo URLs and the listing watermark. */
(function(){
'use strict';
let viewer,stage,canvas,caption,message,zoomLabel;
let photos=[],index=0,scale=1,panX=0,panY=0,ready=false,detailCar=null;
let previousFocus=null,previousOverflow='',background=[],historyToken=null,backPending=false,queuedOpen=false;
let gesture=null,lastTap=null,lastTouchZoom=-Infinity;
const pointers=new Map();
const HISTORY_KEY='caPhotoViewer';
const clamp=(number,low,high)=>Math.max(low,Math.min(high,number));
const isOpen=()=>Boolean(viewer?.classList.contains('open'));

function ensureViewer(){
 if(viewer)return;
 viewer=document.createElement('section');
 viewer.id='caPhotoViewer';viewer.className='ca-photo-viewer';viewer.hidden=true;
 viewer.setAttribute('role','dialog');viewer.setAttribute('aria-modal','true');
 viewer.setAttribute('aria-labelledby','caPhotoViewerTitle');viewer.setAttribute('aria-hidden','true');viewer.tabIndex=-1;
 viewer.innerHTML=`<header class="ca-photo-viewer-header"><h2 id="caPhotoViewerTitle">Avtomobil şəkilləri</h2><button type="button" class="ca-photo-viewer-close" data-ca-viewer="close" aria-label="Şəkil baxışını bağla">✕ Bağla</button></header><div id="caPhotoViewerStage" class="ca-photo-viewer-stage"><div id="caPhotoViewerCanvas" class="ca-photo-viewer-canvas"></div><button type="button" class="ca-photo-viewer-prev" data-ca-viewer="prev" aria-label="Əvvəlki şəkil">‹</button><button type="button" class="ca-photo-viewer-next" data-ca-viewer="next" aria-label="Növbəti şəkil">›</button><p id="caPhotoViewerMessage" class="ca-photo-viewer-message" role="status"></p></div><footer class="ca-photo-viewer-footer"><p id="caPhotoViewerCaption" aria-live="polite"></p><div class="ca-photo-viewer-toolbar" aria-label="Şəkli böyütmə"><button type="button" data-ca-viewer="minus" aria-label="Şəkli kiçilt">−</button><span id="caPhotoViewerZoom" aria-live="polite">100%</span><button type="button" data-ca-viewer="plus" aria-label="Şəkli böyüt">+</button><button type="button" data-ca-viewer="reset">Sığdır</button></div><p id="caPhotoViewerHint">Böyütmək üçün iki dəfə toxunun və ya iki barmaqdan istifadə edin.</p></footer>`;
 document.body.appendChild(viewer);
 stage=viewer.querySelector('#caPhotoViewerStage');canvas=viewer.querySelector('#caPhotoViewerCanvas');
 caption=viewer.querySelector('#caPhotoViewerCaption');message=viewer.querySelector('#caPhotoViewerMessage');zoomLabel=viewer.querySelector('#caPhotoViewerZoom');
 viewer.addEventListener('click',event=>{
  const action=event.target.closest('[data-ca-viewer]')?.dataset.caViewer;
  if(action==='close')close();
  else if(action==='prev')change(-1);
  else if(action==='next')change(1);
  else if(action==='plus')zoomTo(scale+.5);
  else if(action==='minus')zoomTo(scale-.5);
  else if(action==='reset')zoomTo(1);
 });
 stage.addEventListener('pointerdown',pointerDown);
 stage.addEventListener('pointermove',pointerMove);
 stage.addEventListener('pointerup',pointerUp);
 stage.addEventListener('pointercancel',cancelPointer);
 stage.addEventListener('lostpointercapture',cancelPointer);
 stage.addEventListener('dblclick',event=>{
  if(event.target.closest('button'))return;
  if(event.sourceCapabilities?.firesTouchEvents||performance.now()-lastTouchZoom<500)return;
  event.preventDefault();toggleZoom(event.clientX,event.clientY);
 });
 stage.addEventListener('wheel',event=>{
  if(!isOpen()||!ready)return;
  event.preventDefault();zoomTo(scale*Math.exp(-event.deltaY*.002),event.clientX,event.clientY);
 },{passive:false});
}

function fittedSize(){
 const img=canvas?.querySelector('img'),width=stage?.clientWidth||0,height=stage?.clientHeight||0;
 if(!img?.naturalWidth||!img.naturalHeight)return {width:0,height:0};
 const factor=Math.min(width/img.naturalWidth,height/img.naturalHeight);
 return {width:img.naturalWidth*factor,height:img.naturalHeight*factor};
}
function renderTransform(){
 const fit=fittedSize();
 panX=clamp(panX,-Math.max(0,(fit.width*scale-stage.clientWidth)/2),Math.max(0,(fit.width*scale-stage.clientWidth)/2));
 panY=clamp(panY,-Math.max(0,(fit.height*scale-stage.clientHeight)/2),Math.max(0,(fit.height*scale-stage.clientHeight)/2));
 canvas.style.transform=`translate(${panX}px,${panY}px) scale(${scale})`;
 viewer.dataset.zoom=String(scale);stage.classList.toggle('is-zoomed',scale>1.001);
 zoomLabel.textContent=Math.round(scale*100)+'%';
 viewer.querySelector('[data-ca-viewer="minus"]').disabled=!ready||scale<=1.001;
 viewer.querySelector('[data-ca-viewer="plus"]').disabled=!ready||scale>=3.999;
 viewer.querySelector('[data-ca-viewer="reset"]').disabled=!ready||scale<=1.001;
}
function measure(){
 if(!isOpen())return;
 const frame=canvas.querySelector('.ca-watermark-frame'),fit=fittedSize();
 // Keep the watermark in the unscaled image coordinates; canvas scales it once.
 if(frame){frame.style.setProperty('--ca-watermark-photo-width',fit.width+'px');frame.style.setProperty('--ca-watermark-photo-height',fit.height+'px');}
 renderTransform();
}
function zoomTo(next,x,y){
 if(!ready)return;
 next=clamp(next,1,4);
 const rect=stage.getBoundingClientRect(),px=Number.isFinite(x)?x-rect.left-rect.width/2:0,py=Number.isFinite(y)?y-rect.top-rect.height/2:0;
 const ratio=next/scale;
 panX=px-(px-panX)*ratio;panY=py-(py-panY)*ratio;scale=next;
 if(scale===1){panX=0;panY=0;}
 renderTransform();
}
function toggleZoom(x,y){zoomTo(scale>1.001?1:2.5,x,y);}
function setMessage(text,state){viewer.dataset.photoState=state;message.textContent=text;message.hidden=!text;}
function renderPhoto(){
 pointers.clear();gesture=null;lastTap=null;scale=1;panX=0;panY=0;ready=false;
 const photo=photos[index];
 canvas.innerHTML=caListingPhotoMarkup(photo.src,photo.category||'Avtomobil şəkli','gallery');
 caption.textContent=(index+1)+' / '+photos.length+(photo.category?' · '+photo.category:'');
 for(const button of viewer.querySelectorAll('.ca-photo-viewer-prev,.ca-photo-viewer-next'))button.hidden=photos.length<2;
 setMessage('Şəkil yüklənir…','loading');renderTransform();
 const img=canvas.querySelector('img');
 if(!img){setMessage('Şəkil açıla bilmədi.','error');return;}
 img.loading='eager';img.draggable=false;
 const loaded=()=>{
  if(!isOpen()||canvas.querySelector('img')!==img)return;
  ready=Boolean(img.naturalWidth&&img.naturalHeight);
  setMessage(ready?'':'Şəkil açıla bilmədi.',ready?'ready':'error');measure();
 };
 img.addEventListener('load',loaded,{once:true});img.addEventListener('error',loaded,{once:true});
 if(img.complete)loaded();
}
function change(delta){
 if(!isOpen()||photos.length<2)return;
 index=(index+delta+photos.length)%photos.length;renderPhoto();
}
function open(){
 if(backPending){queuedOpen=true;return false;}
 if(isOpen()||typeof detailPhotos==='undefined'||!detailPhotos.length||!document.getElementById('detailOverlay')?.classList.contains('open'))return false;
 ensureViewer();
 photos=detailPhotos.filter(photo=>photo&&typeof photo.src==='string'&&photo.src).map(photo=>({src:photo.src,category:photo.category||''}));
 if(!photos.length)return false;
 index=clamp(Number(detailPhotoIndex)||0,0,photos.length-1);detailCar=activeDetailCar;
 previousFocus=document.activeElement;previousOverflow=document.body.style.overflow;
 viewer.hidden=false;viewer.classList.add('open');viewer.setAttribute('aria-hidden','false');
 document.body.classList.add('ca-photo-viewer-open');document.body.style.overflow='hidden';
 viewer.querySelector('[data-ca-viewer="close"]').focus({preventScroll:true});
 background=[...document.body.children].filter(element=>element!==viewer&&!['SCRIPT','STYLE','LINK'].includes(element.tagName)).map(element=>({element,inert:element.inert,aria:element.getAttribute('aria-hidden')}));
 for(const {element} of background){element.inert=true;element.setAttribute('aria-hidden','true');}
 renderPhoto();
 try{
  historyToken='photo-'+Date.now()+'-'+Math.random().toString(36).slice(2);
  const state=history.state&&typeof history.state==='object'&&!Array.isArray(history.state)?history.state:{};
  history.pushState({...state,[HISTORY_KEY]:historyToken},'',location.href);
 }catch(error){historyToken=null;}
 return true;
}
function close(options={}){
 if(!isOpen())return false;
 const sync=options.returnToDetail!==false;
 const consume=historyToken&&history.state?.[HISTORY_KEY]===historyToken&&!options.fromHistory;
 viewer.classList.remove('open');viewer.hidden=true;viewer.setAttribute('aria-hidden','true');
 document.body.classList.remove('ca-photo-viewer-open');
 pointers.clear();gesture=null;lastTap=null;ready=false;
 for(const {element,inert,aria} of background){
  if(!element.isConnected)continue;
  element.inert=Boolean(inert);if(aria===null)element.removeAttribute('aria-hidden');else element.setAttribute('aria-hidden',aria);
 }
 background=[];
 const detailOpen=document.getElementById('detailOverlay')?.classList.contains('open');
 if(sync&&detailOpen&&activeDetailCar===detailCar&&detailPhotos[index]?.src===photos[index]?.src)setDetailPhoto(index);
 document.body.style.overflow=detailOpen?'hidden':previousOverflow;
 if(sync){
  const target=previousFocus?.isConnected?previousFocus:document.querySelector('#galleryStage .ca-gallery-open');
  if(target&&!target.closest('[inert]'))target.focus({preventScroll:true});
 }
 canvas.replaceChildren();photos=[];detailCar=null;previousFocus=null;historyToken=null;
 if(consume){backPending=true;history.back();}
 return true;
}

function startGesture(){
 const values=[...pointers.values()];
 if(values.length>=2){
  const [a,b]=values;
  gesture={kind:'pinch',startScale:scale,startPanX:panX,startPanY:panY,distance:Math.hypot(b.x-a.x,b.y-a.y),midX:(a.x+b.x)/2,midY:(a.y+b.y)/2,hadPinch:true};
 }else if(values.length===1){
  const point=values[0];
  gesture={kind:scale>1.001?'pan':'swipe',x:point.x,y:point.y,startPanX:panX,startPanY:panY,startScale:scale,hadPinch:Boolean(gesture?.hadPinch)};
 }
}
function pointerDown(event){
 if(!isOpen()||!ready||event.target.closest('button')||event.button>0)return;
 pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
 try{stage.setPointerCapture(event.pointerId);}catch(error){}
 if(pointers.size===1)gesture=null;
 startGesture();
}
function pointerMove(event){
 if(!pointers.has(event.pointerId)||!gesture)return;
 pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
 if(gesture.kind==='pinch'&&pointers.size>=2){
  const [a,b]=[...pointers.values()],rect=stage.getBoundingClientRect();
  const next=clamp(gesture.startScale*Math.hypot(b.x-a.x,b.y-a.y)/Math.max(1,gesture.distance),1,4),ratio=next/gesture.startScale;
  panX=(a.x+b.x)/2-rect.left-rect.width/2-(gesture.midX-rect.left-rect.width/2-gesture.startPanX)*ratio;
  panY=(a.y+b.y)/2-rect.top-rect.height/2-(gesture.midY-rect.top-rect.height/2-gesture.startPanY)*ratio;
  scale=next;renderTransform();
 }else if(gesture.kind==='pan'){
  panX=gesture.startPanX+event.clientX-gesture.x;panY=gesture.startPanY+event.clientY-gesture.y;renderTransform();
 }
}
function pointerUp(event){
 if(!pointers.has(event.pointerId))return;
 const completed=gesture;
 pointers.delete(event.pointerId);
 if(pointers.size){startGesture();return;}
 gesture=null;
 if(!completed||completed.hadPinch)return;
 const dx=event.clientX-completed.x,dy=event.clientY-completed.y;
 if(completed.kind==='swipe'&&Math.abs(dx)>45&&Math.abs(dx)>Math.abs(dy)*1.2){change(dx<0?1:-1);return;}
 if(event.pointerType==='touch'&&Math.hypot(dx,dy)<12){
  const now=performance.now();
  if(lastTap&&now-lastTap.time<320&&Math.hypot(lastTap.x-event.clientX,lastTap.y-event.clientY)<30){lastTap=null;lastTouchZoom=now;toggleZoom(event.clientX,event.clientY);}
  else lastTap={time:now,x:event.clientX,y:event.clientY};
 }
}
function cancelPointer(event){
 if(!pointers.has(event.pointerId))return;
 pointers.delete(event.pointerId);if(pointers.size)startGesture();else gesture=null;
}
document.addEventListener('keydown',event=>{
 if(!isOpen())return;
 if(event.altKey||event.ctrlKey||event.metaKey)return;
 if(event.key==='Tab'){
  const buttons=[...viewer.querySelectorAll('button:not([disabled]):not([hidden])')].filter(button=>button.getClientRects().length);
  const first=buttons[0],last=buttons[buttons.length-1];
  if(!viewer.contains(document.activeElement)||event.shiftKey&&document.activeElement===first||!event.shiftKey&&document.activeElement===last){event.preventDefault();(event.shiftKey?last:first)?.focus();}
  event.stopImmediatePropagation();return;
 }
 const action=({'Escape':()=>close(),'ArrowRight':()=>change(1),'ArrowLeft':()=>change(-1),'+':()=>zoomTo(scale+.5),'=':()=>zoomTo(scale+.5),'-':()=>zoomTo(scale-.5),'0':()=>zoomTo(1)})[event.key];
 if(action){event.preventDefault();event.stopImmediatePropagation();action();}
},true);
window.addEventListener('popstate',()=>{
 const wasPending=backPending;backPending=false;
 if(isOpen()&&history.state?.[HISTORY_KEY]!==historyToken)close({fromHistory:true});
 if(wasPending&&queuedOpen){queuedOpen=false;requestAnimationFrame(open);}
});
window.addEventListener('resize',measure,{passive:true});
window.visualViewport?.addEventListener('resize',measure,{passive:true});
window.caOpenPhotoViewer=open;window.caClosePhotoViewer=close;window.caPhotoViewerIsOpen=isOpen;
})();
