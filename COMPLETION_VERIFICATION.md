# Qalan elan platforması funksiyaları

## 13 noyabr 2026 — yeni beş funksiya

Bu bölmə yeni kodun davranışını və yerli yoxlamalarını təsvir edir. Aşağıdakı əvvəlki mərhələnin tətbiq/yayım nəticələri öz tarixçəsi ilə saxlanılıb; yeni SQL və statik faylların canlıda tətbiqi üçün ayrıca təsdiq tələb olunur.

1. **Şəkil sırası və əsas şəkil.** `19-photo-manager.js` köhnə və yeni şəkli ayrıca silir, eyni bölmədə sıranı dəyişir və ★ ilə əsas şəkli seçir. Yeni seçim köhnə şəkilləri avtomatik əvəz etmir. Yeni şəkil əlavə ediləndə bölmə başına 6 və elan başına 36 həddi saxlanılan + yeni cəminə tətbiq olunur. Əvvəldən limitdən böyük köhnə bölmə öz əvvəlki şəkillərini saxlayaraq azaldıla və sıralana bilər; bu istisna yeni şəkil əlavə etməyə icazə vermir. Əvvəlki təsdiqlənmiş şəkillər öz hesab/bölməsində qala bilər; yeni fayllar eyni real tanıma yolundan keçir. Məlumat, yüklənən fayl, təsdiq və müvəqqəti URL-lər hesab dəyişməsində təmizlənir.
2. **Satılıb.** `ca_mark_listing_sold` yalnız cari satıcının elanını `is_sold=true` edir. Mənbə elanı, şəkillər və paket tarixçəsi silinmir. Açıq RLS/siyahı/paylaşım nəticəsindən çıxır; sahibinin kabinetində «Satılıb · Şəxsi arxiv» qalır. Sahib redaktə etmir, ayrıca arxivləşdirə bilər. Admin sold/satilib kartında yayım statusu dəyişən düymə yoxdur; ayrıca satılmış filtr var. Xətada elan siyahıdan uğur kimi çıxarılmır.
3. **Təxmini şəxsi statistika.** Satıcının öz ID-ləri 100-lük qruplarla soruşulur; başqa satıcının göstəriciləri qaytarılmır. Baxış yalnız aktiv açıq elanın detalları açıldıqda, zəng kliki yalnız `tel:` düyməsinə toxunanda qeyd olunur. Sahibin və admin/şəxsi baxışın hadisələri sayılmır; həqiqi zəng və unikal şəxslər ölçülmür. Sorğu interfeysi bloklamır.
4. **Şikayət və admin baxışı.** Giriş tələb olunur; yalnız başqasının aktiv, satılmamış elanı üçün səbəb və ən çox 1000 simvolluq izah göndərilir. Eyni açıq şikayət təkrarlanmır. Admin 24-lük səhifə və status filtri ilə baxır, «Həll edildi»/«Əsassızdır» qərarı və daxili qeyd saxlayır. Şikayət elanı avtomatik gizlətmir. Mətnlər HTML kimi işə salınmır.
5. **Saxlanılan axtarış və sayt bildirişi.** Ad, əsas/əlavə filtrlər, təchizat, paket və sıralama saxlanılır; hesab üzrə 20 axtarış həddi var. Kabinetdən tətbiq ediləndə uyğun forma və 1-ci nəticə səhifəsi açılır; silmə uğursuzdursa seçim qalır. Sonradan təsdiqlənən uyğun elanlar üçün şəxsi bildiriş yaranır. 24-lük səhifə, oxunmuş işarəsi, hamısını oxuma və aktiv elana keçid var. Keçid keşə kor-koranə etibar etmir: elanın hazırda açıq olması yenidən soruşulur. E-poçt/SMS yoxdur.

### Giriş və məxfilik

