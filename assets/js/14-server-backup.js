/* Admin-only application backup: server rows and every listing-bucket object.
   Credentials are never copied into the archive. No server data is modified. */
(function(){
'use strict';
const RESOURCE_NAMES=['elanlar','paket_sorgulari','profiller','adminler','storage_objects'];
const encoder=new TextEncoder(),HEX=/^[0-9a-f]{64}$/i,UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const BLOB_LIMIT=512*1024*1024,ZIP_LIMIT=0xffffffff;
let prepared=null,viewOwner=null,viewSequence=0,validation=null,job=null,downloadUrl=null;
const el=id=>document.getElementById(id);
const ownerNow=()=>typeof currentUser!=='undefined'?currentUser?.id:null;
const bytes=value=>typeof value==='string'?encoder.encode(value):value;
const digest=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes(value)))].map(n=>n.toString(16).padStart(2,'0')).join('');
const abortError=()=>new DOMException('Əməliyyat dayandırıldı.','AbortError');
function status(text,error=false){const node=el('caServerBackupStatus');if(node){node.textContent=text;node.setAttribute('role',error?'alert':'status');}}
function progress(completed,total){const node=el('caServerBackupProgress');if(node){node.max=Math.max(1,total);node.value=completed;node.hidden=false;}}
function sameOwner(owner){if(!owner||ownerNow()!==owner)throw abortError();}
function guard(current){sameOwner(current.owner);if(job!==current||current.controller.signal.aborted)throw abortError();}
function normalizeManifest(value){
 if(!value||value.version!==1||!Array.isArray(value.resources)||value.resources.length!==RESOURCE_NAMES.length)throw Error('Server nüsxə siyahısını düzgün qaytarmadı.');
 const entries=value.resources.map(item=>{
  if(!item||!RESOURCE_NAMES.includes(item.name)||!Number.isSafeInteger(item.count)||item.count<0||!HEX.test(item.sha256||''))throw Error('Server nüsxə məlumatları natamamdır.');
  return {name:item.name,count:item.count,sha256:item.sha256.toLowerCase()};
 });
 if(new Set(entries.map(item=>item.name)).size!==RESOURCE_NAMES.length)throw Error('Nüsxədə cədvəl çatışmır.');
 return {version:1,resources:RESOURCE_NAMES.map(name=>entries.find(item=>item.name===name))};
}
const signature=manifest=>JSON.stringify(manifest);
async function rpc(name,body,owner,signal){
 sameOwner(owner);const token=await caToken();sameOwner(owner);
 if(!token)throw Error('Sessiya bitib. Hesabına yenidən daxil ol.');
 return caRequest('/rest/v1/rpc/'+name,'POST',body,token,{},signal);
}
function releaseDownload(){if(downloadUrl){URL.revokeObjectURL(downloadUrl);downloadUrl=null;}}
function cancel(message='Nüsxənin hazırlanması dayandırıldı.'){
 validation?.abort();validation=null;viewSequence++;
 const current=job;if(current){current.controller.abort();current.sink?.abort?.().catch(()=>{});clearInterval(current.ownerWatch);job=null;}
 if(el('caServerBackupStart')){el('caServerBackupStart').disabled=!prepared;el('caServerBackupCancel').hidden=true;}
 if(current)status(message);
}
window.caCancelServerBackup=cancel;
window.caServerBackupSessionChanged=function(){
 if(viewOwner&&ownerNow()!==viewOwner){prepared=null;cancel('Hesab dəyişdi. Nüsxə dayandırıldı.');releaseDownload();if(el('caServerBackupStart'))el('caServerBackupStart').disabled=true;}
};

