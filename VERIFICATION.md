# Cənub Avto — dəyişiklik və yoxlama qeydləri

Düzəlişlər `main`-ə göndərilib, Supabase miqrasiyası tətbiq edilib və GitHub Pages-də yayımlanmış versiya real elanlarla yoxlanıb. Aşağıdakı nəticələr 7 noyabr 2026-cı il yoxlamasına aiddir.

Əvvəlki açıq elan oxuma icazəsi haqqında [PUBLIC_LISTING_ACCESS.md](PUBLIC_LISTING_ACCESS.md) tarixi qeyd kimi saxlanılır. Oradakı elan sayları və yoxlama nəticələri əvvəlki mərhələyə aiddir.

## Elan məlumatları və görünüş

- Marka, model, qiymət, il, yürüş və texniki sahələr əsas baza sütunlarından və köhnə `ca_data` formatlarından oxunur. Düzgün sıfır ilə boş dəyər ayrılır; məlumat yoxdursa uydurma qiymət və ya yürüş göstərilmir.
- Əsas siyahı, VIP hissəsi, seçilmişlər, satıcı kabineti, detallar və müqayisə eyni normallaşdırılmış məlumatlardan istifadə edir.
- Şəkil kart çərçivəsində qalır, VIP nişanı onu örtmür. Klaviatura ilə seçilmişlərə və müqayisəyə əlavə etmə səhvən detalları açmır.
- Elan sorğusundakı xəta boş siyahı kimi təqdim edilmir. Təkrar yükləmə imkanı və son uğurlu məlumatlar saxlanılır.

## Yaratma, redaktə və arxivləşdirmə

- Boş yürüş saxlanarkən `null` qalır; istifadəçinin daxil etdiyi `0` itmir. Mühərrik təsvirindən rəqəm dəyəri çıxarılır.
- Təchizat seçimləri checkbox dəyərinə görə bərpa edilir. Kataloqdan çıxmış köhnə seçimlər də saxlanılır, istifadəçinin çıxardığı məlum seçim isə yenidən əlavə edilmir.
- Şəkil bölmələri mövcud URL-lərlə uyğunlaşdırılır. Mətn redaktəsi şəkilləri, onların sırasını və təkrar istinadlarını dəyişmir. Yeni şəkil seçilməyən bölmə qorunur; boş əsas şəkil siyahısı köhnə formadan şəkil diriltmir.
- Redaktə və silmə sorğuları elan ID-si və cari satıcı ilə məhdudlaşır. Serverdən məhz həmin bir elanın ID-si gəlmədikdə əməliyyat uğurlu sayılmır. Uğursuz redaktədə istifadəçinin forması saxlanılır.
- Silmə fiziki `DELETE` əvəzinə `veziyyet = 'silindi'` ilə arxivləşdirmədir. Mövcud şəkillər və ödəniş tarixçəsi saxlanılır; arxiv elan kabinetdən və açıq siyahıdan çıxır.
- Yeni elan üçün serverin qaytardığı ID tələb olunur. Paket yaratmaq üçün ayrıca təkrarlanan frontend sorğusu çıxarılıb; redaktədə yeni paket seçilmədikdə cari paket saxlanılır.
- Paket görünüşü təsdiqlənmiş baza vəziyyətindən müəyyən olunur. VIP 15 gün, Premium 5 gün, Standart 3 gündür. Bitmə tarixi varsa ona üstünlük verilir; tarixsiz köhnə paket yalnız etibarlı təsdiq tarixi öz müddəti daxilindədirsə göstərilir.

Uyğun satıcı icazələri, təkrarlanmayan paket sorğusu və müddətlərin bazada qorunması tətbiq olunan miqrasiya və ayrıca SQL dəsti ilə yoxlanıb. Bu nəticələr frontend və canlı yayım yoxlamalarından ayrıdır.

## Səhifələmə və statistika

