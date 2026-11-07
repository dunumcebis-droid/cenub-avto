# Admin səhifələməsi və parol bərpası

## Tətbiq edilən dəyişikliklər

- Admin elanları və paket sorğuları serverdə axtarılır, statusa görə süzülür və 24-lük səhifələrlə açılır. Ümumi say serverdən gəlir; 1000 qeyddən kənardakı elan və sorğular da əlçatandır. Səhifə boşaldıqda server son mövcud səhifəyə qayıdır.
- Admin girişi serverdə üzvlük yoxlamasından keçir. Brauzerdəki sabit admin ID-si çıxarılıb. Gecikən cavablar yeni filtrin və ya başqa hesabın məlumatlarını əvəz etmir; çıxışda admin məlumatları təmizlənir.
- Elan təsdiqi, rədd və paket təsdiqindən sonra əsas elanlar, VIP hissəsi, bu gün sayğacı və şəxsi siyahılar yenilənir. Son səhifə boşaldıqda köhnə kartların qalmasının qarşısını almaq üçün açıq siyahı birinci səhifədən yenilənir.
- Mutasiya serverdə uğurlu olub, sonrakı siyahı yenilənməsi alınmasa, interfeys bunu saxlanılmış dəyişiklik və yeniləmə xətası kimi ayrıca bildirir. Ödəniş əməliyyatını səhvən təkrar etməyə sövq etmir.
- Giriş ekranında «Şifrəni unutdum», bərpa linki istəmə, yoxlanmış hesabın e-poçtunu göstərmə və iki dəfə yeni parol daxil etmə axını əlavə edilib. Əvvəlki giriş və qeydiyyat saxlanılıb.
- Linkin giriş məlumatları səhifənin digər resurslarından əvvəl URL-dən silinir. Auth serverində hesab yoxlanır; bərpa tokeni yalnız yaddaşda qalır, mövcud sessiyanı əvəz etmir və localStorage-a yazılmır. Link köhnədirsə və ya doğrulanmırsa yeni link istəmə imkanı verilir.
- Bərpa və normal giriş cavabları forma və hesab dəyişdikdən sonra yeni istifadəçinin sessiyasını və qaralamasını dəyişə bilmir. Uğurlu parol yeniləməsindən sonra adi giriş ekranı göstərilir.

İlkin 8 skriptin ardıcıllığı qorunub. Onlardan əvvəl `00-auth-callback.js` sinxron olaraq URL-i təmizləyir; sonra `09-auth.js` yüklənir. Cəmi 10 yerli JavaScript faylı var. Şəkil faylları, yüklənmiş şəkil URL-ləri və VIP müddətləri dəyişdirilməyib.

## Baza və icazələr

`20261107113829_page_admin_listings_and_payments` miqrasiyası tətbiq edilib. SQL istinadı: [database/admin-pagination.sql](database/admin-pagination.sql). Bu, tətbiq edilmiş uzaq miqrasiyanın SQL istinadıdır, yeni CLI tərəfindən yaradılmış tarixli fayl deyil.

Yeni səhifələmə funksiyaları və yenilənmiş `ca_admin_list` `SECURITY INVOKER` rejimindədir. Elanlar mövcud RLS ilə oxunur. Paket səhifələməsi artıq mövcud olan admin yoxlamalı paket sorğusu funksiyasından istifadə edir; yeni imtiyazlı funksiya və ya cədvəl oxuma icazəsi əlavə edilmir.

- **15 SQL yoxlaması keçib:** 1 205 elan və 1 205 paket sorğusu 51 səhifədə təkrarsız əldə edilib; köhnə gözləyən elan/sorğu və bütün qeydlərdə axtarış ayrıca yoxlanıb. Sınaq tranzaksiyası `ROLLBACK` ilə bitib.
- Mövcud **7 elan və 2 paket sorğusunun** bütün sətir hash-ləri tətbiqdən əvvəl və sonra eynidir. Foto və paket dəyərləri də həmin yoxlamaya daxildir. Sınaq elanı qalmayıb.
- Anonim və adi istifadəçinin admin səhifələrinə girişi rədd edilib. Daxili qeydlər, ödəniş cədvəlinə birbaşa oxuma və qorunan paket sahələrinə yazma qapalıdır.

Hesabatlar: [DB regressiyası](tests/reports/admin-db-regression.json), [tətbiqdən sonrakı icazələr və məlumatların qorunması](tests/reports/admin-postmigration.json).

## Avtomatik sınaqlar

```sh
node --test --test-isolation=none --test-reporter=spec tests/*.test.cjs
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*_browser.py' -v
for script in assets/js/*.js; do node --check "$script" || exit; done
git diff --check
```

**58 Node və 35 Chromium sınağı keçib**, uğursuz və ötürülmüş yoxlama yoxdur. Brauzer dəstində 16 yeni admin/parol sınağı və əvvəlki 19 kart/redaktə sınağı var. Bütün 10 JavaScript faylı üçün `node --check` və `git diff --check` də uğurludur.

