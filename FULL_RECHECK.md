# Bütöv təkrar yoxlama — 7 noyabr 2026

İstifadəçinin yeni funksiyalar bildirməzdən əvvəl istədiyi tam yoxlama aparılıb. Baza sxemi dəyişdirilməyib. Canlı elanlara, yüklənmiş şəkillərə və parollara dəyişiklik edilməyib; yeni e-poçt göndərilməyib.

## Tapılıb düzəldilən əlavə hallar

1. **BMW modellərinin ilk siyahısı natamam idi.** X5/X3/Z4/i3/iX kimi modellər axtarış yazılmadan görünmürdü. İlkin 1–8 Series bölmələri saxlanılıb, qalan yerli və uzaq kataloq modelləri əlavə edilib. Yazılı axtarış da eyni qruplaşdırılmış görünüşdən istifadə edir. Əvvəllər yazılı X5 axtarışı işləyirdi; problem ilk baxışda modellərin gizli qalması idi.
2. **Müqayisə əvvəlki məlumatı saxlayırdı.** Elanın qiyməti/yürüşü yeniləndikdə açıq müqayisə köhnə obyekti göstərirdi. İndi yeni server məlumatı tətbiq olunur. Səhifədən kənarda qalan seçilmiş elan saxlanılır; təsdiqlənmiş arxiv/redaktə/rədd əməliyyatından sonra qeyri-ictimai elan çıxarılır və köhnə keşdən yenidən seçilə bilmir. Çıxış/hesab dəyişikliyində müqayisə təmizlənir.
3. **Marka/model dəyişəndə köhnə nəsil qalırdı.** İndi yeni marka və ya fərqli model köhnə nəsli silir. Yeni nəsil seçilmədən elan yadda saxlanmır; eyni model yenidən seçilərsə düzgün köhnə nəsil qorunur. Digər redaktə məlumatları və şəkillər saxlanılır.

Bu üç hal əvvəlcə saxta brauzer məlumatları ilə təkrar yaradılıb, sonra düzəldilib. Yeni funksiya və dizayn dəyişiklikləri bu mərhələyə əlavə edilməyib.

## Avtomatik yoxlama nəticəsi

| Dəst | Nəticə |
| --- | --- |
| Node — məlumat, payload, keş, sıralama, sessiya və şəkil eyniliyi | 58/58 keçib |
| Chromium — bütün mövcud axınlar və 19 yeni reqressiya ssenarisi | 54/54 keçib; 103,655 saniyə |
| Elan idarəetməsi və açıq səhifələmə SQL sınaqları | 59/59 keçib |
| Admin və paket sorğularının səhifələmə SQL sınaqları | 15/15 keçib |
| JavaScript sintaksisi və diff formatı | 10 fayl keçib, diff təmizdir |

Brauzer dəsti kartlar, filtr/sıralama, seçilmişlər, müqayisə, qalereya, klaviatura, redaktə, şəkil/avadanlıq qorunması, arxivləşdirmə, mobil görünüş, 500-dən sonrakı elanlar, 1000-dən sonrakı admin siyahısı, təsdiqdən sonra yenilənmə, parol bərpası və hesablar arasında gecikmiş sorğuları əhatə edir. Brauzer sorğuları tamamilə saxta cavablarla yoxlanır; real admin yazısı və parol dəyişikliyi edilmir.

SQL sınaqları həqiqi sxem və icazələrlə, yalnız yaradılan sınaq qeydləri üzərində `BEGIN … ROLLBACK` daxilində icra edilib. 600 ictimai elan və 1 205 admin elanı/paket sorğusu ilə limitlər və təkrarsız səhifələmə yoxlanıb. Mövcud **7 elan və 2 paket sorğusunun bütün sətir hash-ləri**, foto və paket məlumatları daxil olmaqla, əvvəl və sonra eynidir. Sınaq qeydi qalmayıb.

Hesabatlar: [frontend](tests/reports/full-recheck-frontend.json), [baza və məlumatların qorunması](tests/reports/full-recheck-db.json).

## Təhlükəsizlik məsləhətlərinin vəziyyəti

Yeni təhlükəsizlik məsləhəti yaranmayıb. Bağlı admin/ödəniş cədvəlləri və artıq yoxlanmış admin funksiyaları üçün əvvəlki [RLS](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) və [funksiya icazəsi](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable) qeydləri saxlanılır. [İstifadə olunmamış indeks](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index) və [çoxsaylı icazəverici siyasət](https://supabase.com/docs/guides/database/database-linter?lint=0006_multiple_permissive_policies) məsləhətləri də əvvəlki kimidir.

[Sızmış parol qorunması](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection) Free planında mövcud deyil; Pro və yuxarı plan tələb edir. Real kart ödənişi VÖEN və ABB merchant girişlərini gözləyir. Əvvəlki real bərpa məktubunun çatması və yeni parol ekranının açılması istifadəçi tərəfindən təsdiqlənib; bu yoxlamada əlavə məktub göndərilməyib.

## Canlı yayım

- Yoxlanmış tətbiq commit-i: [`750bf5ed1c188d44598dbe87fe6911132fd5ac4b`](https://github.com/dunumcebis-droid/cenub-avto/commit/750bf5ed1c188d44598dbe87fe6911132fd5ac4b).
- [GitHub Pages yayımı 42372286732](https://github.com/dunumcebis-droid/cenub-avto/actions/runs/42372286732) uğurla bitib. Sonrakı hesabat commit-i tətbiq fayllarını dəyişmir.
- 2 real aktiv elan və 1 VIP elan anonim API-də HTTP 200 ilə yoxlanıb. Gözləyən elan və daxili admin qeydi açılmayıb. Marka filtri və sıfırlama, real kart məlumatları, şəkillərin açılması, detallar, əlaqə linkləri və qalereya 1440/375 px ekranlarda uyğundur.
- Canlı BMW siyahısında X5/X3/Z4/i3/iX ilkin açılışda mövcuddur; yazılı M3 axtarışı qruplaşdırmanı saxlayır. Real elanlar müqayisəyə əlavə olunub və API yenilənməsindən sonra cədvəl cari məlumatlarla uyğun qalıb.
- Bərpa ekranı açılıb və etibarsız saxta token real Auth serverində rədd edilib; URL təmizlənib. Əlavə e-poçt və parol dəyişikliyi edilməyib.
- Bütün **59 statik fayl**, o cümlədən **46 dəyişdirilməmiş şəkil**, yoxlanmış məzmunla bayt səviyyəsində eynidir. Səhifədə JavaScript xətası və gözlənilməz yazı cəhdi yoxdur.
- Hesabatlar: [canlı brauzer/API](tests/reports/full-recheck-live.json), [bütün statik fayllar](tests/reports/full-recheck-static-live.json).

Əvvəlki mərhələlərin nəticələri [ADMIN_AUTH_VERIFICATION.md](ADMIN_AUTH_VERIFICATION.md) və [VERIFICATION.md](VERIFICATION.md) sənədlərində saxlanılır.
