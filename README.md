# Cənub Avto

Avtomobil elanları üçün Azərbaycan dilində statik sayt. HTML, CSS və JavaScript GitHub Pages-də yerləşir; hesablar, elanlar və şəkil saxlancı Supabase ilə işləyir.

- Sayt: https://dunumcebis-droid.github.io/cenub-avto/
- Kod: https://github.com/dunumcebis-droid/cenub-avto

## Cari düzəlişlər

- Marka, model, qiymət, il, yürüş və texniki məlumatlar baza sütunlarından və əvvəlki `ca_data` formatlarından oxunur. Boş yürüş `null`, daxil edilmiş sıfır isə `0 km` olaraq qorunur.
- Redaktə forması təchizat seçimlərini və şəkillərin bölmələrini bərpa edir. Yeni şəkil seçilməyən bölmələr, mövcud şəkil sırası və kataloqda olmayan köhnə təchizat dəyərləri saxlanılır.
- Elan yaratma, redaktə və silmə serverin qaytardığı elan ID-si ilə təsdiqlənir. Heç bir sətri dəyişməyən sorğu uğur kimi göstərilmir. Silmə şəkilləri və ödəniş tarixçəsini saxlayan arxivləşdirmədir (`silindi`).
- Redaktədə cari paket saxlanılır; yeni paket yalnız ayrıca seçildikdə istənilir. VIP, Premium və Standart müddətləri müvafiq olaraq 15, 5 və 3 gündür; faktiki paket bazanın təsdiqlənmiş vəziyyətindən və bitmə tarixindən oxunur.
- Elan siyahısı serverdə süzülür və sıralanır, səhifədə 24 elan göstərilir. Ümumi say üçün kodda əvvəlki 500 elan məhdudiyyəti yoxdur. Satıcının elanları ayrıca 100-lük hissələrlə oxunur.
- «Bu gün təsdiqlənən» göstəricisi server hesabından gəlir; sıfır düzgün göstərilir. Uğursuz sorğu əvvəlki uğurlu məlumatları silmir, köhnə sorğu cavabı yeni səhifəni əvəz etmir.

Serverdə səhifələmə və elan idarəetməsi üçün `20261107060719_fix_listing_management_and_paginated_browse` Supabase miqrasiyası tətbiq edilib; 59 geri qaytarılan SQL yoxlaması keçib. Tətbiq olunan SQL-in istinadı [database/applied-listing-management.sql](database/applied-listing-management.sql) faylındadır. Son kod üzərində 55 Node və 19 Chromium testi keçib. GitHub Pages yayımı və real elanlarla 1440/375 px canlı yoxlama da uğurludur; sübutlar [VERIFICATION.md](VERIFICATION.md) sənədində toplanır.

## Fayllar və şəkillərin qorunması

- `index.html`: səhifənin quruluşu; əvvəlki 12,47 MB əvəzinə təxminən 46 KB.
- `assets/site.css`: əvvəlki 9 stil blokunun ardıcıllığı qorunmuş vahid stil faylı.
- `assets/js/01-main.js`: elanlar, hesab, redaktə, filtrlər və əsas interfeys. Digər 7 JavaScript faylı HTML-dəki əvvəlki icra ardıcıllığı ilə ayrıca `defer` skriptləridir.
- `assets/images/`: 56 daxili şəkil istinadının 46 unikal faylı. Şəkillər yalnız base64-dən fayla çıxarılıb; baytları dəyişdirilməyib, yenidən kodlaşdırılmayıb.
- `assets/manifest.json`: ilkin istinadlar, fayl yolları, ölçülər və SHA-256 izləri. `tests/assets.test.cjs` fayllardan ilkin data URI-lərini yenidən quraraq eyniliyi yoxlayır.
- `tests/`: Node, Chromium və tranzaksiya sonunda geri qaytarılan SQL yoxlamaları.

İstifadəçinin əvvəldən yüklədiyi şəkillər və onların URL-ləri bu fayl bölgüsünə daxil deyil; dəyişdirilməyib. İlk ekranın əsas şəkli dərhal, digər uyğun şəkillər ehtiyac yarandıqda yüklənir.

## Yerli açılış və avtomatik yoxlamalar

Build mərhələsi yoxdur. Repozitoriyanın kökündə yerli statik server açmaq olar:

```sh
python3 -m http.server 8000
```

Sonra http://localhost:8000/ ünvanını açın. Adi sayt real Supabase layihəsinə qoşulur; avtomatik brauzer testləri isə API cavablarını sınaq məlumatları ilə əvəz edir və real bazaya yazmır.

```sh
node --test --test-isolation=none --test-reporter=spec tests/*.test.cjs
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*_browser.py' -v
for script in assets/js/*.js; do node --check "$script" || exit; done
git diff --check
```

Node testləri daxili test kitabxanasından istifadə edir. Python testləri üçün `playwright` paketi və Chromium lazımdır; brauzerin yolunu `CHROMIUM_PATH` ilə göstərmək olar. Yoxlama əhatəsi və canlı yayım nəticələri [VERIFICATION.md](VERIFICATION.md) sənədindədir.

## Ödənişin vəziyyəti

Mövcud əl ilə paket sorğusu və admin təsdiqi axını saxlanılıb. İstifadəçinin hazırda merchant hesabı yoxdur; VÖEN və ABB ilə internet ekvayrinq/merchant girişi alındıqdan sonra bank inteqrasiyası ayrıca tamamlanmalıdır. Bu məlumatlar olmadan kartdan avtomatik ödəniş və bankın təsdiqlədiyi ödəniş nəticəsi aktiv deyil.

Əvvəlki açıq elan oxuma icazəsinin tətbiq tarixçəsi [PUBLIC_LISTING_ACCESS.md](PUBLIC_LISTING_ACCESS.md) sənədində saxlanılır; həmin sənəd cari yeniləmənin yayım sübutu deyil.