Brauzer sınaqları hər şəbəkə sorğusunu əvəz edir. **Həqiqi e-poçt göndərilmir, real parol dəyişdirilmir və real admin mutasiyası edilmir.** Gerçək DB icazələri SQL tranzaksiyası ilə ayrıca yoxlanır. Yeni sınaqlarda vaxtı keçmiş link, URL-in təmizlənməsi, token-hash doğrulaması, parol uyğunluğu, normal giriş/qeydiyyat, hesab dəyişərkən gecikən parol cavabı, 1000-dən sonrakı səhifələr, həqiqi forma hadisələri, gecikmiş admin cavabları və qismən yeniləmə xətaları əhatə olunub.

## Xarici ayarlar və məhdudiyyətlər

- Real Auth `/settings` oxuma sorğusu HTTP 200 qaytarıb: e-poçt girişi və qeydiyyat aktivdir, e-poçt təsdiqi tələb olunur. Bu endpoint SMTP və yönləndirmə siyahısını açıqlamır.
- Bərpa sorğusu `https://dunumcebis-droid.github.io/cenub-avto/` ünvanına yönləndirir. İstifadəçi real məktubdakı linkin həmin saytda «Yeni parol yarat» ekranını açdığını təsdiqləyib. Dəqiq [URL configuration](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/url-configuration) məzmunu mövcud MCP vasitəsilə oxunmur; yoxlama həqiqi linkin davranışına əsaslanır.
- Bütün istifadəçilərə real məktub göndərilməsi üçün [SMTP qurulumu](https://supabase.com/docs/guides/auth/auth-smtp) tələb olunur; Supabase-in standart poçt xidməti yalnız layihə komandasındakı ünvanları dəstəkləyir. İstifadəçinin ayrıca icazəsi ilə verilən öz ünvanına bir bərpa sorğusu göndərilib: Auth HTTP 200 qaytarıb, göndəriş serverdə qeydə alınıb və istifadəçi məktubun gəldiyini təsdiqləyib. Bu yoxlama bir icazəli ünvana aiddir; SMTP ayarlarının məzmunu və digər alıcılara çatdırılma yoxlanmayıb. Parol istənilməyib və dəyişdirilməyib.
- Təşkilatın planı **Free** olaraq yoxlanıb. [Sızmış parol qorunması](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection) **Pro və yuxarı** planlarda mövcuddur. Ödənişli plana keçid və bu ayar aktivləşdirilməyib. Adi parol uzunluğu yoxlaması həmin server qorunmasının əvəzi kimi təqdim edilmir.
- Real kart ödənişi VÖEN, ABB merchant hesabı və bankın inteqrasiya girişlərini gözləyir. Mövcud sınaq/əl ilə təsdiq axını saxlanılıb.

Əvvəlki kart və şəkil düzəlişlərinin sübutları [VERIFICATION.md](VERIFICATION.md) sənədindədir.

## Yekun yayım

- Tətbiq commit-i: [`7f13e4727388aadf0c18170117fe3b36382a1945`](https://github.com/dunumcebis-droid/cenub-avto/commit/7f13e4727388aadf0c18170117fe3b36382a1945).
- [GitHub Pages yayımı 42369959393](https://github.com/dunumcebis-droid/cenub-avto/actions/runs/42369959393) uğurludur. Sonrakı hesabat commit-i tətbiq fayllarını dəyişmir.
- Canlı saytda 2 real aktiv elan və 1 VIP elan, marka filtri/sıfırlama, detallar, telefon linkləri, qalereya və təsvirlər 1440/375 px ekranlarda yoxlanıb. JavaScript xətası və gözlənilməz yazı cəhdi yoxdur.
- Canlı «Şifrəni unutdum» ekranı açılıb. Həqiqi Auth serverinə yalnız etibarsız saxta tokenlə oxuma sorğusu verilib: bərpa rədd edilib, yeni link istəmə ekranı göstərilib, token URL və yaddaşdan təmizlənib, normal sessiya yaradılmayıb.
- Brauzerdə yüklənən 13 statik fayl, ayrıca tam müqayisədə isə bütün **59 statik fayl və onların daxilindəki 46 şəkil** yoxlanmış məzmunla bayt səviyyəsində eynidir. Canlı HTML SHA-256: `0b6165d01dc9b4122d87c582f4de23c33db0ee40a878b98688d368465b9adac5`.
- Hesabatlar: [58 Node / 35 brauzer nəticəsi](tests/reports/admin-auth-frontend.json), [real canlı yoxlama](tests/reports/live-admin-auth-7f13e47.json), [bütün statik fayllar](tests/reports/admin-auth-static-live.json).
- Real bərpa məktubu üçün ayrıca icazə alınıb və yalnız bir sorğu göndərilib. HTTP 200, Auth-un göndəriş qeydi və istifadəçinin məktubun gəlib yeni parol ekranını açması təsdiqi var. [Real e-poçt sınağı](tests/reports/recovery-email-live.json). Heç bir real parol dəyişdirilməyib.