- Açıq siyahı `ca_browse_listings` RPC-si ilə serverdə filtrlənir və sıralanır; hər səhifədə 24 elan qaytarılır. Ümumi say və səhifə sayı server cavabından gəlir, kodda ümumi nəticələri 500 ilə kəsən hədd yoxdur.
- Testlər 500-cü elandan sonrakı səhifələri, ilk/son səhifə düymələrini, sıfır filtr sərhədlərini və VIP sıralamasını əhatə edir.
- Kabinet elanları sabit sıralama ilə 100-lük hissələrdə, seçilmişlər isə etibarlı unikal ID qrupları ilə oxunur. Sonrakı hissə uğursuz olarsa natamam nəticə əvvəlki tam siyahını əvəz etmir.
- «Bu gün təsdiqlənən» göstəricisi təsdiq tarixindən serverdə hesablanır; keşdə olan elanların yaradılma tarixindən təxmin edilmir. Serverin qaytardığı `0` saxlanılır.
- Köhnə səhifə sorğusunun gecikmiş cavabı və xətası daha yeni nəticəni dəyişmir. Hesabdan çıxış zamanı şəxsi elan keşi təmizlənir və əvvəl başlamış şəxsi sorğunun cavabı nəzərə alınmır.

## Statik fayllar və şəkillərin eyniliyi

İlkin `index.html` **12 474 072 bayt** idi; bölünmüş HTML təxminən **46 KB**-dır. CSS və JavaScript ayrıca keşlənən fayllardan yüklənir. Bu rəqəm yalnız HTML ölçüsüdür; görünən şəkillər daxil olmaqla ümumi şəbəkə ötürməsinin ölçüsü deyil.

- 56 daxili `data:image` istinadı 46 unikal JPEG/PNG faylına çıxarılıb. Dekodlaşdırılmış faylların cəmi 6 886 108 baytdır. Ölçü, keyfiyyət və məzmun dəyişdirilməyib; şəkillər yenidən kodlaşdırılmayıb.
- İlkin data URI-ləri, çıxarılmış fayllar və SHA-256 izləri [assets/manifest.json](assets/manifest.json) sənədində uyğunlaşdırılıb. Avtomatik test faktiki fayl baytlarından ilkin data URI-ni yenidən qurub hər istinadın hash-ini müqayisə edir.
- İstifadəçinin Supabase-ə yüklədiyi şəkillər və onların URL-ləri toxunulmadan saxlanılıb.
- 8 klassik JavaScript bloku ayrıca `defer` faylı kimi əvvəlki ardıcıllıqla yüklənir; brauzerdə birləşdirilməyib. Əsas kod [assets/js/01-main.js](assets/js/01-main.js), 9 stil blokunun ardıcıllığı isə [assets/site.css](assets/site.css) faylındadır.
- Əsas ekran şəkli `eager` və yüksək prioritetlə, uyğun digər şəkillər `lazy` ilə yüklənir.

İlkin 56 data URI-nin yeni sətirlə birləşdirilmiş siyahısının SHA-256 izi:

`731611a07c211e10ff4fef10b080b5c9ea5975462cca0717059cb9c53d641295`

## Avtomatik yoxlamalar

Repozitoriyanın kökündə:

```sh
node --test --test-isolation=none --test-reporter=spec tests/*.test.cjs
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*_browser.py' -v
for script in assets/js/*.js; do node --check "$script" || exit; done
git diff --check
```

Son kod üzərində **55 Node testi və 19 Chromium testi keçib**, uğursuz və ötürülmüş yoxlama yoxdur. 8 JavaScript faylının sintaksisi və `git diff --check` də uğurludur. Node dəsti bu mühitdə ayrı proseslərin nəticələri gizlətməməsi üçün `--test-isolation=none` ilə icra edilib.

