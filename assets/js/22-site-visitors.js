// Counts a random browser identifier once per server-defined Baku day.
// No account, phone, URL, IP address or fingerprint is sent by this script.
(()=>{
 'use strict';
 const API='https://iqdtehqxusfiwokrzceo.supabase.co/rest/v1/rpc/';
 const KEY='sb_publishable_i2YE7Nk-XcmmSQVi5-5_Tg_VAx1fSo7';
 const STATE='avtounvan.siteVisitor.v1',ZONE='Asia/Baku';
 const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
 const DAY=/^\d{4}-\d{2}-\d{2}$/;
 let pending=null,lastRead=-Infinity,lastAttempt=-Infinity,shownDay='',controller=null;
 const targets=()=>[...document.querySelectorAll('[data-ca-daily-visitors]')];
 function today(){
  try{
   const parts=new Intl.DateTimeFormat('en',{timeZone:ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
   const get=name=>parts.find(p=>p.type===name).value;return get('year')+'-'+get('month')+'-'+get('day');
  }catch{return new Date(Date.now()+14400000).toISOString().slice(0,10);}
 }
 function randomId(){
  if(globalThis.crypto?.randomUUID)return crypto.randomUUID();
  if(!globalThis.crypto?.getRandomValues)return null;
  const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const hex=[...bytes].map(n=>n.toString(16).padStart(2,'0')).join('');
  return hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);
 }
 function identity(){
  for(const name of ['localStorage','sessionStorage']){
   try{
    const storage=window[name];let state;
    try{state=JSON.parse(storage.getItem(STATE)||'null');}catch{state=null;}
    if(!state||!UUID.test(state.visitor||'')){
     const visitor=randomId();if(!visitor)continue;
     state={visitor,recordedDay:''};storage.setItem(STATE,JSON.stringify(state));
    }
    return {storage,state:{visitor:state.visitor,recordedDay:DAY.test(state.recordedDay||'')?state.recordedDay:''}};
   }catch{}
  }
  return null;
 }
 function render(data){
  for(const element of targets()){
   element.textContent=new Intl.NumberFormat('az-AZ').format(data.visitors);
   const container=element.closest('.ca-site-visitors')||element;
   container.dataset.state='ready';container.dataset.day=data.day;
   container.setAttribute('aria-busy','false');
   container.title='Bakı vaxtı ilə gün ərzində eyni brauzer bir dəfə sayılır. Göstərici təxminidir.';
  }
  shownDay=data.day;
 }
 function unavailable(){
  for(const element of targets()){
   const container=element.closest('.ca-site-visitors')||element;
   if(shownDay!==today())element.textContent='—';
   container.dataset.state='unavailable';container.setAttribute('aria-busy','false');
   container.title='Ziyarətçi sayı hazırda yenilənə bilmir.';
  }
 }
 async function request(name,body){
  controller=new AbortController();const timer=setTimeout(()=>controller?.abort(),8000);
  try{
   const response=await fetch(API+name,{method:'POST',headers:{apikey:KEY,'Content-Type':'application/json'},
    body:JSON.stringify(body),credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',signal:controller.signal});
   if(!response.ok)throw Error('Visitor statistic unavailable');
   const data=await response.json();
   if(!data||!DAY.test(data.day||'')||data.timezone!==ZONE||!Number.isSafeInteger(data.visitors)||data.visitors<0)throw Error('Invalid visitor statistic');
   return data;
  }finally{clearTimeout(timer);controller=null;}
 }
 async function update(){
  const owner=identity(),current=today();
  if(owner&&owner.state.recordedDay!==current){
   const data=await request('ca_record_site_visit',{p_visitor:owner.state.visitor});
   if(typeof data.counted!=='boolean')throw Error('Invalid visit receipt');
   owner.state.recordedDay=data.day;
   try{owner.storage.setItem(STATE,JSON.stringify(owner.state));}catch{}
   render(data);lastRead=performance.now();return;
  }
  if(targets().length){
   const data=await request('ca_daily_site_visitors',{});render(data);lastRead=performance.now();
  }
 }
 function sync(force=false){
  if(document.visibilityState==='hidden'||pending)return pending;
  if(!force&&performance.now()-lastAttempt<60000)return;
  lastAttempt=performance.now();
  pending=Promise.resolve().then(()=>{
   if(!navigator.locks?.request)return update();
   return navigator.locks.request(STATE,update).catch(error=>{
    if(error.name==='SecurityError'||error.name==='NotSupportedError')return update();
    throw error;
   });
  })
   .catch(unavailable).finally(()=>{pending=null;});
  return pending;
 }
 function start(){
  sync(true);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState!=='hidden')sync(true);});
  window.addEventListener('pageshow',event=>{if(event.persisted)sync(true);});
  window.addEventListener('pagehide',()=>controller?.abort());
  setInterval(()=>{
   if(document.visibilityState==='hidden')return;
   const owner=identity();
   if((owner&&owner.state.recordedDay!==today())||(targets().length&&performance.now()-lastRead>=300000))sync();
  },60000);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
