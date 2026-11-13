/* A trusted server reviews new photos when enabled. A disabled service keeps
   the existing admin moderation flow; errors never silently skip an active gate. */
(function(){
'use strict';
if(window.caReviewPreparedPhoto)return;
const categories={
 front:{label:'Ön görünüş',guide:'Ön tərəf, faralar və radiator barmaqlığı aydın görünsün.'},
 rear:{label:'Arxa görünüş',guide:'Arxa tərəf, arxa işıqlar və baqaj hissəsi aydın görünsün.'},
 side:{label:'Yan görünüş',guide:'Avtomobilin sağ və ya sol yan tərəfi görünsün.'},
 interior:{label:'Salon',guide:'Salon, oturacaqlar və ya idarəetmə paneli görünsün.'},
 engine:{label:'Mühərrik',guide:'Açıq kapot altında mühərrik hissəsi görünsün.'},
 other:{label:'Digər şəkillər',guide:'Avtomobilə aid təkər, detal və digər yaxın görünüşlər əlavə et.'}
};
const endpoint=CA_URL.replace(/\/$/,'')+'/functions/v1/ca-photo-review';
let cached=null,pending=null,epoch=0,sessionOwner=currentUser?.id||null,mode=null,precheck=null,available=false;
const groupStates=new Map();
function stale(owner,submission){return !owner||currentUser?.id!==owner||submission!==undefined&&submission!==null&&caListingSubmissionSequence!==submission;}
function assertCurrent(owner,submission){if(stale(owner,submission)){const error=Error('Hesab və ya elan forması dəyişib. Şəkil yoxlaması dayandırıldı.');error.code='photo_review_stale';throw error;}}
function note(text,state){const el=document.getElementById('caPhotoReviewNote');if(el){el.textContent=text;el.dataset.reviewMode=state;}}
function group(category){return document.getElementById('caPhotoReview-'+category);}
function clearGroup(category){groupStates.delete(category);const el=group(category);if(el){el.textContent='';el.setAttribute('role','status');el.setAttribute('aria-live','polite');el.dataset.reviewState='';}document.getElementById('photos-'+category)?.removeAttribute('aria-invalid');}
function drawGroup(category){
 const state=groupStates.get(category),el=group(category);if(!state||!el)return;
 const error=Boolean(state.error);el.setAttribute('role',error?'alert':'status');el.setAttribute('aria-live',error?'assertive':'polite');el.dataset.reviewState=error?'error':state.checking?'checking':'approved';
 el.textContent=state.error||(state.checking?'Şəkil yoxlanır…':state.approved+' şəkil yoxlamadan keçdi.');
 const input=document.getElementById('photos-'+category);if(input){if(error)input.setAttribute('aria-invalid','true');else input.removeAttribute('aria-invalid');}
}
function syncPrecheck(){
 const button=document.getElementById('caPhotoPrecheck'),form=document.getElementById('listingForm');if(!button)return;
 const busy=Boolean(precheck&&!stale(precheck.owner,precheck.submission))||form?.getAttribute('aria-busy')==='true'||Boolean(document.getElementById('submitListingBtn')?.disabled);
 button.hidden=!available;button.disabled=!available||busy;
 const label=precheck&&!stale(precheck.owner,precheck.submission)?'Şəkillər yoxlanır…':'Şəkilləri yoxla';if(button.textContent!==label)button.textContent=label;
}
function precheckMessage(text,error=false){const el=document.getElementById('caPhotoPrecheckResult');if(el){el.textContent=text;el.setAttribute('role',error?'alert':'status');el.setAttribute('aria-live',error?'assertive':'polite');}}
function setMode(status){
 available=status.enabled&&status.configured;syncPrecheck();
 const next=status.enabled?'automatic':'manual';
 if(mode!==null&&next!==mode){window.caPhotoReviewModeChanged?.();for(const category of Object.keys(categories))clearGroup(category);}
 mode=next;
 if(!status.enabled)note('Şəkillər admin tərəfindən yoxlanacaq. Ekran görüntüsü, reklam və avtomobilə aid olmayan şəkillər qəbul edilmir.','manual');
 else if(!status.configured)note('Şəkil yoxlaması hazırda mümkün deyil. Bir qədər sonra yenidən yoxla.','unavailable');
 else note('Şəkillər göndəriş zamanı avtomatik yoxlanacaq. Hər şəkil seçilən bölməyə uyğun olmalıdır; ekran görüntüsü və avtomobilə aid olmayan şəkil əlavə etmə.','automatic');
}
async function jsonRequest(url,options,timeout){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
 try{
  const response=await fetch(url,{...options,signal:controller.signal});let data;
  try{data=await response.json();}catch(error){const failure=Error('Şəkil yoxlamasının cavabı oxunmadı. Yenidən yoxla.');failure.code='invalid_review_response';throw failure;}
  if(!response.ok){const failure=Error('Şəkil yoxlaması tamamlanmadı.');failure.code=typeof data?.code==='string'?data.code:response.status===429?'rate_limited':response.status===401?'auth_required':'provider_unavailable';failure.status=response.status;throw failure;}
  return data;
 }catch(error){
  if(typeof error.code==='string'&&error.code)throw error;
  const failure=Error('Şəkil yoxlamasına qoşulmaq olmadı. İnternet bağlantını yoxlayıb yenidən cəhd et.');failure.code='review_connection_failed';throw failure;
 }finally{clearTimeout(timer);}
}
async function statusFor(owner,token){
 if(currentUser?.id!==sessionOwner)window.caPhotoReviewSessionChanged();
 assertCurrent(owner);if(!token)throw Error('Şəkil əlavə etmək üçün hesabına daxil ol.');
 if(cached?.owner===owner&&cached.until>Date.now())return cached.value;
 if(pending?.owner===owner)return pending.promise;
 const generation=epoch;
 const promise=(async()=>{
  const value=await jsonRequest(endpoint+'/status',{method:'GET',headers:{apikey:CA_KEY,Authorization:'Bearer '+token}},12000);
  assertCurrent(owner);if(generation!==epoch)throw Error('Hesab sessiyası dəyişib. Yenidən yoxla.');
  if(typeof value?.enabled!=='boolean'||typeof value.configured!=='boolean'){const error=Error('Şəkil yoxlamasının vəziyyəti təsdiqlənmədi. Yenidən yoxla.');error.code='invalid_review_response';throw error;}
  const clean={enabled:value.enabled,configured:value.configured};cached={owner,value:clean,until:Date.now()+10000};setMode(clean);return clean;
 })();
 const holder={owner,promise};pending=holder;
 try{return await promise;}finally{if(pending===holder)pending=null;}
}
function humanError(error,category,fileName){
 const item=categories[category],prefix=(item?.label||'Şəkil')+(fileName?' — '+String(fileName).slice(0,140):'')+': ';
 const messages={
  screenshot:'Ekran görüntüsü və ya üzərində tətbiq/sayt interfeysi olan şəkil qəbul edilmir. Avtomobilin öz fotosunu seç.',
  not_vehicle:'Şəkildə avtomobil və ya ona aid hissə görünmür. Avtomobilin uyğun fotosunu seç.',
  category_mismatch:'Şəkil bu bölməyə uyğun deyil. '+(item?.guide||'Uyğun bölməni seç.'),
  uncertain:'Şəklin uyğunluğu aydın deyil. Avtomobili daha aydın göstərən foto seç.',
  rate_limited:'Çox şəkil yoxlaması göndərilib. Bir qədər gözləyib yenidən yoxla.',
  provider_quota:'Şəkil tanıma xidmətinin limiti dolub. Şəkillərin formadadır; bir qədər sonra yenidən yoxla.',
  provider_denied:'Şəkil tanıma xidmətinə giriş təsdiqlənmədi. Şəkillərin formadadır; dəstək xidməti ilə əlaqə saxla.',
  auth_required:'Sessiya bitib. Hesabına yenidən daxil ol.',
  invalid_image:'Şəkil açıla bilmir və ya uyğun ölçüdə deyil. Başqa foto seç.',
  provider_unavailable:'Şəkil yoxlaması hazırda mümkün deyil. Şəkillərin formadadır; bir qədər sonra yenidən cəhd et.',
  invalid_review_response:'Şəkil yoxlaması təsdiqlənmədi. Yenidən yoxla.'
 };
 return prefix+(messages[error.code]||error.message||messages.provider_unavailable);
}
window.caPhotoReviewBeforeBatch=async function({owner,submission,token}){
 assertCurrent(owner,submission);const status=await statusFor(owner,token);assertCurrent(owner,submission);
 if(status.enabled&&!status.configured){const error=Error('Şəkil yoxlaması hazırda mümkün deyil. Bir qədər sonra yenidən cəhd et.');error.code='provider_unavailable';throw error;}
 return status;
};
window.caReviewPreparedPhoto=async function(blob,{category,owner,submission,token,onProgress,fileName}={}){
 assertCurrent(owner,submission);
 if(!Object.hasOwn(categories,category)){const error=Error('Şəkil üçün uyğun bölmə seç.');error.code='invalid_category';throw error;}
 const status=await window.caPhotoReviewBeforeBatch({owner,submission,token});assertCurrent(owner,submission);
 if(!status.enabled)return null;
 const state=groupStates.get(category)||{checking:0,approved:0,error:''};groupStates.set(category,state);if(!state.checking)state.error='';state.checking++;drawGroup(category);
 try{
  onProgress?.(0);const body=new FormData();body.append('file',blob,'photo.jpg');body.append('category',category);
  const result=await jsonRequest(endpoint,{method:'POST',headers:{apikey:CA_KEY,Authorization:'Bearer '+token},body},60000);
  assertCurrent(owner,submission);
  const id=result?.review_id,validId=typeof id==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
  const expected=CA_URL.replace(/\/$/,'')+'/storage/v1/object/public/elan-sekilleri/'+owner+'/checked/'+id+'-ca-wm1.jpg';
  if(!validId||result.category!==category||result.url!==expected){const error=Error('Şəkil yoxlamasının nəticəsi təsdiqlənmədi.');error.code='invalid_review_response';throw error;}
  state.approved++;onProgress?.(1);return result.url;
 }catch(error){
  if(stale(owner,submission))throw error;
  const message=humanError(error,category,fileName);state.error=message;const failure=Error(message);failure.code=error.code||'photo_review_failed';throw failure;
 }finally{if(!stale(owner,submission)&&groupStates.get(category)===state){state.checking--;drawGroup(category);}}
};
// Review selected new photos without creating or editing an advertisement.
async function precheckPhotos(){
 const form=document.getElementById('listingForm');if(!form||form.getAttribute('aria-busy')==='true'||document.getElementById('submitListingBtn')?.disabled)return false;
 if(!currentUser){requireLogin('sell');return false;}
 const inputs=[...form.querySelectorAll('.photo-input')];
 if(!inputs.some(input=>input.files.length)){precheckMessage('Yoxlamaq üçün ən azı bir yeni avtomobil şəkli seç.',true);return false;}
 const task={owner:currentUser.id,submission:++caListingSubmissionSequence};precheck=task;
 caSetListingFormBusy(form,true);syncPrecheck();precheckMessage('Yeni şəkillər yoxlanır…');
 try{
  const token=await caToken();assertCurrent(task.owner,task.submission);
  const status=await window.caPhotoReviewBeforeBatch({...task,token});assertCurrent(task.owner,task.submission);
  if(!status.enabled){precheckMessage('Şəkillər admin tərəfindən yoxlanacaq.');return false;}
  const photos={};await caUploadSelectedPhotos(inputs,photos);assertCurrent(task.owner,task.submission);
  precheckMessage('Yeni şəkillər yoxlamadan keçdi. Elanı göndərə bilərsən.');return true;
 }catch(error){
  if(stale(task.owner,task.submission))return false;
  const message=[...groupStates.values()].some(state=>state.error===error.message)?error.message:humanError(error);
  precheckMessage(message,true);caShowListingFeedback(message,'error');return false;
 }finally{
  if(precheck===task){precheck=null;if(!stale(task.owner,task.submission))caSetListingFormBusy(form,false);syncPrecheck();}
 }
}
window.caPrecheckPhotos=precheckPhotos;
window.caPhotoReviewSessionChanged=function(){
 const owner=currentUser?.id||null;if(owner===sessionOwner)return;
 sessionOwner=owner;epoch++;cached=null;pending=null;mode=null;precheck=null;available=false;precheckMessage('');syncPrecheck();for(const category of Object.keys(categories))clearGroup(category);
 note('Şəkli uyğun bölməyə əlavə et. Yoxlama vəziyyəti göndəriş zamanı göstəriləcək.','pending');
};
async function refreshNote(){
 const owner=currentUser?.id;if(!owner)return;const submission=caListingSubmissionSequence;
 try{const token=await caToken();if(stale(owner,submission))return;await statusFor(owner,token);}
 catch(error){if(!stale(owner,submission))note('Şəkil yoxlamasının vəziyyəti alınmadı. Göndərişdə yenidən yoxlanacaq.','unavailable');}
}
const inputs=[...document.querySelectorAll('.photo-input')];
if(inputs.length){
 const notice=document.createElement('p');notice.id='caPhotoReviewNote';notice.className='ca-photo-review-note';notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');notice.textContent='Şəkli uyğun bölməyə əlavə et. Yoxlama vəziyyəti göndəriş zamanı göstəriləcək.';
 const groups=document.querySelector('.photo-groups');groups?.before(notice);
 const button=document.createElement('button');button.type='button';button.id='caPhotoPrecheck';button.className='back-btn';button.textContent='Şəkilləri yoxla';button.hidden=true;button.disabled=true;button.addEventListener('click',precheckPhotos);
 const result=document.createElement('p');result.id='caPhotoPrecheckResult';result.className='ca-photo-review-status';result.setAttribute('role','status');result.setAttribute('aria-live','polite');
 groups?.before(button,result);
 for(const input of inputs){
  const category=input.dataset.category,item=categories[category];if(!item)continue;
  const help=document.createElement('p');help.id='caPhotoGuide-'+category;help.className='ca-photo-review-guide';help.textContent=item.guide;
  const status=document.createElement('p');status.id='caPhotoReview-'+category;status.className='ca-photo-review-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  input.before(help);input.after(status);input.setAttribute('aria-describedby',[input.getAttribute('aria-describedby'),help.id,status.id].filter(Boolean).join(' '));
  input.addEventListener('change',()=>{clearGroup(category);precheckMessage('');if(input.files.length)refreshNote();});
 }
 const form=document.getElementById('listingForm');
 form?.addEventListener('reset',()=>{if(precheck&&stale(precheck.owner,precheck.submission))precheck=null;precheckMessage('');for(const category of Object.keys(categories))clearGroup(category);syncPrecheck();});
 if(typeof MutationObserver==='function'){
  if(form)new MutationObserver(syncPrecheck).observe(form,{attributes:true,attributeFilter:['aria-busy']});
  const submit=document.getElementById('submitListingBtn');if(submit)new MutationObserver(syncPrecheck).observe(submit,{attributes:true,attributeFilter:['disabled']});
 }
 if(typeof MutationObserver==='function')new MutationObserver(()=>{window.caPhotoReviewSessionChanged();if(document.body.classList.contains('sell-open'))refreshNote();}).observe(document.body,{attributes:true,attributeFilter:['class']});
 if(document.body.classList.contains('sell-open'))refreshNote();
}
})();
