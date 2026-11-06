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

- 13 Node testi: məlumat çevrilməsi, köhnə formatlar, sıfır/boş sahələr, rəqəmlər, sıralama, şəkil istinadları və VIP uyğunluğu.
- 7 Chromium testi: 1440, 768, 375 və 320 px ekranlarda mətn və şəkil həndəsəsi; filtr, sıralama, seçilmişlər, müqayisə, kabinet, klaviatura, xəta və təkrar yükləmə.
- Bütün 8 JavaScript blokunun sintaksisi `node --check` ilə yoxlanılıb.
- Brauzer testləri şəbəkə cavablarını sınaq məlumatları ilə əvəz edir; həqiqi bazaya yazmır.
- Python testləri üçün `playwright` və Chromium tələb olunur. Lazım gəlsə `CHROMIUM_PATH` ilə Chromium yolunu göstərin.

## Şəkillərin və mövcud funksiyaların qorunması

56 daxili `data:image` dəyəri ilkin GitHub versiyası ilə bayt səviyyəsində eynidir.
Bu dəyərlərin yeni sətirlə birləşdirilmiş siyahısının SHA-256 izi:

`731611a07c211e10ff4fef10b080b5c9ea5975462cca0717059cb9c53d641295`

Paket uyğunluğu və sıralaması, elan payload-u, şəkil hazırlama/yükləmə, serverə yazma/silmə və qalereya məlumatlarını oxuma funksiyalarının kodu dəyişdirilməyib.

## Canlı saytda aşkarlanan ayrıca maneə

Canlı `index.html` ilkin GitHub faylı ilə eynidir. Açıq ziyarətçi üçün Supabase elan sorğusunun cavabı:

```text
HTTP 401
code: 42501
message: permission denied for table elanlar
hint: GRANT SELECT ON public.elanlar TO anon
```

Frontend düzəlişi baza icazəsini dəyişmir. Buna görə canlı elanların tam işlədiyini hələ təsdiqləmək olmaz.

`supabase-listing-diagnostics.sql` faylının işlək hissəsi yalnız baza icazələrini və RLS qaydalarını oxuyur. Mümkün düzəliş şərh şəklində verilib: əvvəlcə RLS və ictimaiyyətə açıla biləcək sütunlar yoxlanmalıdır. Bu iş zamanı Supabase icazələri, elan qeydləri, VIP vəziyyətləri və yüklənmiş şəkillər dəyişdirilməyib.

İstifadəçi birbaşa `main` budağına göndərmə və canlı yoxlama üçün icazə verib. Frontend testləri ayrıca sınaq məlumatları ilə aparılıb. Canlı elanların tam yoxlanması Supabase-də ictimai oxuma icazəsinin bərpasını tələb edir.
