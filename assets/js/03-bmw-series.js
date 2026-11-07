const bmwSeriesModels={
1:['114i','116i','116d','118i','118d','120i','120d','123d','125i','125d','128ti','130i','135i','M135i','M140i','F40 118i','F40 120d','F70 120','F70 M135 xDrive'],
2:['F22 218i','F22 220i','F22 220d','F22 228i','F22 230i','F22 M235i','F22 M240i','G42 220i','G42 230i','G42 M240i','F44 218i Gran Coupe','F44 220d Gran Coupe','F44 M235i Gran Coupe','F45 Active Tourer','F46 Gran Tourer','U06 Active Tourer','M2','M2 Competition','M2 CS'],
3:['E21 315','E21 320','E30 316i','E30 318i','E30 325i','E36 316i','E36 318i','E36 320i','E36 325i','E36 M3','E46 316i','E46 318i','E46 320i','E46 330i','E46 M3','E90 318i','E90 320i','E90 325i','E90 330i','F30 316i','F30 318i','F30 320i','F30 328i','F30 330i','F30 335i','G20 318i','G20 320i','G20 330i','G20 330e','G20 M340i','G80 M3','M3 Competition'],
4:['F32 418i','F32 420i','F32 420d','F32 430i','F32 435i','F32 440i','G22 420i','G22 430i','G22 M440i','G26 i4','G26 420d Gran Coupe','G26 M440i Gran Coupe','F33 Convertible','G23 Convertible','M4','M4 Competition','M4 CSL'],
5:['E12 520','E28 520i','E34 520i','E34 525i','E39 520i','E39 525i','E39 530i','E39 M5','E60 520i','E60 525i','E60 530i','E60 535d','E60 M5','F10 520i','F10 520d','F10 528i','F10 530d','F10 535i','F10 M5','G30 520i','G30 520d','G30 530i','G30 530e','G30 540i','G30 M550i','G60 520i','G60 530i','i5','M5','M5 Competition'],
6:['E24 628CSi','E24 635CSi','E63 630i','E63 645Ci','E63 650i','E63 M6','F06 640i Gran Coupe','F06 650i Gran Coupe','F12 640i Convertible','F12 M6','F13 640i Coupe','F13 M6','G32 630i GT','G32 640i GT','G32 620d GT'],
7:['E23 728i','E32 730i','E32 750i','E38 728i','E38 740i','E38 750i','E65 730i','E65 745i','F01 730d','F01 740i','F01 750i','G11 730i','G11 740i','G11 750i','G12 M760Li','G70 735i','G70 740i','G70 760i','i7','i7 M70'],
8:['E31 840Ci','E31 850i','G14 840i Convertible','G14 M850i Convertible','G15 840i Coupe','G15 840d Coupe','G15 M850i Coupe','G16 840i Gran Coupe','G16 M850i Gran Coupe','M8','M8 Competition','M8 CS']
};;
function showBMWSeries(){const p=document.getElementById('bmwSeriesPanel');p.hidden=false;p.scrollIntoView({behavior:'smooth',block:'nearest'});}
function hideBMWSeries(){document.getElementById('bmwSeriesPanel').hidden=true;document.getElementById('bmwModels').hidden=true;document.querySelectorAll('.bmw-series-card').forEach(x=>x.classList.remove('active'));}
function selectBMWSeries(n){
 document.querySelectorAll('.bmw-series-card').forEach(x=>x.classList.toggle('active',x.dataset.series===n+' Series'));
 const box=document.getElementById('bmwModels');
 const list=bmwSeriesModels[n]||[];
 document.getElementById('bmwModelsTitle').textContent='BMW '+n+' Series — bütün modellər';
 document.getElementById('bmwModelChips').innerHTML=list.map(m=>`<button type="button" class="bmw-model-chip" onclick="quickBMWModel(${n},'${m.replace(/'/g,"\\'")}')">${m}</button>`).join('');
 box.hidden=false;
 box.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function quickBrand(make){const input=document.getElementById('searchMake');if(input){input.value=make;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('.search').scrollIntoView({behavior:'smooth',block:'center'});}}
function quickBMWModel(n,model){quickBrand('BMW');const input=document.getElementById('searchModel');if(input){input.disabled=false;input.value=model;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));}document.getElementById('elanlar').scrollIntoView({behavior:'smooth'});}