// A small ZIP STORE writer. Streaming output commits only after verification;
// the Blob fallback keeps a clear memory limit rather than omitting any file.
const crcTable=Uint32Array.from({length:256},(_,index)=>{let value=index;for(let bit=0;bit<8;bit++)value=value&1?0xedb88320^(value>>>1):value>>>1;return value>>>0;});
function crc32(data){let value=0xffffffff;for(const byte of data)value=crcTable[(value^byte)&255]^(value>>>8);return (value^0xffffffff)>>>0;}
function zipTime(){const date=new Date(),year=Math.max(1980,date.getFullYear());return {time:(date.getHours()<<11)|(date.getMinutes()<<5)|(date.getSeconds()>>1),date:((year-1980)<<9)|((date.getMonth()+1)<<5)|date.getDate()};}
function zipWriter(sink,streaming){
 let offset=0,closed=false;const central=[];
 async function write(data){if(closed)throw abortError();if(offset+data.byteLength>ZIP_LIMIT)throw Error('Nüsxə ZIP formatının 4 GB həddini keçir. Server səviyyəsində nüsxə al.');if(!streaming&&offset+data.byteLength>BLOB_LIMIT)throw Error('Nüsxə bu brauzerin 512 MB yaddaş həddini keçir. Fayla birbaşa yazmanı dəstəkləyən kompüter brauzerindən istifadə et.');await sink.write(data);offset+=data.byteLength;}
 return {
  async add(name,input){
   if(!/^(?:data|photos)\/[a-zA-Z0-9_./-]+$/.test(name)&&name!=='manifest.json')throw Error('Nüsxə faylının adı düzgün deyil.');
   if(name.split('/').some(part=>part==='..'||part===''))throw Error('Nüsxə yolu düzgün deyil.');
   const data=bytes(input),filename=encoder.encode(name),stamp=zipTime(),crc=crc32(data),start=offset;
   if(filename.length>65535||data.byteLength>ZIP_LIMIT)throw Error('Nüsxə faylı ZIP həddini keçir.');
   const local=new Uint8Array(30+filename.length),view=new DataView(local.buffer);
   view.setUint32(0,0x04034b50,true);view.setUint16(4,20,true);view.setUint16(6,0x0800,true);view.setUint16(8,0,true);view.setUint16(10,stamp.time,true);view.setUint16(12,stamp.date,true);view.setUint32(14,crc,true);view.setUint32(18,data.byteLength,true);view.setUint32(22,data.byteLength,true);view.setUint16(26,filename.length,true);local.set(filename,30);
   await write(local);await write(data);
   const entry=new Uint8Array(46+filename.length),header=new DataView(entry.buffer);
   header.setUint32(0,0x02014b50,true);header.setUint16(4,20,true);header.setUint16(6,20,true);header.setUint16(8,0x0800,true);header.setUint16(10,0,true);header.setUint16(12,stamp.time,true);header.setUint16(14,stamp.date,true);header.setUint32(16,crc,true);header.setUint32(20,data.byteLength,true);header.setUint32(24,data.byteLength,true);header.setUint16(28,filename.length,true);header.setUint32(42,start,true);entry.set(filename,46);central.push(entry);
   if(central.length>65535)throw Error('Nüsxədə ZIP həddindən çox fayl var. Server səviyyəsində nüsxə al.');
   return {path:name,bytes:data.byteLength,sha256:await digest(data)};
  },
  async finish(){
   const start=offset;for(const entry of central)await write(entry);const length=offset-start;
   const end=new Uint8Array(22),view=new DataView(end.buffer);view.setUint32(0,0x06054b50,true);view.setUint16(8,central.length,true);view.setUint16(10,central.length,true);view.setUint32(12,length,true);view.setUint32(16,start,true);await write(end);await sink.close();closed=true;
  },
  async abort(){closed=true;await sink.abort?.();}
 };
}
function blobSink(){const chunks=[];let blob=null;return {async write(data){chunks.push(data);},async close(){blob=new Blob(chunks,{type:'application/zip'});chunks.length=0;},async abort(){chunks.length=0;blob=null;},getBlob(){return blob;}};}
function photoArchiveName(item){
 if(!UUID.test(item.id||''))throw Error('Şəkil identifikatoru düzgün deyil.');
 const mime=String(item.metadata?.mimetype||item.metadata?.contentType||'').toLowerCase();
 const extensions={'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/avif':'avif','image/gif':'gif','image/svg+xml':'svg','image/heic':'heic'};
 return 'photos/'+item.id+'.'+(extensions[mime]||'bin');
}
function photoUrl(item){
 if(typeof item.name!=='string'||!item.name||item.name.includes('\\')||item.name.includes('\0')||item.name.split('/').some(part=>!part||part==='.'||part==='..'))throw Error('Şəklin saxlanma yolu düzgün deyil.');
 if(item.bucket_id&&item.bucket_id!=='elan-sekilleri')throw Error('Gözlənilməyən şəkil qovluğu.');
 return CA_URL+'/storage/v1/object/public/elan-sekilleri/'+item.name.split('/').map(encodeURIComponent).join('/');
}
async function exportServer(){
 if(job||!prepared||!viewOwner)return;
 const owner=viewOwner,initial=prepared,sequence=viewSequence;
 const current={owner,controller:new AbortController(),sink:null,writer:null,ownerWatch:null};job=current;
 el('caServerBackupStart').disabled=true;el('caServerBackupCancel').hidden=false;
 status('Nüsxə hazırlanır…');progress(0,1);
 current.ownerWatch=setInterval(()=>{if(ownerNow()!==owner)window.caServerBackupSessionChanged();},200);
 let sink,streaming=false;
 const filename='Cenub_Avto_server_'+new Date().toISOString().replace(/[:.]/g,'-')+'.zip';
 try{
  // Called directly from the user's click, preserving the browser activation.
  const selection=typeof window.showSaveFilePicker==='function'?window.showSaveFilePicker({suggestedName:filename,types:[{description:'ZIP ehtiyat nüsxəsi',accept:{'application/zip':['.zip']}}]}):null;
  if(selection){const handle=await selection;guard(current);sink=await handle.createWritable();streaming=true;}
  else sink=blobSink();
  current.sink=sink;guard(current);current.writer=zipWriter(sink,streaming);
  const fresh=normalizeManifest(await rpc('ca_admin_export_manifest',{},owner,current.controller.signal));guard(current);
  if(signature(fresh)!==signature(initial))throw Error('Server məlumatları dəyişib. Siyahını yeniləyib nüsxəni yenidən başlat.');
  const totalRows=initial.resources.reduce((sum,item)=>sum+item.count,0),totalPhotos=initial.resources.find(item=>item.name==='storage_objects').count;
  let completedRows=0,completedPhotos=0;const files=[],resources=[],photos=[];
  const update=()=>{status('Məlumatlar: '+completedRows+' / '+totalRows+' · Şəkillər: '+completedPhotos+' / '+totalPhotos);progress(completedRows+completedPhotos,totalRows+totalPhotos);};update();
  for(const resource of initial.resources){
   let cursor=null,pageNumber=0,count=0;const hashes=[],cursors=new Set(),seenHashes=new Set(),pages=[];
   if(resource.count){do{
    guard(current);const page=await rpc('ca_admin_export_page',{p_resource:resource.name,p_cursor:cursor,p_page_size:100},owner,current.controller.signal);guard(current);
    if(!page||!Array.isArray(page.items)||!Array.isArray(page.hashes)||page.items.length!==page.hashes.length||page.items.length>100||page.items.some(item=>!item||typeof item!=='object'||Array.isArray(item))||page.hashes.some(hash=>!HEX.test(hash||'')))throw Error('Server nüsxə səhifəsini natamam qaytardı.');
    if(page.next_cursor!==null&&page.next_cursor!==undefined&&!UUID.test(page.next_cursor))throw Error('Nüsxə səhifəsinin keçidi düzgün deyil.');
    if(!page.items.length&&page.next_cursor)throw Error('Nüsxədə boş səhifə keçidi alındı.');
    for(const hash of page.hashes){if(seenHashes.has(hash))throw Error('Nüsxədə təkrar sətir alındı.');seenHashes.add(hash);hashes.push(hash.toLowerCase());}
    count+=page.items.length;if(count>resource.count)throw Error('Nüsxənin sətir sayı dəyişib. Yenidən başlat.');
    if(page.items.length){
     const path='data/'+resource.name+'/'+String(++pageNumber).padStart(6,'0')+'.json';
     const file=await current.writer.add(path,JSON.stringify({resource:resource.name,items:page.items,hashes:page.hashes},null,2));guard(current);files.push(file);pages.push(path);
     if(resource.name==='storage_objects')photos.push(...page.items);
    }
    completedRows+=page.items.length;update();
    cursor=page.next_cursor||null;if(cursor){if(cursors.has(cursor))throw Error('Nüsxə səhifəsi təkrarlanır.');cursors.add(cursor);}
   }while(cursor);}
   if(count!==resource.count||await digest(hashes.join(''))!==resource.sha256)throw Error('Nüsxənin bütövlüyü təsdiqlənmədi. Server məlumatları dəyişmiş ola bilər.');
   resources.push({...resource,pages});
  }
  const photoFiles=[];
  for(const item of photos){
   guard(current);const response=await fetch(photoUrl(item),{method:'GET',signal:current.controller.signal,cache:'no-store',credentials:'omit'});guard(current);
   if(!response.ok)throw Error('Şəkil yüklənmədi ('+response.status+'). Tam nüsxə yaradılmadı.');
   const data=new Uint8Array(await response.arrayBuffer());guard(current);
   const expected=Number(item.metadata?.size??item.metadata?.contentLength);
   if(Number.isFinite(expected)&&expected>=0&&data.byteLength!==expected)throw Error('Şəklin ölçüsü server məlumatına uyğun gəlmir. Tam nüsxə yaradılmadı.');
   const file=await current.writer.add(photoArchiveName(item),data);guard(current);files.push(file);photoFiles.push({...file,id:item.id,originalName:item.name});completedPhotos++;update();
  }
  const final=normalizeManifest(await rpc('ca_admin_export_manifest',{},owner,current.controller.signal));guard(current);
  if(signature(final)!==signature(initial))throw Error('Nüsxə hazırlanarkən server məlumatları dəyişdi. Tam nüsxə üçün yenidən başlat.');
  const manifest={format:'cenub-avto-server-data-backup',version:1,created:new Date().toISOString(),scope:'application tables and all elan-sekilleri bucket objects; excludes Auth secrets and server configuration',resources,files,photos:photoFiles};
  await current.writer.add('manifest.json',JSON.stringify(manifest,null,2));guard(current);
  await current.writer.finish();guard(current);
  if(!streaming){
   const blob=sink.getBlob();if(!blob)throw Error('Nüsxə faylı hazırlanmadı.');releaseDownload();downloadUrl=URL.createObjectURL(blob);
   const anchor=document.createElement('a');anchor.href=downloadUrl;anchor.download=filename;document.body.appendChild(anchor);guard(current);anchor.click();anchor.remove();setTimeout(releaseDownload,60000);
  }
  clearInterval(current.ownerWatch);job=null;prepared=null;
  status('Tam nüsxə hazırdır: '+totalRows+' məlumat sətri və '+totalPhotos+' şəkil. Faylı təhlükəsiz yerdə saxla.');progress(totalRows+totalPhotos,totalRows+totalPhotos);el('caServerBackupStart').disabled=true;el('caServerBackupCancel').hidden=true;
 }catch(error){
  await current.writer?.abort().catch(()=>{});if(!current.writer)await sink?.abort?.().catch(()=>{});
  clearInterval(current.ownerWatch);
  if(job===current){job=null;prepared=null;if(viewSequence===sequence&&ownerNow()===owner){status(error.name==='AbortError'?'Nüsxə dayandırıldı; tamamlanmış fayl yaradılmadı.':'Nüsxə yaradılmadı: '+error.message,error.name!=='AbortError');if(el('caServerBackupStart'))el('caServerBackupStart').disabled=true;if(el('caServerBackupCancel'))el('caServerBackupCancel').hidden=true;}}
 }
}
window.caShowServerBackup=async function(){
 cancel();prepared=null;viewOwner=ownerNow();const owner=viewOwner,sequence=++viewSequence;
 const overlay=el('caOverlay'),body=el('caDialogBody');if(!overlay||!body)return;
 el('caDialogTitle').textContent='Server məlumatlarının ehtiyat nüsxəsi';
 body.innerHTML='<section id="caServerBackup"><p>ZIP faylı elanları, paket sorğularını, profilləri, admin siyahısını və bütün elan şəkillərini saxlayır. Giriş parolları və server ayarları daxil deyil.</p><p>Faylda şəxsi məlumatlar var; yalnız təhlükəsiz yerdə saxla.</p><p id="caServerBackupStatus" role="status" aria-live="polite"></p><progress id="caServerBackupProgress" hidden></progress><div class="ca-actions"><button type="button" class="ca-tool" id="caServerBackupStart" disabled>ZIP nüsxəsini hazırla</button><button type="button" class="ca-tool" id="caServerBackupCancel" hidden>Dayandır</button><button type="button" class="ca-tool" id="caServerBackupRefresh">Yenilə</button></div></section>';
 overlay.classList.add('ca-open');el('caServerBackupStart').addEventListener('click',exportServer);el('caServerBackupCancel').addEventListener('click',()=>cancel());el('caServerBackupRefresh').addEventListener('click',window.caShowServerBackup);
 if(!owner){status('Server nüsxəsini yalnız daxil olmuş sayt admini yarada bilər.');return;}
 validation=new AbortController();status('Admin girişi və server məlumatları yoxlanılır…');
 try{
  const manifest=normalizeManifest(await rpc('ca_admin_export_manifest',{},owner,validation.signal));sameOwner(owner);
  if(sequence!==viewSequence||!el('caServerBackup')||!overlay.classList.contains('ca-open'))return;
  prepared=manifest;const total=manifest.resources.reduce((sum,item)=>sum+item.count,0),photos=manifest.resources.find(item=>item.name==='storage_objects').count;
  status(total+' məlumat sətri və '+photos+' şəkil nüsxələnəcək.');el('caServerBackupStart').disabled=false;el('caServerBackupStart').focus({preventScroll:true});
 }catch(error){if(sequence===viewSequence&&ownerNow()===owner)status(error.name==='AbortError'?'Yoxlama dayandırıldı.':'Admin girişi təsdiqlənmədi və ya server nüsxə xidməti əlçatan deyil.',true);}
};
const overlay=el('caOverlay'),dialog=el('caDialogBody');
if(typeof MutationObserver==='function'&&overlay&&dialog){const observer=new MutationObserver(()=>{if((job||validation)&&(!overlay.classList.contains('ca-open')||!el('caServerBackup')))cancel();});observer.observe(overlay,{attributes:true,attributeFilter:['class']});observer.observe(dialog,{childList:true});}
})();
