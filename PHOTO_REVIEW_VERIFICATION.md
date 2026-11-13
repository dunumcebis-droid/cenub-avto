# Avtomobil şəkillərinin bölmə və məzmun yoxlaması

**Real tanıma normal, hesaba girişlə qorunan yolda yoxlanıb.** Düzgün ön, arxa, yan, salon, mühərrik və digər avtomobil detalı təsdiqləri mövcuddur; rədd cavabları da müşahidə edilib. Bu, real provayderin işlədiyini göstərir, dəqiqliyə dair universal zəmanət deyil. Son yayım üçün admin təsdiqi qalır.

## Sürət düzəlişi

- Ən çox 6 ayrı şəkil bir model sorğusunda yoxlanır; kollaj hazırlanmır və görüntü məlumatı azaldılmır.
- İki qrup sorğusu paralel işləyir. Brauzerdə eyni vaxtda yalnız iki orijinal şəkil hazırlanır; telefonda yaddaş yükü məhdudlaşır.
- Hazırlanmış JPEG faylı uğursuz cəhddə təkrar dekodlaşdırılmır. Əvvəl təsdiqlənmiş eyni baytlı şəkil yeni fayl obyekti ilə seçilsə də, həmin hesab/bölmədə yenidən modelə göndərilmir.
- Qarışıq nəticədə düzgün şəkillərin təsdiqi qalır; yalnız uğursuz şəkillər təkrar göndərilir.
- Hər qrupun nəticə indeksləri, sayı, sahibi, bölməsi və təsdiqlənmiş URL-ləri tam yoxlanır. Uyğunsuz cavab təsdiq sayılmır.
- Provayder cavabı üçün ayrıca vaxt həddi var: tək şəkil 12 saniyə, qrup 16 saniyə; server sorğusunun ümumi həddi 25 saniyədir. Bu hədlər istənilən internet bağlantısında yüklənmənin həmin vaxtda bitəcəyinə zəmanət deyil.

Sürətə aid brauzer sınağında 12 yeni şəkil iki paralel HTTP sorğusu yaradır. Qismən rədddən sonra yalnız rədd edilmiş şəkil göndərilir; dekoder sayı artmır. Bu sınaqlar şəbəkəni imitasiya edir, real provayderin yeni qrup gecikməsini ölçmür. Təhlükəsiz əməliyyat və dəqiqlik yoxlamaları `tests/photo-review-server.test.cjs`, `tests/test_photo_review_browser.py` və `tests/test_photo_batch_pipeline_browser.py` fayllarındadır.

## Hazırlanan davranış

Ön, arxa, yan, salon, mühərrik və digər avtomobil detalı üçün ayrıca qayda göstərilir. Xidmət aktiv olanda yeni şəkil serverdə qiymətləndirilir. Ön şəkli arxa bölməyə və ya arxa şəkli ön bölməyə qoymaq, görünən ekran interfeysi və əlaqəsiz şəkil seçmək uyğun xəbərdarlıqla göndərişi dayandırır. Qeyri-müəyyən nəticə də təsdiq sayılmır. Xidmət xətasında şəkil gizlicə adi yükləməyə ötürülmür, formadakı məlumatlar qalır.

Qəbul edilmiş şəkli server özü saxlayır. Baza təsdiqi hesab, bölmə, yol və SHA-256 izi ilə bağlayır. Başqa hesaba/bölməyə aid təsdiq və brauzerdən yazılmış saxta təsdiq qəbul edilmir. `checked` qovluğundakı şəkli brauzer dəyişə və silə bilmir. Köhnə şəkillər yalnız öz elan və əvvəlki bölməsində saxlanılır; yeni bölməyə köçürülmə yeni yoxlama tələb edir. Qalereya və əsas şəkil də yoxlanılır.

## Yoxlama əhatəsi

- Serverin 18 ayrıca sınağı: giriş, CORS, söndürülmüş/hazır olmayan xidmət, ölçü və tip həddi, nəticə sxemi, yanlış bölmə, ekran interfeysi, əlaqəsiz və qeyri-müəyyən nəticə, provayder xətası, limit, saxlanan baytların izi, təsdiq və uğursuzluq təmizləməsi. Model cavabları imitasiya edilib.
- Yeni 14 brauzer sınağı: ön/arxa xəbərdarlığı, ekran/əlaqəsiz şəkil, qeyri-müəyyən nəticə, forma və faylların qorunması, uğurlu yoxlamadan gələn URL-in istifadə olunması, etibarsız cavabların rəddi, hesab dəyişikliyi və eyni faylın başqa bölməyə köçürüləndə təkrar yoxlanması. HTTP tam əvəz edilib.
- `tests/photo-review-db.sql`: mövcud giriş rolları ilə 9 yoxlama qrupu, o cümlədən icazə, təsdiqin düzgünlüyü, şəkil yolu, hesab/bölmə, qalereya, köhnə şəkil istisnası və 121-ci sorğunun limitə düşməsi. Sintetik sətirlər və xidmətin müvəqqəti bayrağı `ROLLBACK` edilib. Real şəkil baytları yaradılmayıb.
- Mövcud elanların, paket sorğularının və şəkil obyektlərinin izləri əvvəlki təsdiqlənmiş izlərlə eynidir. Yeni təhlükəsizlik xəbərdarlığı yoxdur; yeni şəxsi cədvəllərdə yalnız server rolu üçün açıq şəkildə göstərilmiş RLS qaydaları var.
- Yayımlanmış Edge Function girişsiz status sorğusunu `401 auth_required` ilə rədd edir. Xidmət RPC-si də girişsiz və adi istifadəçi roluna açılmır. Ümumi və admin sınaq rejimləri ayrı bayraqlardır; admin sınağının icazəsi mövcud hesab girişi və `cenub_admin_yoxla` ilə yoxlanır. Xidmət açarı istifadəçinin admin icazəsini yoxlamaq üçün işlədilmir.

Əvvəlki mərhələnin tam avtomatik dəsti: **78 Node və 161 Chromium brauzer sınağı** keçib. JavaScript sintaksisi və `git diff --check` keçib. Canlı statik faylların yoxlama nəticəsi istifadəçiyə ayrıca bildirilir. Canlı qarşılıqlı sınaqlarda da provayder/yazma əməliyyatları əvəz edilir; real provayderə şəkil, ödəniş, SMS və e-poçt göndərilmir.

## Aktivləşdirmədən əvvəl

[PHOTO_REVIEW_SETUP.md](PHOTO_REVIEW_SETUP.md) üzrə qoşulmuş açarın real işləməsi və standart modelə giriş təsdiqlənməlidir. Real düzgün və yanlış şəkillərlə tanıma dəqiqliyi yoxlanıldıqdan sonra baza bayrağı ayrıca açılır. Açarlar brauzerə və GitHub-a yazılmır.

Görünən ekran interfeysi aşkar edilə bilər; ekran görüntüsündən bütün interfeys kəsilərək yalnız avtomobil saxlanılıbsa, onun mənbəyini hər dəfə müəyyən etmək mümkün deyil. Elanın son yayımı üçün admin təsdiqi saxlanılır.

## Cari sınaq mexanizmi

«Şəkilləri yoxla» düyməsi boş elan formasında da işləyir. Mövcud girişlə qorunan şəkil yoxlaması yolunu çağırır, elan sorğusu göndərmir, sahə və faylları saxlayır. Təsdiqlənmiş nəticə adi göndərişdə təkrar istifadə edilir. Qaytarılan məzmun, hesab, bölmə, status və fayl izi eyni server/baza qaydalarından keçir.
