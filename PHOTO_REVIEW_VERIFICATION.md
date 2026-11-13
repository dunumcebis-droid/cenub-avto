# Avtomobil şəkillərinin bölmə və məzmun yoxlaması

**Avtomatik tanıma hazırda aktiv deyil.** API hesabı/açarı qoşulmayıb və real modelin dəqiqliyi sınaqdan keçirilməyib. Hazırkı sayt şəkilləri admin yoxlamasına göndərir. Aşağıdakı kod, xəbərdarlıqlar və qoruma mexanizmləri xidmətin təhlükəsiz qoşulması üçün hazırlanıb; avtomatik tanımanın indi işlədiyini göstərmir.

## Hazırlanan davranış

Ön, arxa, yan, salon, mühərrik və digər avtomobil detalı üçün ayrıca qayda göstərilir. Xidmət aktiv olanda yeni şəkil serverdə qiymətləndirilir. Ön şəkli arxa bölməyə və ya arxa şəkli ön bölməyə qoymaq, görünən ekran interfeysi və əlaqəsiz şəkil seçmək uyğun xəbərdarlıqla göndərişi dayandırır. Qeyri-müəyyən nəticə də təsdiq sayılmır. Xidmət xətasında şəkil gizlicə adi yükləməyə ötürülmür, formadakı məlumatlar qalır.

Qəbul edilmiş şəkli server özü saxlayır. Baza təsdiqi hesab, bölmə, yol və SHA-256 izi ilə bağlayır. Başqa hesaba/bölməyə aid təsdiq və brauzerdən yazılmış saxta təsdiq qəbul edilmir. `checked` qovluğundakı şəkli brauzer dəyişə və silə bilmir. Köhnə şəkillər yalnız öz elan və əvvəlki bölməsində saxlanılır; yeni bölməyə köçürülmə yeni yoxlama tələb edir. Qalereya və əsas şəkil də yoxlanılır.

## Yoxlama əhatəsi

- Serverin 18 ayrıca sınağı: giriş, CORS, söndürülmüş/hazır olmayan xidmət, ölçü və tip həddi, nəticə sxemi, yanlış bölmə, ekran interfeysi, əlaqəsiz və qeyri-müəyyən nəticə, provayder xətası, limit, saxlanan baytların izi, təsdiq və uğursuzluq təmizləməsi. Model cavabları imitasiya edilib.
- Yeni 14 brauzer sınağı: ön/arxa xəbərdarlığı, ekran/əlaqəsiz şəkil, qeyri-müəyyən nəticə, forma və faylların qorunması, uğurlu yoxlamadan gələn URL-in istifadə olunması, etibarsız cavabların rəddi, hesab dəyişikliyi və eyni faylın başqa bölməyə köçürüləndə təkrar yoxlanması. HTTP tam əvəz edilib.
- `tests/photo-review-db.sql`: mövcud giriş rolları ilə 9 yoxlama qrupu, o cümlədən icazə, təsdiqin düzgünlüyü, şəkil yolu, hesab/bölmə, qalereya, köhnə şəkil istisnası və 121-ci sorğunun limitə düşməsi. Sintetik sətirlər və xidmətin müvəqqəti bayrağı `ROLLBACK` edilib. Real şəkil baytları yaradılmayıb.
- Mövcud elanların, paket sorğularının və şəkil obyektlərinin izləri əvvəlki təsdiqlənmiş izlərlə eynidir. Yeni təhlükəsizlik xəbərdarlığı yoxdur; yeni şəxsi cədvəllərdə yalnız server rolu üçün açıq şəkildə göstərilmiş RLS qaydaları var.
- Yayımlanmış Edge Function girişsiz status sorğusunu `401 auth_required` ilə rədd edir. Xidmət RPC-si də girişsiz və adi istifadəçi roluna açılmır. DB statusu `enabled:false`, real təsdiq sətrləri `0`-dır.

Tam avtomatik dəst: **78 Node və 161 Chromium brauzer sınağı** keçib. JavaScript sintaksisi və `git diff --check` keçib. Canlı statik faylların yoxlama nəticəsi istifadəçiyə ayrıca bildirilir. Canlı qarşılıqlı sınaqlarda da provayder/yazma əməliyyatları əvəz edilir; real provayderə şəkil, ödəniş, SMS və e-poçt göndərilmir.

## Aktivləşdirmədən əvvəl

[PHOTO_REVIEW_SETUP.md](PHOTO_REVIEW_SETUP.md) üzrə provayder hesabı/açarı və uyğun model qoşulmalıdır. Real düzgün və yanlış şəkillərlə tanıma dəqiqliyi yoxlanıldıqdan sonra baza bayrağı ayrıca açılır. Açarlar brauzerə və GitHub-a yazılmır.

Görünən ekran interfeysi aşkar edilə bilər; ekran görüntüsündən bütün interfeys kəsilərək yalnız avtomobil saxlanılıbsa, onun mənbəyini hər dəfə müəyyən etmək mümkün deyil. Elanın son yayımı üçün admin təsdiqi saxlanılır.
