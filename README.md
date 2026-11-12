# Cənub Avto

Avtomobil elanları üçün Azərbaycan dilində statik sayt. HTML, CSS və JavaScript GitHub Pages-də yerləşir; hesablar, elanlar və şəkil saxlancı Supabase ilə işləyir.

- Sayt: https://dunumcebis-droid.github.io/cenub-avto/
- Kod: https://github.com/dunumcebis-droid/cenub-avto

## Son düzəliş və yoxlama

Elanın böyük şəklinə toxunanda tam ekran baxışı açılır. Yaxınlaşdırma, iki barmaq, sürüşdürmə, əvvəlki/növbəti şəkil, klaviatura və geri düyməsi işləyir. Elan və tam ekran baxışı açıq olanda üzən alətlər/admin düyməsi gizlənir. Yeni toxunma ssenariləri və əlaqəli şəkil yoxlamaları: [PHOTO_VIEWER_VERIFICATION.md](PHOTO_VIEWER_VERIFICATION.md).

## Əvvəlki su nişanı

Elan şəkillərinə yarımşəffaf **CƏNUB AVTO** su nişanı əlavə olunub. Yeni hazırlanmış JPEG faylları yazını özündə saxlayır; əvvəlki şəkillərin orijinalları və URL-ləri dəyişmədən ekranda yazı göstərilir. 60 Node və 84 brauzer yoxlaması (79 mövcud, 5 yeni) keçib. Əhatə: [WATERMARK_VERIFICATION.md](WATERMARK_VERIFICATION.md).

## Əvvəlki loqo və şüar

İstifadəçinin loqosu bütün səhifələrə yerləşdirilib. Yeni şüar: **Xəyal etdiyin avtomobili kəşf et**. Loqo faylı və əvvəlki avtomobil şəkilləri dəyişdirilməyib. 60 Node, 79 brauzer və 48 responsive görünüş yoxlaması keçib. Əhatə və sübutlar: [BRANDING_VERIFICATION.md](BRANDING_VERIFICATION.md).

## Əvvəlki ayrıca parol bərpası səhifəsi