| Dəst | Əhatə |
| --- | --- |
| `tests/listing-data.test.cjs` | Köhnə/yeni məlumat formatları, boş/sıfır rəqəmlər, kart məlumatları, VIP müddətləri və sıralama |
| `tests/listing-management.test.cjs` | Payload, təchizat, şəkil bölmələri və sırası, təsirlənmiş sətir təsdiqi, arxivləşdirmə, səhifələmə, statistika, şəxsi keş və gecikən sorğular |
| `tests/assets.test.cjs` | 56 şəkil istinadının bayt eyniliyi, 46 fayl, kiçik HTML və 8 klassik skriptin icra ardıcıllığı |
| `tests/test_cards_browser.py` | 1440/768/375/320 px görünüş, mətn/şəkil həndəsəsi, filtrlər, sıralama, seçilmişlər, müqayisə, kabinet, klaviatura, xəta/təkrar yükləmə |
| `tests/test_listing_management_browser.py` | Redaktə, təchizat və 9 şəkil bölməsi, boş yürüş, uğursuz yazma, arxiv, 501-ci elana keçid, server statistikası və yerli fayl yolunun təhlükəsiz həlli |
| `tests/listing-management-db.sql` | Uyğun baza sxemində satıcı/admin icazələri, paket axını və müddətləri, arxiv, 600 elanlıq səhifələmə, açıq sütunlar və mövcud qeydlərin qorunması |

Brauzer testləri API cavablarını sınaq məlumatları ilə əvəz edir və real bazaya yazmır. Python üçün `playwright` və Chromium tələb olunur; lazım gəlsə `CHROMIUM_PATH` brauzerin yolunu göstərir. SQL dəsti ayrıca uyğun sxemdə icra olunur və `ROLLBACK` ilə bitir; nəticəsi frontend testlərindən ayrıdır.

Yekun brauzer dəstinə arxivləşdirmədən sonra gecikən şəxsi sorğu, A hesabından B hesabına keçiddə forma/şəkil təmizlənməsi, davam edən köhnə yaddaşlama və yeni qaralamanın qorunması yoxlamaları da daxildir. Testlərdən sonra tətbiq kodu dəyişdirilməyib.

## Tətbiq olunan baza miqrasiyası və real API

Supabase layihəsində `20261107060719_fix_listing_management_and_paginated_browse` miqrasiyası uğurla tətbiq edilib. Tətbiq olunan SQL-in istinadı [database/applied-listing-management.sql](database/applied-listing-management.sql) faylındadır; bu fayl Supabase CLI-nin avtomatik yaratdığı versiyalı miqrasiya kimi təqdim edilmir. Göndərilmiş SQL məzmununun SHA-256 izi:

`f6cbb3443ebb9b0d1e9e62e9ed733add634994675f4daa8d2943a4cb6c15186f`

- `tests/listing-management-db.sql` dəstində **59 yoxlama keçib**. Sınaq məlumatları tranzaksiya sonunda `ROLLBACK` edilib. 600 unikal elanın 25 səhifədə tam əldə edilməsi ayrıca təsdiqlənib.
- Tətbiqdən əvvəl və sonra mövcud **7 elanın bütün qeyd, şəkil və paket hash-ləri**, həmçinin **2 paket sorğusunun hash-ləri** eynidir. Mövcud elanların və ödəniş sorğularının məlumatları dəyişməyib.
- Real anonim sorğu **2 aktiv elan**, **1 VIP elan**, hər elan üçün **29 açıq sahə** və `today_approved = 0` qaytarıb. **5 gözləyən elan** açıq nəticəyə düşməyib.
- Daxili admin qeydinin oxunması həm `anon`, həm də adi `authenticated` rolu üçün rədd edilib. Satıcının `INSERT` və `UPDATE` ilə özünə paket vəziyyəti təyin etməsi də rədd edilib.
- `ca_browse_listings` funksiyası `SECURITY INVOKER` kimi yoxlanıb; sorğu çağıran rolun icazələri ilə işləyir.

## Supabase məsləhətləri və qalan məhdudiyyətlər

Trigger və event-trigger funksiyalarının RPC kimi çağırılmasına `EXECUTE` icazələri geri alındıqdan sonra anonim istifadəçi üçün `SECURITY DEFINER` xəbərdarlıqları aradan qalxıb. Daxil olmuş istifadəçilərə aid **8 `SECURITY DEFINER` xəbərdarlığı** qalır: bunlar daxilində hesab/admin yoxlamaları olan, qəsdən açıq saxlanmış RPC-lərə aiddir. Admin və paket/ödəniş cədvəllərində RLS aktivdir; birbaşa girişə siyasət verilməməsi həmin cədvəlləri bağlı saxlamaq üçündür. İstinadlar: [anonim funksiya icazəsi](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable), [authenticated funksiya icazəsi](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable), [RLS aktiv, siyasət yoxdur](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).