- Yeni 7 cədvəl API-yə açılmayan `ca_private` sxemindədir. RLS aktivdir; `anon`/`authenticated` üçün birbaşa cədvəl icazəsi yoxdur. İctimai `SECURITY INVOKER` RPC-ləri məhdud daxili funksiyaları çağırır. Özəl əməliyyatlarda `auth.uid()`, admin əməliyyatlarında cari admin üzvlüyü yoxlanır; profilin dəyişdirilə bilən iddiası admin icazəsi deyil.
- Axtarışlar və bildirişlər cari hesaba aiddir. Şikayətlər və daxili qeydlər açıq elan məlumatı deyil. Gecikmiş cavablar hesab dəyişəndə başqa hesabın DOM/cache/bildiriş nişanını doldura bilmir.
- Statistikaya brauzerdə yaradılmış təsadüfi UUID və gündəlik təkrar qeydləri xidmət edir; IP, user-agent və cihaz barmaq izi bu sayğacın mənbəsi deyil. UUID serverdə günə bağlı heşlənir. Bazada elan, hadisə növü, gün və heş təkrar sayılmanı azaldır.
- İki gündən köhnə günlük izlərin təmizlənməsi yeni sorğularda 100-lük hissələrlə aparılır. Bu, təxminən bir neçə günlük işçi tarixçədir, dəqiq 48 saatlıq avtomatik silinmə zəmanəti deyil; sorğu olmadıqda və ya növbə qalanda köhnə iz qala bilər. `listing_stats` cəmləri elan saxlanıldığı müddətdə qalır. Yeni brauzer/cihaz və yerli yaddaşın təmizlənməsi səbəbindən rəqəmlər təxminidir.
- Bildiriş sorğusu yalnız görünən səhifə və daxil olmuş hesab üçün təkrarlanır. Təsdiq növbəsi serverdə 100-lük hissələrlə emal olunur; qalan iş məhdud aralıqlarla davam edir. Sistem kənar məktub və SMS yaratmır.

### Bu mərhələnin yoxlama sübutu

- `tests/test_photo_manager_browser.py`: **14/14** imitasiya edilmiş Chromium sınağı. Əsas şəkil/sıra, mövcud şəkillərin qorunması, tək silmə, önbaxış URL təmizliyi, saxlanma zamanı kilid, təsdiqin təkrar istifadəsi, xəta/təkrar cəhd və 320 px idarəetmə əhatə olunur.
- `tests/test_marketplace_browser.py`: **15/15**, inteqrasiya edilmiş CSS və skriptlərlə **18,648 saniyə**. 105 sahib elanı üçün 100-lük statistika, satılıb uğur/xəta, VIP/şəkil qorunması, günlük baxış/zəng kliki təkrarı, giriş və admin baxışının ayrılması, XSS, admin qərarı, tam filtr bərpası, bildirişin 24+1 səhifəsi/növbə emalı və hesab dəyişməsində köhnə cavablar yoxlanıb. Satılmış admin kartında `[data-status]` düyməsi yoxdur; 320 px dialoqda üzən alətlər gizli və `inert` olur.
- `tests/assets.test.cjs`: 18 klassik skriptin ardıcıllığı (`19-photo-manager` → `20-marketplace`) və ilkin şəkil baytları üzrə qoruyucu yoxlama keçib. Dəyişmiş JavaScript sintaksisi və `git diff --check` keçib.
- Brauzer API cavabları tam sınaq məlumatları ilə əvəz edilib. Bu sınaqlar real elan, ödəniş, şəkil, hesaba giriş, şikayət, bildiriş, e-poçt və SMS yaratmır. Onlar SQL/RLS-in canlıda işlədiyinin sübutu deyil.
- `tests/marketplace-features-db.sql` üzrə **155**, `tests/photo-manager-legacy-subsets-db.sql` üzrə **27** baza yoxlaması keçib. Sınaq məlumatları `ROLLBACK` ilə geri qaytarılıb. Hər iki miqrasiya canlı bazaya tətbiq edilib; mövcud elanlar və paket məlumatları dəyişdirilməyib.

Ümumi yerli yoxlama: **102/102 Node**, **208/208 brauzer** (313,579 saniyə) və ayrıca son əlavə edilən qəzalı avtomobil forması sınağı **1/1** keçib. Birlikdə cari 209 brauzer ssenarisi əhatə olunub. Yoxlama həm də qeyri-müəyyən ilk saxlamadan sonra redaktəyə keçərkən seçilmiş faylın iki dəfə əlavə olunması xətasının düzəlişini və silmə/əsas şəkil/upload keşinin qorunmasını əhatə edir.

### Qəzalı avtomobillər

Elan formasında «Vəziyyəti → Qəzalı» seçimi var; qəza tarixçəsi ayrıca saxlanılır. Şəkil tanıma təlimatı qəzalı, təmir olunmamış və bəzi detalları olmayan avtomobili sırf zədəyə görə rədd etməməyi tələb edir. Görünüş və ekran interfeysi qaydaları saxlanılır. `ca-photo-review` versiya 5 canlıdır, JWT yoxlaması aktivdir. 102 Node sınağı, o cümlədən tək və qrup sorğularında bu təlimatın qorunması keçib. Bu, modelin bütün mümkün zədə şəkillərini səhvsiz tanıması haqqında iddia deyil.

