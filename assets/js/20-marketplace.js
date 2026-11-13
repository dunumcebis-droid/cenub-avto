/* Private seller tools, moderation, saved searches and site-only notifications. */
(function () {
'use strict';
const $ = id => document.getElementById(id);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ownerNow = () => typeof currentUser !== 'undefined' ? currentUser?.id || null : null;
const node = (tag, text, className) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (className) n.className = className; return n; };
const button = (text, action) => { const b = node('button', text); b.type = 'button'; if (action) b.addEventListener('click', action); return b; };
const reasons = {fraud:'Dələduzluq şübhəsi',wrong_info:'Yanlış məlumat',duplicate:'Təkrar elan',inappropriate:'Uyğun olmayan məzmun',other:'Digər'};
let owner = ownerNow(), epoch = 0, modalSequence = 0, modal = null, savedSequence = 0, statsSequence = 0;
let statsCache = new Map(), statsPending = '', savedRows = [], notificationState = null;
let notificationSequence = 0, notificationBusy = false, notificationPage = 1, pollTimer = null, drainTimer = null;
let adminSequence = 0, reportPreviewSequence = 0, adminAuthorized = false, reportPage = 1, reportRows = [], adminOwner = null;
let overlay, content, message, title, close, form, submit, returnFocus, oldOverflow = '';
const validSession = (expected, version = epoch) => !!expected && expected === owner && expected === ownerNow() && version === epoch;
async function rpc(name, body, expected = owner, version = epoch) {
 if (!validSession(expected, version)) throw Error('Hesab dəyişib. Yenidən daxil ol.');
 const token = await caToken();
 if (!token || !validSession(expected, version)) throw Error('Sessiya bitib. Yenidən daxil ol.');
 const result = await caRequest('/rest/v1/rpc/' + name, 'POST', body || {}, token);
 if (!validSession(expected, version)) throw Error('Hesab dəyişib.');
 return result;
}
function showMessage(text, error = false) {
 if (!message) return;
 message.textContent = text;
 message.classList.toggle('ca-market-error', error);
}
function ensureModal() {
 if (overlay) return;
 overlay = node('div', null, 'auth-overlay ca-market-overlay'); overlay.id = 'caMarketOverlay';
 // This dialog can open over listing details (14500), including before feature CSS loads.
 overlay.style.zIndex = '16500';
 overlay.setAttribute('role', 'dialog'); overlay.setAttribute('aria-modal', 'true'); overlay.setAttribute('aria-labelledby', 'caMarketTitle');
 overlay.hidden = true;
 const box = node('div', null, 'auth-box ca-market-box');
 close = button('✕ Bağla', () => closeModal()); close.id = 'caMarketClose'; close.className = 'detail-close ca-market-close';
 title = node('h2'); title.id = 'caMarketTitle';
 content = node('div', null, 'ca-market-content'); content.id = 'caMarketContent';
 message = node('p', '', 'ca-market-message'); message.id = 'caMarketMessage'; message.setAttribute('role', 'status'); message.setAttribute('aria-live', 'polite');
 form = node('form'); form.id = 'caMarketForm';
 submit = node('button'); submit.type = 'submit'; submit.id = 'caMarketSubmit'; submit.className = 'primary';
 form.append(content, message, submit); box.append(close, title, form); overlay.append(box); document.body.append(overlay);
 overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
 form.addEventListener('submit', async e => {
  e.preventDefault(); const context = modal; if (!context || context.busy || !context.onSubmit) return;
  context.busy = true; submit.disabled = true; showMessage('Saxlanılır...');
  try { await context.onSubmit(context); }
  catch (error) { if (modal === context) showMessage(error.message || 'Sorğu alınmadı. Yenidən yoxla.', true); }
  finally { if (modal === context) { context.busy = false; submit.disabled = false; } }
 });
 document.addEventListener('keydown', e => {
  if (!modal) return;
  if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); closeModal(); return; }
  if (e.key !== 'Tab') return;
  const items = [...overlay.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],[tabindex="0"]')].filter(n => !n.hidden && n.getClientRects().length);
  if (!items.length) { e.preventDefault(); close.focus(); return; }
  if (e.shiftKey && (document.activeElement === items[0] || !overlay.contains(document.activeElement))) { e.preventDefault(); items.at(-1).focus(); }
  else if (!e.shiftKey && (document.activeElement === items.at(-1) || !overlay.contains(document.activeElement))) { e.preventDefault(); items[0].focus(); }
 }, true);
 document.addEventListener('focusin', e => { if (modal && !overlay.contains(e.target)) close.focus({preventScroll:true}); });
}
function openModal(kind, heading, submitText, onSubmit) {
 ensureModal();
 if (!modal) { returnFocus = document.activeElement; oldOverflow = document.body.style.overflow; }
 modal = {kind, onSubmit, sequence:++modalSequence, owner, epoch, busy:false};
 title.textContent = heading; content.replaceChildren(); showMessage('');
 submit.textContent = submitText || ''; submit.hidden = !submitText; submit.disabled = false;
 overlay.hidden = false; overlay.classList.add('open'); document.body.classList.add('ca-market-open'); document.body.style.overflow = 'hidden';
 close.focus({preventScroll:true});
 return modal;
}
function closeModal(restore = true) {
 if (!overlay || !modal) return;
 modal = null; modalSequence++; overlay.classList.remove('open'); overlay.hidden = true;
 content.replaceChildren(); showMessage(''); document.body.classList.remove('ca-market-open');
 const underneath = document.querySelector('#detailOverlay.open,.auth-overlay.open:not(#caMarketOverlay),#caPhotoViewer.open');
 document.body.style.overflow = underneath ? 'hidden' : oldOverflow;
 if (restore && returnFocus?.isConnected) returnFocus.focus({preventScroll:true});
 returnFocus = null;
}
function isModal(context) { return context === modal && validSession(context.owner, context.epoch); }
function field(labelText, id, input) {
 const wrap = node('label', null, 'ca-market-field'); wrap.append(node('span', labelText)); input.id = id; wrap.append(input); return wrap;
}
function loginNotice() { if ($('detailOverlay')?.classList.contains('open')) closeCarDetail(); if (typeof openAuth === 'function') openAuth('login'); }
function ownCars() { return ownerNow() && typeof myCars === 'function' ? myCars().filter(c => c.ownerId === ownerNow()) : []; }
function sold(c) { return c?.isSold === true || c?.is_sold === true || c?.status === 'satilib' || c?.veziyyet === 'satilib'; }
function publicCar(c, options = {}) {
 return c && UUID.test(c._id || '') && !sold(c) && (c.veziyyet || c.status) === 'aktiv' && c.ownerId !== ownerNow() && !options.privatePreview && !options.adminPreview;
}
function decorateCabinet() {
 if (!owner) return;
 const cars = ownCars(); const byId = new Map(cars.map(c => [c._id, c]));
 document.querySelectorAll('#cabinetList .cabinet-card[data-listing-id]').forEach(card => {
  const id = card.dataset.listingId, car = byId.get(id); if (!car || !UUID.test(id)) return;
  let stat = card.querySelector('[data-ca-stats]');
  if (!stat) { stat = node('p', 'Statistika yüklənir...', 'ca-listing-stats'); stat.dataset.caStats = id; card.querySelector('.ca-cab-status')?.after(stat); }
  if (statsCache.has(id)) drawStat(stat, statsCache.get(id));
  const actions = card.querySelector('.cab-actions'); if (!actions) return;
  if (sold(car)) {
   card.dataset.caSoldStatus = 'true';
   actions.querySelectorAll('button').forEach(b => {
    if ((b.getAttribute('onclick') || '').startsWith('editCar(') || b.dataset.caSold) b.remove();
    else if ((b.getAttribute('onclick') || '').startsWith('deleteCar(')) b.textContent = 'Arxivlə';
   });
   const status = card.querySelector('.ca-cab-status'); if (status) status.textContent = 'Satılıb · Şəxsi arxiv';
  } else if (!actions.querySelector('[data-ca-sold]')) {
   const b = button('Satılıb', () => confirmSold(id)); b.dataset.caSold = id; actions.append(b);
  }
 });
 loadStats(cars.map(c => c._id).filter(id => UUID.test(id)));
}
function drawStat(element, data) {
 const count = key => Number.isSafeInteger(data?.[key]) && data[key] >= 0 ? data[key].toLocaleString('az-AZ') : '0';
 element.textContent = 'Baxışlar: ' + count('views') + ' · Zəng klikləri: ' + count('contact_clicks');
 element.title = 'Zəng klikləri telefon düyməsinə toxunmaları göstərir; baş tutmuş zəng sayı deyil.';
}
async function loadStats(ids) {
 const missing = [...new Set(ids)].filter(id => !statsCache.has(id)); if (!missing.length) return;
 const key = missing.join(','); if (statsPending === key) return;
 statsPending = key; const expected = owner, version = epoch, sequence = ++statsSequence;
 try {
  for (let start = 0; start < missing.length; start += 100) {
   const batch = missing.slice(start, start + 100);
   const rows = await rpc('ca_my_listing_stats', {p_ids:batch}, expected, version);
   if (!validSession(expected, version) || sequence !== statsSequence) return;
   if (!Array.isArray(rows) || rows.some(row => !batch.includes(row.id))) throw Error('Statistika düzgün gəlmədi.');
   batch.forEach(id => statsCache.set(id, rows.find(row => row.id === id) || {views:0,contact_clicks:0}));
   document.querySelectorAll('[data-ca-stats]').forEach(n => { if (statsCache.has(n.dataset.caStats)) drawStat(n, statsCache.get(n.dataset.caStats)); });
  }
 } catch (error) {
  if (validSession(expected, version) && sequence === statsSequence) document.querySelectorAll('[data-ca-stats]').forEach(n => { if (!statsCache.has(n.dataset.caStats)) n.textContent = 'Statistika yüklənmədi. Kabineti yenidən aç.'; });
 } finally { if (sequence === statsSequence) statsPending = ''; }
}
function confirmSold(id) {
 const car = ownCars().find(c => c._id === id); if (!car || sold(car)) return;
 const context = openModal('sold', 'Avtomobil satılıb?', 'Satılıb kimi qeyd et', async ctx => {
  const changed = await rpc('ca_mark_listing_sold', {p_id:id}, ctx.owner, ctx.epoch);
  if (!isModal(ctx)) return;
  if (changed !== id) throw Error('Satılıb statusu saxlanmadı. Elan dəyişdirilmədi.');
  // Keep the seller record and its pictures/packages; remove only its public visibility.
  for (const item of ownCars()) if (item._id === id) { item.status = 'satilib'; item.veziyyet = 'satilib'; item.isSold = true; }
  for (const rows of [caPageCars,caVipCars,caOwnCars,caFavoriteCars]) for (const item of rows) if (item._id === id) { item.status = 'satilib'; item.veziyyet = 'satilib'; item.isSold = true; }
  caRebuildListingCache(); renderCabinet(); render();
  showMessage('Satılıb kimi qeyd olundu. Elan şəxsi kabinetində saxlanıldı.'); submit.hidden = true;
  const results = await Promise.allSettled([caFetchMyListings(),caFetchListings(1),caFetchFavoriteListings()]);
  if (isModal(ctx) && results.some(r => r.status === 'rejected' || r.value === false)) showMessage('Satılıb kimi qeyd olundu. Bəzi siyahılar yenilənmədi; kabineti yenidən aç.');
 });
 content.append(node('p', (car.make || '') + ' ' + (car.model || '')),
  node('p', 'Elan ümumi siyahıdan çıxacaq, şəkillər və paket tarixçəsi şəxsi kabinetində qalacaq.'));
 return context;
}
let visitorMemory = null;
function visitor() {
 if (visitorMemory) return visitorMemory;
 try { const old = localStorage.getItem('caMarketVisitor'); if (UUID.test(old || '')) return visitorMemory = old; } catch (_) {}
 const value = crypto.randomUUID(); visitorMemory = value;
 try { localStorage.setItem('caMarketVisitor', value); } catch (_) {}
 return value;
}
const recorded = new Set();
function recordEvent(car, kind) {
 if (!publicCar(car) || document.querySelector('#detailOverlay')?.dataset.privatePreview === 'true') return;
 const day = new Date().toISOString().slice(0,10), key = car._id + ':' + kind + ':' + day;
 if (recorded.has(key)) return;
 const storageKey = 'caMarketEvent:' + key;
 try { if (localStorage.getItem(storageKey) === '1') { recorded.add(key); return; } } catch (_) {}
 recorded.add(key);
 const id = car._id, expected = ownerNow();
 Promise.resolve().then(async () => {
  const token = expected ? await caToken() : null;
  if (ownerNow() !== expected || car.ownerId === ownerNow()) return;
  const accepted = await caRequest('/rest/v1/rpc/ca_record_listing_event','POST',{p_id:id,p_kind:kind,p_visitor:visitor()},token);
  if (accepted === true) { try { localStorage.setItem(storageKey, '1'); } catch (_) {} }
 }).catch(() => { recorded.delete(key); });
}
function addReportButton(car, options = {}) {
 const contact = $('detailContact'); if (!contact) return;
 contact.querySelector('#caReportListingBtn')?.remove();
 if (!publicCar(car, options)) return;
 const b = button('⚑ Elanı şikayət et', () => openReport(car._id)); b.id = 'caReportListingBtn'; contact.append(b);
}
function openReport(id) {
 if (!ownerNow()) return loginNotice();
 if (!activeDetailCar || activeDetailCar._id !== id || !publicCar(activeDetailCar) || $('detailOverlay')?.dataset.privatePreview === 'true') return;
 openModal('report', 'Elanı şikayət et', 'Şikayəti göndər', async ctx => {
  if (!activeDetailCar || activeDetailCar._id !== id || !publicCar(activeDetailCar) || $('detailOverlay')?.dataset.privatePreview === 'true') throw Error('Elan artıq şikayət üçün açıq deyil.');
  const result = await rpc('ca_report_listing',{p_id:id,p_reason:$('caReportReason').value,p_details:$('caReportDetails').value.trim()},ctx.owner,ctx.epoch);
  if (!isModal(ctx)) return;
  if (!UUID.test(result || '')) throw Error('Şikayət saxlanmadı. Yenidən yoxla.');
  content.replaceChildren(node('p','Şikayətin göndərildi. Admin yoxlayacaq.')); showMessage('Şikayət elanı avtomatik gizlətmir.'); submit.hidden = true;
 });
 const reason = node('select'); reason.required = true;
 Object.entries(reasons).forEach(([value,label]) => { const o = node('option',label); o.value = value; reason.append(o); });
 const details = node('textarea'); details.maxLength = 1000; details.rows = 4;
 content.append(field('Səbəb','caReportReason',reason),field('Əlavə məlumat (istəyə görə, 1000 simvoladək)','caReportDetails',details));
 reason.focus();
}
const searchFields = {make:'searchMake',model:'searchModel',price:'searchPrice',city:'searchCity',priceMin:'caPriceMin',priceMax:'caPriceMax',yearMin:'caYearMin',yearMax:'caYearMax',kmMin:'caKmMin',kmMax:'caKmMax',engineMin:'caEngineMin',engineMax:'caEngineMax',hpMin:'caHpMin',hpMax:'caHpMax',vehicle:'caVehicle',state:'caState',body:'caBody',color:'caColor',market:'caMarket',seats:'caSeats',saleType:'caSaleType'};
const numericFields = new Set(['price','priceMin','priceMax','yearMin','yearMax','kmMin','kmMax','engineMin','engineMax','hpMin','hpMax']);
function selectedFilters() {
 const filters = {};
 Object.entries(searchFields).forEach(([key,id]) => {
  const element = $(id); let value = element ? element.value.trim() : currentSearch?.[key];
  if (numericFields.has(key)) value = value === '' || value == null ? null : Number(value);
  if (value !== '' && value != null && (typeof value !== 'number' || Number.isFinite(value))) filters[key] = value;
 });
 filters.equipment = [...document.querySelectorAll('input[name="caEquipment"]:checked')].map(n => n.value);
 filters.pack = currentFilter || 'all'; filters.sort = $('sortListings')?.value || 'newest';
 return filters;
}
function saveSearchDialog() {
 if (!ownerNow()) return loginNotice();
 const filters = selectedFilters();
 openModal('save-search','Axtarışı yadda saxla','Yadda saxla', async ctx => {
  const name = $('caSearchName').value.trim(); if (!name) throw Error('Axtarışa ad yaz.');
  const id = await rpc('ca_save_search',{p_name:name,p_filters:filters},ctx.owner,ctx.epoch);
  if (!isModal(ctx)) return;
  if (!UUID.test(id || '')) throw Error('Axtarış saxlanmadı.');
  showMessage('Axtarış saxlanıldı. Uyğun yeni elanlar saytdakı bildirişlərdə görünəcək.'); submit.hidden = true;
  content.replaceChildren(node('p',name)); loadSavedSearches(); pollNotifications();
 });
 const name = node('input'); name.type = 'text'; name.maxLength = 80; name.required = true;
 name.value = [filters.make,filters.model,filters.city].filter(Boolean).join(' · ').slice(0,80) || 'Axtarışım';
 content.append(field('Axtarışın adı','caSearchName',name),node('p','Uyğun elanlar üçün yalnız saytda bildiriş alacaqsan.'));
 name.focus(); name.select();
}
function savedSection() {
 let section = $('caSavedSearches'); if (section) return section;
 const cabinet = $('cabinetList'); if (!cabinet) return null;
 section = node('section',null,'ca-market-section'); section.id = 'caSavedSearches';
 const head = node('div',null,'ca-actions'); head.append(node('h3','Saxlanılan axtarışlar'),button('Yenilə',()=>loadSavedSearches()));
 const list = node('div'); list.id = 'caSavedSearchList'; list.setAttribute('aria-live','polite');
 section.append(head,list); cabinet.before(section); return section;
}
async function loadSavedSearches() {
 if (!owner) return;
 savedSection(); const list = $('caSavedSearchList'); if (!list) return;
 const expected = owner, version = epoch, sequence = ++savedSequence; list.textContent = 'Axtarışlar yüklənir...';
 try {
  const rows = await rpc('ca_list_saved_searches',{},expected,version);
  if (!validSession(expected,version) || sequence !== savedSequence) return;
  if (!Array.isArray(rows) || rows.some(r => !UUID.test(r.id || '') || !r.filters || typeof r.filters !== 'object')) throw Error('Axtarışlar düzgün gəlmədi.');
  savedRows = rows; drawSavedSearches();
 } catch (error) { if (validSession(expected,version) && sequence === savedSequence) list.textContent = 'Axtarışlar yüklənmədi. «Yenilə» düyməsinə toxun.'; }
}
function drawSavedSearches() {
 const list = $('caSavedSearchList'); if (!list) return;
 list.replaceChildren();
 if (!savedRows.length) { list.append(node('p','Hələ saxlanılan axtarış yoxdur. Axtarış bölməsindən əlavə edə bilərsən.')); return; }
 for (const row of savedRows) {
  const card = node('article',null,'ca-market-item'); card.dataset.searchId = row.id;
  const apply = button('Axtarışı aç',()=>applySearch(row.id)); apply.dataset.caSearchApply = row.id;
  const remove = button('Sil',()=>deleteSearch(row.id,remove)); remove.dataset.caSearchDelete = row.id;
  const actions = node('div',null,'ca-actions'); actions.append(apply,remove); card.append(node('strong',row.name),actions); list.append(card);
 }
}
async function deleteSearch(id,b) {
 if (!savedRows.some(row => row.id === id)) return;
 const expected = owner,version = epoch; b.disabled = true;
 try {
  const ok = await rpc('ca_delete_saved_search',{p_id:id},expected,version);
  if (!validSession(expected,version)) return;
  if (ok !== true) throw Error('Axtarış silinmədi.');
  savedRows = savedRows.filter(row=>row.id!==id); drawSavedSearches(); pollNotifications();
 } catch (error) { if (validSession(expected,version)) { b.disabled = false; let status = $('caSavedSearchMessage'); if (!status) { status = node('p'); status.id='caSavedSearchMessage'; status.setAttribute('role','status'); $('caSavedSearchList').before(status); } status.textContent=error.message; } }
}
function applySearch(id) {
 const row = savedRows.find(r => r.id === id); if (!owner || !row) return;
 const filters = JSON.parse(JSON.stringify(row.filters));
 currentSearch = {}; Object.keys(searchFields).forEach(key => { if (filters[key] != null) currentSearch[key] = filters[key]; });
 currentSearch.equipment = Array.isArray(filters.equipment) ? filters.equipment : [];
 currentFilter = ['all','VIP','Premium','Standart','Pulsuz'].includes(filters.pack) ? filters.pack : 'all';
 Object.entries(searchFields).forEach(([key,id]) => { const element = $(id); if (element) element.value = filters[key] == null ? '' : String(filters[key]); });
 if ($('searchModel')) $('searchModel').disabled = !filters.make;
 document.querySelectorAll('input[name="caEquipment"]').forEach(n => { n.checked = currentSearch.equipment.includes(n.value); });
 const sort = $('sortListings'); if (sort) sort.value = [...sort.options].some(o => o.value === filters.sort) ? filters.sort : 'newest';
 document.querySelectorAll('.pill').forEach(p => {
  const match = (p.getAttribute('onclick') || '').match(/setFilter\(['"]([^'"]+)['"]/); if (match) p.classList.toggle('active',match[1] === currentFilter);
 });
 caSyncSaleTypeUI();
 closeModal(false); closeCabinet(); closeSellPage(); caFetchListings(1); $('elanlar')?.scrollIntoView({behavior:'smooth'});
}
function updateNotificationBadge() {
 const launch = $('caNotificationsLaunch'); if (!launch) return;
 launch.hidden = !owner; const count = Math.max(0,Number(notificationState?.unread_count)||0);
 let badge = $('caNotificationBadge'); if (!badge) { badge = node('span', '', 'ca-notification-badge'); badge.id = 'caNotificationBadge'; launch.append(badge); } badge.textContent = count > 99 ? '99+' : String(count); badge.hidden = !count;
 launch.setAttribute('aria-label','Bildirişlər'+(count?' · '+count+' oxunmamış':''));
}
function openNotifications() {
 if (!ownerNow()) return loginNotice();
 openModal('notifications','Bildirişlər','',null);
 content.append(node('p','Saxlanılan axtarışlara uyğun yeni elanlar. Bildirişlər yalnız bu saytdadır.'));
 const list = node('div'); list.id = 'caNotificationList'; content.append(list); notificationPage=1;
 if (notificationState?.page===1) drawNotifications(); pollNotifications(1,true);
}
function validPage(data) {
 return data && Array.isArray(data.items) && Number.isSafeInteger(data.total) && data.total>=0 && Number.isSafeInteger(data.page) && data.page>=1 && Number.isSafeInteger(data.total_pages) && data.total_pages>=0 && data.items.length<=24;
}
async function pollNotifications(page = notificationPage, forced = false, drainPass = 0) {
 if (!owner || document.hidden || notificationBusy && !forced) return;
 const expected=owner,version=epoch,sequence=++notificationSequence; notificationBusy=true;
 const context=modal?.kind==='notifications'?modal:null;
 try {
  const data=await rpc('ca_list_notifications',{p_page:page,p_page_size:24},expected,version);
  if (!validSession(expected,version)||sequence!==notificationSequence) return;
  if (!validPage(data)||!Number.isSafeInteger(data.unread_count)||data.unread_count<0||data.items.some(r=>!UUID.test(r.id||'')||!UUID.test(r.elan_id||''))) throw Error('Bildirişlər düzgün gəlmədi.');
  notificationState=data;notificationPage=data.page;updateNotificationBadge();
  if(context&&modal===context)drawNotifications();
  if(data.processing===true&&!document.hidden){
   clearTimeout(drainTimer);
   // Bounded batches allow queued approvals to catch up without blocking the page.
   drainTimer=setTimeout(()=>{if(validSession(expected,version)&&!document.hidden)pollNotifications(notificationPage,false,drainPass<3?drainPass+1:0);},drainPass<3?250:2000);
  }
 }catch(error){if(validSession(expected,version)&&sequence===notificationSequence&&context&&modal===context)showMessage('Bildirişlər yüklənmədi. Yenidən yoxla.',true);}
 finally{if(sequence===notificationSequence)notificationBusy=false;}
}
function drawNotifications() {
 if(modal?.kind!=='notifications'||!notificationState)return;
 const list=$('caNotificationList');if(!list)return;list.replaceChildren();
 const controls=node('div',null,'ca-actions');
 const all=button('Hamısını oxunmuş et',()=>markNotification(null,all));all.id='caNotificationReadAll';all.disabled=!notificationState.unread_count;
 controls.append(all,button('Yenilə',()=>pollNotifications(notificationPage,true)));list.append(controls);
 if(!notificationState.items.length)list.append(node('p','Hələ yeni uyğun elan yoxdur.'));
 for(const row of notificationState.items){
  const card=node('article',null,'ca-market-item');card.dataset.notificationId=row.id;card.classList.toggle('ca-unread',!row.is_read);
  card.append(node('small',row.search_name),node('strong',[row.marka,row.model,row.il].filter(Boolean).join(' ')),node('p',String(row.qiymet??'')+' AZN · '+String(row.seher||'')));
  const actions=node('div',null,'ca-actions'),open=button('Elana bax',()=>openNotification(row,open));open.dataset.caNotificationOpen=row.id;actions.append(open);
  if(!row.is_read){const read=button('Oxunmuş et',()=>markNotification(row.id,read));read.dataset.caNotificationRead=row.id;actions.append(read);}
  card.append(actions);list.append(card);
 }
 const pager=node('div',null,'ca-actions ca-market-pager');
 const prev=button('← Əvvəlki',()=>pollNotifications(notificationPage-1,true));prev.dataset.caNotificationPage='previous';prev.disabled=notificationPage<=1;
 const next=button('Növbəti →',()=>pollNotifications(notificationPage+1,true));next.dataset.caNotificationPage='next';next.disabled=notificationPage>=notificationState.total_pages;
 if(notificationState.total_pages>1){pager.append(prev,node('span',notificationPage+' / '+notificationState.total_pages),next);list.append(pager);}
}
async function markNotification(id,b) {
 const context=modal;if(context?.kind!=='notifications'||id&&!notificationState?.items.some(r=>r.id===id))return;
 b.disabled=true;
 try{const ok=await rpc('ca_mark_notification_read',{p_id:id},context.owner,context.epoch);if(!isModal(context))return;if(ok!==true)throw Error('Oxunma statusu saxlanmadı.');await pollNotifications(notificationPage,true);}
 catch(error){if(isModal(context)){showMessage(error.message,true);b.disabled=false;}}
}
async function openNotification(row,b) {
 const context=modal;if(context?.kind!=='notifications'||!notificationState?.items.some(r=>r.id===row.id))return;
 b.disabled=true;showMessage('Elan açılır...');
 try{
  const token=await caToken();if(!token||!isModal(context))return;
  const rows=await caRequest('/rest/v1/elanlar?select='+CA_LISTING_COLUMNS+'&id=eq.'+encodeURIComponent(row.elan_id)+'&veziyyet=eq.aktiv&limit=1','GET',null,token);
  if(!isModal(context))return;
  if(!Array.isArray(rows)||rows.length!==1||rows[0].id!==row.elan_id)throw Error('Elan artıq aktiv deyil.');
  const car=caRemoteToCar(rows[0]);if(sold(car)||(car.veziyyet||car.status)!=='aktiv')throw Error('Elan artıq aktiv deyil.');
  const ok=await rpc('ca_mark_notification_read',{p_id:row.id},context.owner,context.epoch);if(!isModal(context))return;if(ok!==true)throw Error('Bildiriş yenilənmədi. Yenidən yoxla.');
  closeModal(false);window.caCancelListingLink?.();caOpenCarRecord(car);pollNotifications(notificationPage,true);
 }catch(error){if(isModal(context)){showMessage(error.message,true);b.disabled=false;}}
}
function reportsSection() {
 const panel=$('caAdminPanel');if(!panel)return null;
 let section=$('caReportsAdmin');if(section)return section;
 section=node('section',null,'ca-market-section');section.id='caReportsAdmin';section.hidden=true;
 const heading=node('h3','Elan şikayətləri'),filters=node('div',null,'ca-actions'),select=node('select');select.id='caReportsFilter';select.setAttribute('aria-label','Şikayət statusu');
 for(const [value,text] of Object.entries({open:'Açıq şikayətlər',resolved:'Həll edilmiş',dismissed:'Əsassız hesab edilmiş',all:'Bütün şikayətlər'})){const option=node('option',text);option.value=value;select.append(option);}
 select.addEventListener('change',()=>loadReports(1));filters.append(select,button('Şikayətləri yenilə',()=>loadReports(reportPage)));
 const status=node('p');status.id='caReportsMessage';status.setAttribute('role','status');
 const list=node('div');list.id='caReportsList';const pager=node('div',null,'ca-actions');pager.id='caReportsPager';section.append(heading,filters,status,list,pager);panel.append(section);return section;
}
function adminVisible(){return $('caAdminPanel')&&$('caAdminPanel').style.display!=='none';}
async function initReports(){
 const section=reportsSection();if(!section||!owner||!adminVisible())return;
 window.caCancelReportPreview?.();
 const expected=owner,version=epoch,sequence=++adminSequence;adminAuthorized=false;adminOwner=null;section.hidden=true;
 try{const ok=await rpc('cenub_admin_yoxla',{},expected,version);if(!validSession(expected,version)||sequence!==adminSequence||!adminVisible())return;if(ok!==true)return;adminAuthorized=true;adminOwner=expected;section.hidden=false;loadReports(1);}
 catch(_){if(validSession(expected,version)&&sequence===adminSequence)section.hidden=true;}
}
async function loadReports(page=reportPage){
 if(!adminAuthorized||adminOwner!==owner||!adminVisible())return;
 window.caCancelReportPreview?.();
 const expected=owner,version=epoch,sequence=++adminSequence,status=$('caReportsFilter').value;reportPage=page;$('caReportsMessage').textContent='Şikayətlər yüklənir...';
 try{
  const data=await rpc('ca_admin_browse_reports',{p_status:status,p_page:page,p_page_size:24},expected,version);
  if(!validSession(expected,version)||sequence!==adminSequence||!adminAuthorized||!adminVisible())return;
  if(!validPage(data)||data.items.some(r=>!UUID.test(r.id||'')))throw Error('Şikayətlər düzgün gəlmədi.');
  reportRows=data.items;reportPage=data.page;$('caReportsMessage').textContent=data.total+' şikayət';drawReports(data);
 }catch(error){if(validSession(expected,version)&&sequence===adminSequence&&adminVisible())$('caReportsMessage').textContent='Şikayətlər yüklənmədi. Yenidən yoxla.';}
}
function drawReports(data){
 const list=$('caReportsList');list.replaceChildren();if(!reportRows.length)list.append(node('p','Bu bölmədə şikayət yoxdur.'));
 for(const row of reportRows){
  const card=node('article',null,'ca-market-item');card.dataset.reportId=row.id;
  card.append(node('strong',[row.marka,row.model].filter(Boolean).join(' ')),node('p',reasons[row.reason]||'Digər'),node('p',row.details||''),node('p','Status: '+({open:'Açıq',resolved:'Həll edilib',dismissed:'Əsassız hesab edilib'}[row.status]||row.status)));
  const note=node('textarea');note.maxLength=1000;note.rows=2;note.value=row.admin_note||'';note.dataset.caReportNote=row.id;note.setAttribute('aria-label','Daxili admin qeydi');card.append(note);
  const actions=node('div',null,'ca-actions');
  const preview=button('Elana bax',()=>previewReportListing(row.id,row.elan_id,preview));
  preview.dataset.caReportPreview=row.id;preview.dataset.listingId=row.elan_id||'';preview.disabled=!UUID.test(row.elan_id||'');actions.append(preview);
  for(const [status,label]of [['resolved','Həll edildi'],['dismissed','Əsassızdır']]){const b=button(label,()=>resolveReport(row.id,status,note.value,b));b.dataset.caReportStatus=status;b.disabled=row.status===status;actions.append(b);}
  card.append(actions);list.append(card);
 }
 const pager=$('caReportsPager');pager.replaceChildren();if(data.total_pages>1){const prev=button('← Əvvəlki',()=>loadReports(reportPage-1));prev.disabled=reportPage<=1;const next=button('Növbəti →',()=>loadReports(reportPage+1));next.disabled=reportPage>=data.total_pages;pager.append(prev,node('span',reportPage+' / '+data.total_pages),next);}
}
async function previewReportListing(reportId,listingId,b){
 if(!adminAuthorized||adminOwner!==owner||!adminVisible()||!UUID.test(listingId||'')||!reportRows.some(row=>row.id===reportId&&row.elan_id===listingId))return;
 const expected=owner,version=epoch,sequence=adminSequence,previewSequence=++reportPreviewSequence;
 const current=()=>previewSequence===reportPreviewSequence&&validSession(expected,version)&&adminAuthorized&&adminOwner===expected&&adminVisible()&&sequence===adminSequence&&b.isConnected&&reportRows.some(row=>row.id===reportId&&row.elan_id===listingId);
 $('caReportsMessage').textContent='Elanın tam məlumatları yüklənir...';
 try{
  if(typeof window.caAdminPreviewReportListing!=='function')throw Error('Baxış xidməti hazır deyil. Səhifəni yenilə.');
  const opened=await window.caAdminPreviewReportListing(listingId,b,current);
  if(!current())return;
  const detailMessage=$('caAdminActionMsg')?.textContent||'';
  $('caReportsMessage').textContent=opened?'':(detailMessage&&detailMessage!=='Elanın tam məlumatları yüklənir...'?detailMessage:'Elan açılmadı. Yenidən yoxla.');
 }catch(error){if(current()){$('caReportsMessage').textContent='Elan açılmadı: '+error.message;b.disabled=false;}}
}
async function resolveReport(id,status,note,b){
 if(!adminAuthorized||adminOwner!==owner||!adminVisible()||!reportRows.some(r=>r.id===id))return;
 const expected=owner,version=epoch;b.disabled=true;
 try{const ok=await rpc('ca_admin_resolve_report',{p_report_id:id,p_status:status,p_note:note.trim().slice(0,1000)},expected,version);if(!validSession(expected,version)||!adminAuthorized||!adminVisible())return;if(ok!==true)throw Error('Qərar saxlanmadı.');$('caReportsMessage').textContent='Qərar saxlanıldı. Elanın yayım statusu dəyişmədi.';loadReports(reportPage);}
 catch(error){if(validSession(expected,version)&&adminVisible()){$('caReportsMessage').textContent=error.message;b.disabled=false;}}
}
function mount(){
 const actions=document.querySelector('.ca-search-main .search-actions')||document.querySelector('.search-actions');
 if(actions&&!$('caSaveSearchLaunch')){const b=button('Axtarışı yadda saxla',saveSearchDialog);b.id='caSaveSearchLaunch';actions.append(b);}
 const header=document.querySelector('header .header-actions');
 if(header&&!$('caNotificationsLaunch')){const b=button('',openNotifications);b.id='caNotificationsLaunch';b.className='ca-notification-launch';b.append(node('span','🔔 Bildirişlər'));const badge=node('span','0','ca-notification-badge');badge.id='caNotificationBadge';badge.hidden=true;b.append(badge);header.prepend(b);}
 savedSection();reportsSection();updateNotificationBadge();if($('caSavedSearches'))$('caSavedSearches').hidden=!owner;
}
function sessionChanged(){
 const next=ownerNow();if(next===owner){mount();return;}
 owner=next;epoch++;savedSequence++;statsSequence++;notificationSequence++;adminSequence++;modalSequence++;
 closeModal(false);statsCache=new Map();statsPending='';savedRows=[];notificationState=null;notificationBusy=false;notificationPage=1;reportRows=[];adminAuthorized=false;adminOwner=null;
 clearTimeout(drainTimer);drainTimer=null;
 for(const id of ['caSavedSearchList','caNotificationList','caReportsList','caReportsMessage','caReportsPager','caSavedSearchMessage'])$(id)?.replaceChildren();
 document.querySelectorAll('[data-ca-stats]').forEach(n=>n.remove());if($('caReportsAdmin'))$('caReportsAdmin').hidden=true;
 mount();if(owner){queueMicrotask(()=>{if(ownerNow()===owner&&!document.hidden)pollNotifications(1,true);});if(document.body.classList.contains('cabinet-open')){decorateCabinet();loadSavedSearches();}}
}
window.caMarketSessionChanged=sessionChanged;
const originalCabinet=window.renderCabinet;
window.renderCabinet=function(...args){const result=originalCabinet.apply(this,args);sessionChanged();decorateCabinet();return result;};
const originalOpenCabinet=window.openCabinet;
window.openCabinet=function(...args){statsCache.clear();statsSequence++;statsPending='';const result=originalOpenCabinet.apply(this,args);sessionChanged();if(owner){loadSavedSearches();pollNotifications(1,true);}return result;};
const originalDetail=window.caOpenCarRecord;
window.caOpenCarRecord=function(car,options={}){const result=originalDetail.call(this,car,options);if(result!==false&&$('detailOverlay')?.classList.contains('open')&&activeDetailCar?._id===car?._id){addReportButton(car,options);if(publicCar(car,options))recordEvent(car,'view');}return result;};
const originalAdmin=window.caAdminOpen;
if(originalAdmin)window.caAdminOpen=async function(...args){const result=await originalAdmin.apply(this,args);sessionChanged();if(adminVisible())await initReports();return result;};
const originalAdminClose=window.caAdminClose;
if(originalAdminClose)window.caAdminClose=function(...args){adminSequence++;adminAuthorized=false;adminOwner=null;reportRows=[];$('caReportsList')?.replaceChildren();if($('caReportsAdmin'))$('caReportsAdmin').hidden=true;return originalAdminClose.apply(this,args);};
const originalEdit=window.editCar;
if(originalEdit)window.editCar=function(id,...args){if(ownCars().some(c=>c._id===id&&sold(c)))return;return originalEdit.call(this,id,...args);};
document.addEventListener('click',event=>{if(event.target.closest('#detailContact a[href^="tel:"]')&&$('detailOverlay')?.classList.contains('open'))recordEvent(activeDetailCar,'contact');},true);
function resumePolling(){sessionChanged();if(owner&&!document.hidden)pollNotifications(notificationPage);}
window.addEventListener('focus',resumePolling);document.addEventListener('visibilitychange',resumePolling);
mount();pollTimer=setInterval(resumePolling,60000);if(owner&&!document.hidden)pollNotifications(1,true);
})();
