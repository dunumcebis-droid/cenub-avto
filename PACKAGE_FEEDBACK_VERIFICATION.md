# VIP sorğusunun görünməsi və satıcı bildirişi — 7 noyabr 2026

Adminin elan kartı tələb edilən paketi, sorğunun vəziyyətini və bazada qeydiyyatda olan paketi ayrıca göstərir. «Paket sorğusuna bax» həmin sorğunun unikal ID-si ilə ödəniş hissəsini açır; eyni marka/model və sonrakı səhifələrdəki sorğular qarışmır. Gözləyən, rədd edilmiş və məlumatı çatışmayan paket üçün elanı yayımlamaq düyməsi bağlıdır. Paket təsdiqindən sonra elan ayrıca təsdiqlənir. Pulsuz elanların adi təsdiqi saxlanılıb.

Elan göndərilməsinin nəticəsi brauzerin domen başlıqlı `alert()` pəncərəsi əvəzinə saytın bildirişində göstərilir. Uğur yalnız server elan ID-sini qaytardıqdan sonra göstərilir. Saxlanmış elandan sonra siyahı yenilənməzsə, xəbərdarlıq onun artıq saxlandığını bildirir; uğursuz göndərişdə forma və seçilmiş şəkillər qorunur. Bildiriş çıxışda və hesab dəyişəndə bağlanır.

Kartla ödəniş hələ qoşulmayıb. Məbləğin tutulmadığı paket seçimindən əvvəl aydın göstərilir; uğur bildirişi yalnız müraciətin qəbulunu bildirir. Köhnə, yanlış «məlumatlar yalnız brauzerdə saxlanılır» qeydi çıxarılıb. Şəkillərə, VIP müddətlərinə və real elanların təsdiq vəziyyətinə dəyişiklik edilməyib.

## Yoxlamalar

| Dəst | Nəticə |
| --- | --- |
| Node: məlumat, payload, sessiya, şəkillərin bayt eyniliyi | 58/58 |
| Chromium: əvvəlki axınlar və 11 yeni paket/bildiriş ssenarisi | 65/65; 126,313 saniyə |
| Yeni admin paket metadatası SQL sınaqları | 26/26 |
| Mövcud admin/ödəniş səhifələmə SQL sınaqları | 15/15 |
| JavaScript sintaksisi və diff formatı | 10 fayl; təmiz |

Brauzer sınaqları saxta API cavabları və sintetik şəkil ilə işləyir; real elana və ya ödənişə təsdiq vermir. 375 px görünüş, uğursuz yükləmə/saxlama, sıfır sətrə yazı, təsdiqdən sonra yenilənmə xətası, dəqiq sorğuya keçid və paket təsdiqi ilə yayımın ayrılığı yoxlanıb. Sessiya yeniləməsi uğursuz olduqda əvvəlki bildiriş bağlanır və başqa hesabda görünmür. Bərpa e-poçtu yenidən göndərilməyib.

Son canlı vizual baxışda üzən alət panelinin bildirişdən yuxarı qaldığı görünüb. Yalnız `#listingFeedback` qat sırası və CSS keş açarı düzəldilib; bundan sonra 58 Node və 11 uyğun brauzer sınağı yenidən keçib (25,385 saniyə).

SQL sınaqları `BEGIN … ROLLBACK` daxilində həqiqi sxem və icazələrlə icra olunub. `20261107163916_admin_listing_package_feedback` miqrasiyası yalnız iki mövcud admin oxuma funksiyasını yeniləyir; imzalar, RLS və ictimai oxuma icazələri saxlanılır. SQL istinadı: [database/admin-package-metadata.sql](database/admin-package-metadata.sql).

Tətbiqdən əvvəl və sonra **8 elan və 3 paket sorğusunun bütün sətir hash-ləri eynidir**; şəkil və paket məlumatları da bu müqayisəyə daxildir. İctimai aktiv elan sayı 2 olaraq qalıb. İstifadəçinin bildirdiyi LADA 1200 admin funksiyasında VIP sorğusu ilə düzgün əlaqələnir; həm elan, həm də sorğu gözləmədə saxlanılıb. Real təsdiq edilməyib.

Hesabatlar: [frontend](tests/reports/package-feedback-frontend.json), [26 SQL yoxlaması](tests/reports/package-metadata-db-regression.json), [tətbiqdən sonrakı baza və təhlükəsizlik yoxlaması](tests/reports/package-feedback-postmigration.json).

Yeni imtiyazlı funksiya və təhlükəsizlik xəbərdarlığı yaranmayıb. Mövcud bağlı admin/ödəniş cədvəlləri və qorunan admin funksiyaları üzrə məsləhətlər hesabatda saxlanılır. [Sızmış parol qorunması](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection) Free planında aktiv edilə bilmir; plan dəyişdirilməyib.

## Canlı yayım

- Tətbiq commit-ləri: [4524330](https://github.com/dunumcebis-droid/cenub-avto/commit/45243300bfc9d04c3f8907c0e50457db54db0679) və son görünüş düzəlişi [a3a8333](https://github.com/dunumcebis-droid/cenub-avto/commit/a3a833339b850ff657435ff0f570bf23650cc2fc).
- Son tətbiq üçün [Pages yayımı 42393794728](https://github.com/dunumcebis-droid/cenub-avto/actions/runs/42393794728) uğurla bitib.
- Həqiqi saytda 1440 və 375 px görünüş, 2 aktiv elan və 1 VIP, kart məlumatları, şəkillər, detallar, əlaqə linkləri, qalereya, server filtri, BMW seçimi və müqayisə yenilənməsi keçib. İctimai cavabda gözləyən elan və daxili qeyd yoxdur.
- Yayımlanmış bildiriş köməkçisi ayrıca açılıb/bağlanıb; 375 px ekrana sığır, domen başlıqlı brauzer pəncərəsi yaratmır və üzən alət düymələrini örtür. Paket seçimindən əvvəl kartdan məbləğ tutulmadığı qeydi mövcuddur. Bu yoxlamada real elan göndərilməyib və real paket təsdiqi edilməyib. Admin ekranının vəziyyətləri saxta brauzer cavabları ilə, istifadəçinin bildirdiyi elanın metadatası isə real admin SQL oxuması ilə yoxlanıb.
- Bərpa ekranı və saxta etibarsız tokenin həqiqi Auth serverində rəddi yoxlanıb. Yeni e-poçt və parol dəyişikliyi yoxdur.
- Bütün **59 statik fayl**, o cümlədən **46 dəyişdirilməmiş şəkil**, yoxlanmış tətbiq commit-i ilə bayt səviyyəsində eynidir. JavaScript xətası və gözlənilməz yazı cəhdi yoxdur.
- Hesabatlar: [canlı brauzer/API](tests/reports/package-feedback-live.json), [bütün statik fayllar](tests/reports/package-feedback-static-live.json). Sonrakı hesabat commit-i tətbiq fayllarını dəyişmir.

Əvvəlki bütöv yoxlama: [FULL_RECHECK.md](FULL_RECHECK.md).