Sızmış parolların yoxlanması **söndürülmüş qalır**. Mövcud Supabase bağlantısı Auth konfiqurasiyasını dəyişmək imkanını vermir; bunu ayrıca layihənin Auth parametrlərindən aktivləşdirmək lazımdır. Buna görə layihə üçün bütün təhlükəsizlik məsləhətlərinin bağlandığı iddia edilmir. İstinad: [parol və sızmış parol qorunması](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

Performans məsləhətlərində yeni yaradılmış **3 istifadə olunmamış indeks üçün INFO** və mövcud admin/açıq oxuma/satıcı siyasətlərinin yaratdığı çoxsaylı icazəverici `SELECT`/`UPDATE` siyasəti qeydləri qalır. İstinadlar: [istifadə olunmamış indeks](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index), [çoxsaylı icazəverici siyasətlər](https://supabase.com/docs/guides/database/database-linter?lint=0006_multiple_permissive_policies).

## GitHub və canlı yayım sübutları

- Tətbiq kodu commit-i: [`d7f28170008d122c8b83b2e4a0bf3e78e31a1612`](https://github.com/dunumcebis-droid/cenub-avto/commit/d7f28170008d122c8b83b2e4a0bf3e78e31a1612). `main`-ə göndərilib.
- [GitHub Pages yayımı 42345930118](https://github.com/dunumcebis-droid/cenub-avto/actions/runs/42345930118) uğurla bitib. Sonrakı sənədləşdirmə commit-i tətbiq fayllarını dəyişmir.
- Canlı HTML, 8 JavaScript, CSS və yüklənmiş yerli şəkil daxil olmaqla 11 statik fayl yoxlanmış işçi fayllarla bayt səviyyəsində eynidir. HTML SHA-256: `4947c1068698d7d118ac42b15685aab996f9a9fd21ef1100dcf87cba3c55dd28`.
- Həqiqi anonim REST API HTTP 200 qaytarır: 2 aktiv elan, 1 VIP, 24/səhifə və bu gün üçün 0 təsdiq. Marka filtri 1 nəticə qaytarıb, sıfırlama 2 nəticəni bərpa edib.
- 1440 və 375 px ekranlarda real kartların məlumatları, şəkillərin açılması və çərçivəsi, üfüqi daşmanın olmaması yoxlanıb. Detallar, telefon linkləri, qalereya və təsvirlər real API məlumatları ilə uyğun gəlir.
- İlkin yüklənmiş şəkil URL-ləri dəyişməyib. Canlı yoxlama yalnız oxuma sorğularına icazə verib; gözlənilməz yazı cəhdi və JavaScript xətası olmayıb. 600 elanlıq bütün səhifələr ayrıca geri qaytarılan DB sınağında, 501-ci elana keçid isə brauzer sınağında yoxlanıb.
- Hesabatlar: [59 DB yoxlaması](tests/reports/db-regression.json), [miqrasiyadan sonrakı qorunma/icazə nəticələri](tests/reports/postmigration.json), [real canlı yoxlama](tests/reports/live-d7f2817.json).

Mövcud elanlardan birinin yüklənmiş şəkli köhnə `permission denied for table profiller` xəta ekranının şəklidir. Bu, cari saytda açılmış canlı xəta pəncərəsi deyil; istifadəçinin şəkillərinə toxunmamaq tələbinə görə dəyişdirilməyib.

## Bank ödənişi üçün asılılıq

Mövcud əl ilə paket sorğusu və admin təsdiqi axını qorunub. İstifadəçinin hələ merchant hesabı yoxdur; VÖEN və ABB-dən internet ekvayrinq/merchant girişi əldə edəcək. Bankın server girişləri, imza və nəticə təsdiqi qaydaları alındıqdan sonra avtomatik kart ödənişi ayrıca inteqrasiya və yoxlama tələb edir. Hazırkı dəyişikliklər kartdan real pul tutulmasının işlədiyi kimi təqdim edilmir.
