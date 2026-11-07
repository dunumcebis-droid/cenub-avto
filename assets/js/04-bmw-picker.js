/* BMW model picker: 1–8 Series accordion; models are shown only after opening a series. */
let cenubBMWOpenSeries = new Set();
function renderPickerItems(){
  const q=pickerSearch.value.trim().toLocaleLowerCase('az');
  const all=pickerItems();
  const items=all.filter(x=>x.toLocaleLowerCase('az').includes(q));
  if(activePicker.kind==='make'){
    const popular=popularMakes.filter(x=>items.some(y=>y.toLocaleLowerCase('az')===x.toLocaleLowerCase('az')));
    const popularSet=new Set(popular.map(x=>x.toLocaleLowerCase('az')));
    const others=items.filter(x=>!popularSet.has(x.toLocaleLowerCase('az')));
    const renderBrand=x=>{const urls=makeLogoUrls(x);const initials=x.split(/\s+/).slice(0,2).map(w=>w[0]||'').join('').toUpperCase();return `<button type="button" class="picker-option brand-picker-option" data-picker-value="${esc(x)}"><span class="brand-logo-box"><span class="brand-logo-fallback" style="display:grid">${esc(initials)}</span><img decoding="async" loading="lazy" src="${urls.primary}" data-alt="${urls.secondary}" data-third="${urls.tertiary}" alt="${esc(x)} loqosu" onload="this.style.display='block';this.previousElementSibling.style.display='none'" onerror="if(this.dataset.alt){this.src=this.dataset.alt;this.dataset.alt=''}else if(this.dataset.third){this.src=this.dataset.third;this.dataset.third=''}else{this.style.display='none';this.previousElementSibling.style.display='grid'}"></span><span class="brand-option-name">${esc(x)}<small>Rəsmi marka loqosu</small></span></button>`};
    pickerList.innerHTML=(popular.length?`<div class="picker-section-title">Məşhur markalar</div>${popular.map(renderBrand).join('')}`:'')+(others.length?`<div class="picker-section-title">Bütün markalar</div>${others.map(renderBrand).join('')}`:'')||'<div class="picker-empty">Uyğun marka tapılmadı. Adı özün də əlavə edə bilərsən.</div>';
    document.getElementById('pickerNote').textContent=`${items.length} marka göstərilir · Məşhur markalar yuxarıda yerləşir.`;
  }else if(String(activePicker.make||'').toLocaleLowerCase('az')==='bmw' && typeof bmwSeriesModels!=='undefined'){
    const groups=[],grouped=new Set();
    for(let n=1;n<=8;n++){
      const base=bmwSeriesModels[n]||[];
      const catalog=(modelCatalog.BMW||[]);
      const patterns={
        1:/^(?:1\s*Series|1M\b|1\d{2}[a-z]?|M1\d{2}|F\d+\s+1)/i,
        2:/^(?:2\s*Series|M2\b|2\d{2}[a-z]?|F\d+\s+2|.*Active Tourer|.*Gran Tourer)/i,
        3:/^(?:3\s*Series|M3\b|E\d{2}\s+3\d{2}|F\d{2}\s+3\d{2}|G\d{2}\s+3\d{2}|3\d{2}[a-z]?)/i,
        4:/^(?:4\s*Series|M4\b|F\d{2}\s+4\d{2}|G\d{2}\s+4\d{2}|4\d{2}[a-z]?)/i,
        5:/^(?:5\s*Series|M5\b|E\d{2}\s+5\d{2}|F\d{2}\s+5\d{2}|G\d{2}\s+5\d{2}|5\d{2}[a-z]?)/i,
        6:/^(?:6\s*Series|M6\b|E\d{2}\s+6\d{2}|F\d{2}\s+6\d{2}|G\d{2}\s+6\d{2}|6\d{2}[a-z]?)/i,
        7:/^(?:7\s*Series|M7\b|i7\b|E\d{2}\s+7\d{2}|F\d{2}\s+7\d{2}|G\d{2}\s+7\d{2}|7\d{2}[a-z]?)/i,
        8:/^(?:8\s*Series|M8\b|G\d{2}\s+8\d{2}|8\d{2}[a-z]?)/i
      };
      const merged=[...new Set([...base,...catalog.filter(m=>patterns[n].test(m))])];
      merged.forEach(model=>grouped.add(model));
      const filtered=merged.filter(m=>!q || (`${n} series ${m}`).toLocaleLowerCase('az').includes(q));
      if(filtered.length)groups.push({n,models:filtered});
    }
    const remaining=items.filter(model=>!grouped.has(model));
    const series=groups.map(({n,models})=>{
      const open=cenubBMWOpenSeries.has(String(n)) || (!!q && models.some(m=>m.toLocaleLowerCase('az').includes(q)));
      if(open)cenubBMWOpenSeries.add(String(n));
      return `<section class="bmw-picker-series ${open?'open':''}">
        <button type="button" class="bmw-picker-series-head" data-bmw-series-toggle="${n}" aria-expanded="${open}">
          <span class="series-number">${String(n).padStart(2,'0')}</span>
          <span class="series-label">${n} Series <small class="series-count">${models.length} model</small></span>
          <span class="series-arrow">›</span>
        </button>
        ${open?`<div class="bmw-picker-series-models">${models.map(m=>`<button type="button" class="picker-option" data-picker-value="${esc(m)}">${esc(m)}<small>BMW ${n} Series</small></button>`).join('')}</div>`:''}
      </section>`;
    }).join('');
    const other=remaining.length?'<div class="picker-section-title">Digər BMW modelləri</div>'+remaining.map(model=>`<button type="button" class="picker-option model-picker-option" data-picker-value="${esc(model)}"><span class="model-option-name">${esc(model)}<small>BMW modeli</small></span></button>`).join(''):'';
    pickerList.innerHTML=series+other||'<div class="picker-empty">Bu axtarışa uyğun BMW modeli tapılmadı.</div>';
    document.getElementById('pickerNote').textContent=`BMW · 1–8 seriyaları və digər modellər · ${groups.reduce((a,g)=>a+g.models.length,0)+remaining.length} model`;
  }else{
    pickerList.innerHTML=items.map((x,i)=>`<button type="button" class="picker-option model-picker-option" data-picker-value="${esc(x)}"><span class="model-option-mark">${String(i+1).padStart(2,'0')}</span><span class="model-option-name">${esc(x)}<small>${esc(activePicker.make)} modeli</small></span></button>`).join('')||'<div class="picker-empty">Uyğun model tapılmadı. Axtarış sözünü yoxla və ya öz model adını əlavə et.</div>';
    document.getElementById('pickerNote').textContent=`${activePicker.make} üçün ${items.length} model`;
  }
  const exact=[...pickerList.querySelectorAll('[data-picker-value]')].some(option=>option.dataset.pickerValue.toLocaleLowerCase('az')===q);
  pickerCustom.style.display=q&&!exact?'block':'none';
  pickerCustom.textContent=`“${pickerSearch.value.trim()}” adını istifadə et`;
}
// The main script registered its original renderer before this BMW override.
// Keep typed BMW searches on the same grouped renderer as opening the picker.
pickerSearch.addEventListener('input',event=>{
  if(activePicker.kind==='model'&&String(activePicker.make||'').toLocaleLowerCase('az')==='bmw'){
    event.stopImmediatePropagation();renderPickerItems();
  }
},true);
pickerList.addEventListener('click',e=>{
  const toggle=e.target.closest('[data-bmw-series-toggle]');
  if(!toggle)return;
  const n=toggle.dataset.bmwSeriesToggle;
  if(cenubBMWOpenSeries.has(n))cenubBMWOpenSeries.delete(n);else cenubBMWOpenSeries.add(n);
  renderPickerItems();
});
