# Cənub Avto — düzəliş və yoxlama qeydləri

Əsas versiya: `09753f2298937e8cf7e0bfb2369497ac03774a5b` (`main`).

## Dəyişikliklər

- Kart şəkli öz çərçivəsində qalır; VIP nişanı şəkli örtmür. Şəkil faylları və URL-ləri dəyişdirilməyib.
- Marka, model, qiymət, il, yürüş və texniki məlumatlar baza sütunlarından və köhnə `ca_data` formatlarından düzgün oxunur.
- `0 km` saxlanılır; boş qiymət və il uydurma `0` ilə göstərilmir. Yürüş `km` vahidi ilə göstərilir.
- Əsas siyahı, seçilmişlər, satıcı kabineti, ətraflı baxış və müqayisə eyni məlumatlardan istifadə edir.
- Rəqəm aralıqları və qiymət sıralaması boş və sıfır dəyərləri ayırır. VIP sıralama üstünlüyü saxlanılır.
- Klaviatura ilə seçilmişlərə və müqayisəyə əlavə etmək səhvən ətraflı baxışı açmır.
- Elan sorğusu uğursuz olarsa, sayt bunu boş elan siyahısı kimi göstərmir; təkrar yükləmə düyməsi görünür.

## Avtomatik yoxlamalar

```sh
node --test --test-isolation=none --test-reporter=spec tests/listing-data.test.cjs
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*_browser.py' -v
git diff --check
```

- 14 Node testi: məlumat çevrilməsi, köhnə formatlar, sıfır/boş sahələr, rəqəmlər, sıralama, şəkil istinadları və VIP uyğunluğu.
- 7 Chromium testi: 1440, 768, 375 və 320 px ekranlarda mətn və şəkil həndəsəsi; filtr, sıralama, seçilmişlər, müqayisə, kabinet, klaviatura, xəta və təkrar yükləmə.
- Bütün 8 JavaScript blokunun sintaksisi `node --check` ilə yoxlanılıb.
- Brauzer testləri şəbəkə cavablarını sınaq məlumatları ilə əvəz edir; həqiqi bazaya yazmır.
- Python testləri üçün `playwright` və Chromium tələb olunur. Lazım gəlsə `CHROMIUM_PATH` ilə Chromium yolunu göstərin.

## Şəkillərin və mövcud funksiyaların qorunması

56 daxili `data:image` dəyəri ilkin GitHub versiyası ilə bayt səviyyəsində eynidir.
Bu dəyərlərin yeni sətirlə birləşdirilmiş siyahısının SHA-256 izi:

`731611a07c211e10ff4fef10b080b5c9ea5975462cca0717059cb9c53d641295`

Paket uyğunluğu və sıralaması, elan payload-u, şəkil hazırlama/yükləmə, serverə yazma/silmə və qalereya məlumatlarını oxuma funksiyalarının kodu dəyişdirilməyib.

## Elanların real API ilə yoxlanması

İlkin açıq sorğu `401 / 42501 — permission denied for table elanlar` qaytarırdı. İstifadəçinin konkret təsdiqindən sonra yalnız elanların 28 açıq sütununa SELECT icazəsi verildi. Saytın sorğusu bu sütunları açıq sadalayır; daxili admin qeydi sorğulanmır.

Açıq API indi HTTP 200 qaytarır: 2 aktiv elan görünür, 5 gözləyən elan görünmür. Daxili admin qeydinə giriş rədd edilir. Mövcud RLS siyasətləri və daxil olmuş istifadəçilərin icazələri saxlanılıb. Bütün 7 elanın məlumat, şəkil və paket hash-ləri dəyişməyib.

Real anonim API ilə yerli HTML brauzer yoxlaması uğurludur: 2 real şəkil yüklənib, kartların məlumatları və detallar düzgündür, 1440/375 px görünüş və 1 VIP elan təsdiqlənib. Canlı yayımdan sonra HTML-nin test edilmiş faylla eyniliyi və real kartlar ayrıca yoxlanır.

Tətbiq olunan SQL və yoxlamalar [PUBLIC_LISTING_ACCESS.md](PUBLIC_LISTING_ACCESS.md) sənədindədir.

## Mövcud məsləhət qeydləri

Dəyişiklikdən əvvəl və sonra Supabase təhlükəsizlik məsləhətləri eynidir; bu oxuma icazəsi yeni xəbərdarlıq yaratmayıb. Admin/ödəniş cədvəllərində siyasətin olmaması, mövcud SECURITY DEFINER funksiyaları və parol qorunması bu məhdud düzəlişdə dəyişdirilməyib. İstinadlar: [RLS siyasətləri](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy), [anon funksiyalar](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable), [daxil olmuş istifadəçi funksiyaları](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable), [parol qorunması](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