### ZIP ehtiyat nüsxənin yeni əhatəsi

Əvvəlki ixrac yalnız 5 mənbəni tanıyırdı. `database/marketplace-backup.sql` və uyğun `14-server-backup.js` sabit siyahını 12 mənbəyə genişləndirir: `elanlar`, `paket_sorgulari`, `profiller`, `adminler`, `storage_objects`, `listing_stats`, `listing_events`, `listing_reports`, `saved_searches`, `approved_listing_events`, `notification_progress`, `search_notifications`.

`tests/test_server_backup_browser.py` üzrə **7/7** imitasiya edilmiş brauzer sınağı **18,633 saniyədə** keçib. ZIP açılaraq bütün 12 mənbənin sətirləri, o cümlədən 100-dən çox günlük və təsdiq növbəsi sətrinin səhifələri, şəkil baytları və manifest yoxlanıb. İtən/təkrar/yad mənbə, səhv heş, dəyişən manifest və hesabdan çıxış natamam yükləmə yaratmır.

Hazırlanmış SQL ayrıca **PGlite 0.5.16** PostgreSQL mühitində yalnız sintetik sxem və məlumatlarla iki dəfə tətbiq edilərək yoxlanıb. `tests/admin-preview-export-db.sql` dəstinin 9 nəticə qrupu, 205-sətirlik qeyri-UUID açar mənbələrinin səhifələnməsi, iki hesablanmış indeksin UUID cursor sorğusunda istifadəsi və tarix formatından asılı olmayan açarlar keçib. Bu yoxlama real Supabase məlumatını oxumayıb, canlı miqrasiya tətbiq etməyib və real ZIP yükləməyib.

Yeni məlumatlara giriş əvvəlki admin yoxlamasından keçir; təxmin edilən mənbə adını göndərməklə başqa cədvəl ixrac edilmir. Səhifə/cursor, sətir heşi, sətir sayı və yekun manifest uyğunluğu saxlanılır. Mənbə cədvəlləri və məxfi Auth məlumatları ictimai rol üçün açılmır. ZIP miqrasiyası da canlı bazaya tətbiq edilib. Yenilənmiş `tests/admin-preview-export-db.sql` bütün 12 mənbə üzrə səhifə/hash, icazə və parametr yoxlamalarını canlı bazada yalnız oxuma ilə keçib; nəticələr tranzaksiyadan sonra say və yoxlama adları ilə qaytarılıb. Real ZIP yüklənməyib.

ZIP şəxsi axtarış, şikayət və daxili qeydləri, eləcə də o anda qalan günlük izləri daşıyır. Onu məxfi saxlamaq lazımdır; server təmizləməsi əvvəl yüklənmiş faylı silmir. Yeni klik/baxış ixrac zamanı cəm və manifesti dəyişərsə yoxlama uğursuz ola bilər. Bu halda sakit vaxtda yenidən cəhd edilməlidir; alət uyğunsuz nüsxəni uğurlu kimi göstərməməlidir. İxrac atomik baza snapshot-u deyil.

## Əvvəlki tamamlanma mərhələsi

## Yekun davranış