Yeni bərpa məktubları ayrıca [parol bərpası səhifəsini](https://dunumcebis-droid.github.io/cenub-avto/reset-password.html) açır. Etibarlı link yoxlanandan sonra iki parol xanası görünür; səhv və ya köhnə linkdə yeni məktub istəmək olur. 60 Node, 79 brauzer və yeni səhifəyə aid 15 görünüş yoxlaması keçib. Əhatə: [DEDICATED_RECOVERY.md](DEDICATED_RECOVERY.md).

## Əvvəlki bərpa və məlumat səhifələri

Elanlardan sonra ayrıca məlumat menyusu göstərilir. [Dəstək xidməti](https://dunumcebis-droid.github.io/cenub-avto/support.html) və [Haqqımızda](https://dunumcebis-droid.github.io/cenub-avto/about.html) ayrıca səhifələrdir. Açıq brauzer səhifəsinə gələn bərpa keçidi də işlənir; istifadə edilmiş keçid aydın yenidən cəhd ekranını göstərir. 60 Node, 69 brauzer və 35 görünüş yoxlaması keçib; bütün 61 statik fayl canlıda tutuşdurulub. Əhatə və məhdudiyyətlər: [RECOVERY_SUPPORT_PAGES.md](RECOVERY_SUPPORT_PAGES.md).

## Əvvəlki dəstək və footer düzəlişi

«Dəstək xidməti ilə əlaqə» bölməsinə `0709091997` və `cenubavtoelan@gmail.com` əlavə olunub. Footer və admin/alət düymələri telefonda bir-birini örtmür. 58 Node, 35 mövcud brauzer sınağı və 21 görünüş yoxlaması keçib. Sübutlar: [SUPPORT_FOOTER_VERIFICATION.md](SUPPORT_FOOTER_VERIFICATION.md). Parol bərpasında Gmail SMTP istifadə olunur; göndərən ünvanı `cenubavtoelan@gmail.com`-dur. Ümumi quraşdırma bələdçisi: [EMAIL_SENDER_SETUP.md](EMAIL_SENDER_SETUP.md).

## Əvvəlki VIP bildirişi düzəlişi

Admin elan kartında VIP/paket sorğusu və təsdiq vəziyyəti görünür; kartdan dəqiq paket sorğusuna keçmək olur. Paket təsdiqi və elanın yayımı ayrı əməliyyatlardır. Satıcının göndəriş nəticəsi saytın öz bildirişində göstərilir, kartla ödənişin hələ aktiv olmadığı paket seçimindən əvvəl bildirilir. 58 Node, 65 brauzer və bu dəyişikliklərə aid 41 baza yoxlaması keçib. Sübutlar: [PACKAGE_FEEDBACK_VERIFICATION.md](PACKAGE_FEEDBACK_VERIFICATION.md).

## Əvvəlki bütöv yoxlama

Kartlar, admin, parol bərpası, BMW seçimi, nəsil məlumatı və müqayisə axını təkrar yoxlanıb. 58 Node, 54 brauzer və 74 baza sınağı keçib. Əhatə, tapılıb düzəldilmiş hallar və canlı yoxlama sübutları [FULL_RECHECK.md](FULL_RECHECK.md) sənədindədir.

## Cari düzəlişlər

- Marka, model, qiymət, il, yürüş və texniki məlumatlar baza sütunlarından və əvvəlki `ca_data` formatlarından oxunur. Boş yürüş `null`, daxil edilmiş sıfır isə `0 km` olaraq qorunur.
- Redaktə forması təchizat seçimlərini və şəkillərin bölmələrini bərpa edir. Yeni şəkil seçilməyən bölmələr, mövcud şəkil sırası və kataloqda olmayan köhnə təchizat dəyərləri saxlanılır.
- Elan yaratma, redaktə və silmə serverin qaytardığı elan ID-si ilə təsdiqlənir. Heç bir sətri dəyişməyən sorğu uğur kimi göstərilmir. Silmə şəkilləri və ödəniş tarixçəsini saxlayan arxivləşdirmədir (`silindi`).
- Redaktədə cari paket saxlanılır; yeni paket yalnız ayrıca seçildikdə istənilir. VIP, Premium və Standart müddətləri müvafiq olaraq 15, 5 və 3 gündür; faktiki paket bazanın təsdiqlənmiş vəziyyətindən və bitmə tarixindən oxunur.
- Elan siyahısı serverdə süzülür və sıralanır, səhifədə 24 elan göstərilir. Ümumi say üçün kodda əvvəlki 500 elan məhdudiyyəti yoxdur. Satıcının elanları ayrıca 100-lük hissələrlə oxunur.
- «Bu gün təsdiqlənən» göstəricisi server hesabından gəlir; sıfır düzgün göstərilir. Uğursuz sorğu əvvəlki uğurlu məlumatları silmir, köhnə sorğu cavabı yeni səhifəni əvəz etmir.

Serverdə səhifələmə və elan idarəetməsi üçün `20261107060719_fix_listing_management_and_paginated_browse` Supabase miqrasiyası tətbiq edilib; 59 geri qaytarılan SQL yoxlaması keçib. Tətbiq olunan SQL-in istinadı [database/applied-listing-management.sql](database/applied-listing-management.sql) faylındadır. Əvvəlki kart düzəlişləri canlı saytda yoxlanıb. Admin panelinin səhifələməsi, təsdiqdən sonra yenilənmə və parol bərpası axınının yeni sübutları [ADMIN_AUTH_VERIFICATION.md](ADMIN_AUTH_VERIFICATION.md), əvvəlki mərhələnin nəticələri isə [VERIFICATION.md](VERIFICATION.md) sənədindədir.

## Admin və parol bərpası

Admin elanları və paket sorğuları serverdə axtarılır və 24-lük səhifələrə bölünür. Təsdiqdən sonra əsas siyahı, VIP hissəsi və sayğac yenilənir. Girişdə «Şifrəni unutdum» axını, bərpa linkinin doğrulanması və yeni parol forması var. Real e-poçtun çatdırılması SMTP/yönləndirmə ayarlarından asılıdır; bu asılılıqlar və sınaq əhatəsi [yoxlama sənədində](ADMIN_AUTH_VERIFICATION.md) göstərilib.

## Fayllar və şəkillərin qorunması

- `index.html`: səhifənin quruluşu; əvvəlki 12,47 MB əvəzinə təxminən 46 KB.
- `assets/site.css`: əvvəlki 9 stil blokunun ardıcıllığı qorunmuş vahid stil faylı.
- `assets/js/01-main.js`: elanlar, hesab, redaktə, filtrlər və əsas interfeys. İlkin digər 7 faylın ardıcıllığı qorunub. Əlavə `00-auth-callback.js` URL-i resurslardan əvvəl təmizləyir, `09-auth.js` isə parol bərpasını idarə edir.
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