- Açıq elanlarda hər səhifədə 24 nəticə var. 0–24 nəticədə səhifələmə gizlidir; 25-dən başlayaraq əvvəlki/növbəti və 1, 2, 3… nömrələri görünür. Çox sayda səhifədə cari səhifəyə yaxın düymələr və ilk/son səhifə saxlanılır; bütün nömrələr bir anda yığılmır.
- Elanın «Paylaş» düyməsi yalnız həmin açıq elanın `?ad=UUID` linkini paylaşır/kopyalayır. Yeni telefonda link səhifədə yüklənmiş nəticələrdən asılı olmadan ayrıca anonim, yalnız `aktiv` elan sorğusu ilə açılır. Gözləyən/rədd edilmiş elanlar, yanlış linklər, admin baxışı və bərpa tokenləri paylaşılmır.
- Admin hər kartdan «Şəkillər və tam məlumat» baxışını açır: tam təsvir, bütün məlumatlar, 36-dək şəkil və tam ekran qalereyası. İcazə hər sorğuda serverdə cari admin üzvlüyü ilə yoxlanır. Şəxsi baxış açıq siyahı/cache-ə əlavə olunmur, bağlananda və hesab dəyişəndə DOM və yaddaşdan təmizlənir.
- Yeni `terms.html` və `privacy.html` səhifələri faktiki xidmət, qiymət/müddətlər, moderasiya, açıq telefon/fotolar, arxiv və tam silinmə üçün dəstək yolunu izah edir. Şirkət/VÖEN/ünvan və saxlanma müddəti uydurulmur. Əsas footer-lər, qeydiyyat və elan formaları bu səhifələrə keçid verir; əvvəlki demo mətni qaydalar pəncərəsindən çıxarılıb.
- Ehtiyat nüsxə aləti yalnız admin üçün serverdən elanlar, paket sorğuları, profillər, admin siyahısı və bütün cari `elan-sekilleri` obyektlərinin baytlarını ZIP-ə yığır. Məxfi Auth parolları/tokenləri və server sistem ayarları ixrac edilmir. Bu, tətbiq məlumatlarının nüsxəsidir; PostgreSQL disk nüsxəsi deyil. Sətir sayı, ardıcıl səhifə hash-ləri və son server manifesti yoxlanmadan uğur göstərilmir. Şəkil çatışmazlığı, məlumat dəyişikliyi, dayandırma və hesab dəyişməsi natamam uğur yaratmır. Dəstəklənən brauzerdə birbaşa fayla yazılır; Blob rejimində 512 MiB, ZIP32 formatında 4 GiB həddi aşılarsa aydın xəta verilir, məlumat kəsilmir.
- Şəxsi kabinetdə SMS provayderi üçün hazır telefon təsdiqi axını var. Provayder bağlıdırsa kod göndərildiyi iddia edilmir. Aktiv provayderdə koddan sonra serverin cari hesab üzrə `phone_confirmed_at` sübutu yoxlanır; dəyişdirilə bilən profil iddiası etibarlı sayılmır. E-poçtla giriş və bərpa saxlanılır.

## Baza və icazələr

`admin_detail_and_verified_application_export` miqrasiyası tətbiq edilib. [SQL istinadı](database/admin-read-export.sql). İmtiyazlı oxuma funksiyaları API-yə açılmayan `ca_private` sxemindədir; ictimai RPC-lər `SECURITY INVOKER`-dir. Anonim EXECUTE yoxdur; daxil olmuş adi istifadəçi və saxta `user_metadata.admin=true` iddiası rədd edilir. Parametrlər resurs allowlist-i, UUID cursor və 1–200 səhifə ölçüsü ilə məhduddur.

[Gerçək bazada read-only yoxlama](tests/admin-preview-export-db.sql) bütün beş mənbənin səhifələnməsini və hash bərabərliyini, tam admin baxışını, anonim/adi hesab rəddini və yanlış parametrləri yoxlayıb. Tranzaksiya geri qaytarılıb. Əvvəl/sonra bütün tətbiq cədvəllərinin və şəkil metadatasının hash-ləri eynidir. Yeni təhlükəsizlik məsləhəti yaranmayıb.

## Sınaqlar

- 60/60 Node, əvvəlki 46 şəkil və 56 istinadın eyniliyi daxil olmaqla.
- 117/117 brauzer sınağı, 173,025 saniyə. Bütün API cavabları sınaq məlumatları ilə əvəz olunur; real elan, ödəniş, parol, SMS və ya e-poçt dəyişikliyi edilmir.
- Yeni ssenarilər: 7 səhifə/paylaşım, 6 admin baxışı, 6 ZIP nüsxə, 6 telefon təsdiqi. ZIP faylları ayrıca oxunaraq sətirlər, orijinal foto baytları, CRC və SHA-256 yoxlanır; streaming və Blob çıxışı əhatə olunur.
- 12 mətn/görünüş və 12 gerçək qaydalar/məxfilik səhifəsi ölçüsü 240–1440 px aralığında keçib. JavaScript sintaksisi və diff formatı yoxlanıb.

## Xarici xidmətlər

Real bank ödənişi VÖEN/ABB merchant müqaviləsi və bank girişlərini gözləyir. SMS xidməti hesabı olmadığı üçün real SMS aktivləşdirilməyib. Heç bir ödənişli xidmət açılmayıb və real göndəriş edilməyib. Hazır addımlar: [SMS_SETUP.md](SMS_SETUP.md), [PAYMENT_SETUP.md](PAYMENT_SETUP.md).
