# Bərpa keçidi və ayrıca məlumat səhifələri

Ana səhifədə elanlardan sonra ayrıca məlumat menyusu var. «Haqqımızda» `about.html`, «Dəstək xidməti» isə `support.html` səhifəsini açır. Telefon və e-poçt keçidləri dəstək səhifəsindədir; hər iki səhifədən elanlara qayıtmaq olur. Footer və alət paneli bir-birini örtmür.

Bərpa məlumatı yalnız ilk açılışda oxunurdu. İndi artıq açıq olan səhifəyə `hashchange` və `popstate` ilə gələn bərpa keçidləri də tutulur; məxfi URL parametrləri interfeys açılmamış təmizlənir. İşlənmiş, vaxtı bitmiş və təsdiq məlumatı çatışmayan keçid aydın bərpa izahını göstərir. Yeni parol forması yalnız Auth tərəfindən yoxlanmış hesab üçün aktivləşir. Bərpa tokeni yaddaşda qalır, cari giriş sessiyasını əvəz etmir. Auth pəncərəsi admin/alət panellərindən yuxarı göstərilir. Yeni məktubların bərpa ünvanı `?auth=recovery` işarəsini istifadə edir; `Site URL` ümumi sayt ünvanı olaraq qalır.

## Yoxlamalar

| Dəst | Nəticə |
| --- | --- |
| Node: əvvəlki yoxlamalar və callback reqressiyaları | 60/60 |
| Chromium: bütün axınlar və yeni bərpa reqressiyaları | 69/69; 133,990 saniyə |
| Menyu, ayrıca səhifələr və responsive görünüşlər | 35/35 |
| JavaScript sintaksisi və diff formatı | 10 fayl; təmiz |

İki brauzer ssenarisi düzəlişdən əvvəl uğursuz olub: açıq səhifəyə gələn bərpa fragmenti və yalnız bərpa işarəsi olan keçid. Düzəlişdən sonra keçib. İstifadə edilmiş keçid xətası, query tokeninin yoxlanması, cari hesabın qorunması, mobil görünüş və əvvəlki elan/VIP axınları da yoxlanıb. Brauzer API-ləri saxtadır; bu dəst real məktub, parol dəyişikliyi və admin təsdiqi etmir.

Son bərpa ünvanı işarəsi dəyişəndən sonra 60 Node və 20 admin/bərpa brauzer sınağı yenidən keçib (27,787 saniyə).

Görünüşlər 320, 360, 375, 390, 430, 768 və 1440 px enlərdə yoxlanıb. Dəstək əlaqələri, menyu, geri qayıtma və footer görünür; səhifələr üfüqi daşmır. Şəkillərin ilkin bayt eyniliyi qorunur.

## Canlı yoxlama

Tətbiq commit-i [608160d](https://github.com/dunumcebis-droid/cenub-avto/commit/608160d9464a4898eb249237c539058ef4d8a691), [Pages yayımı 42403226777](https://github.com/dunumcebis-droid/cenub-avto/actions/runs/42403226777) uğurludur. Ayrıca səhifələr, telefon/e-poçt keçidləri, elanlara qayıdış və menyunun ayrılığı həqiqi saytda yoxlanıb. Sintetik bərpa keçidləri ilə açıq səhifədə istifadə edilmiş link xətası, yalnız bərpa işarəsi, etibarsız tokenin rəddi və pəncərənin alətlərdən yuxarı görünməsi keçib. Bu canlı UI yoxlaması məktub göndərmir və parol dəyişmir.

Bütün 61 statik fayl, o cümlədən 46 dəyişdirilməmiş şəkil, tətbiq commit-i ilə bayt səviyyəsində eynidir. Real açıq elanların kartları, detallar, qalereya, filtrlər, BMW seçimi və müqayisə də yoxlanıb. JavaScript xətası və gözlənilməz yazı cəhdi yoxdur.

Hosted Auth-un `Site URL` və `Redirect URLs` ayarları da istifadə olunan sayt ünvanına uyğun olmalıdır. Ümumi ünvanlar [EMAIL_SENDER_SETUP.md](EMAIL_SENDER_SETUP.md) sənədindədir. İşlənmiş bərpa linki yenidən istifadə edilmir; real yeni məktub sınağı ayrıca icazə ilə aparılır. Şəxsi Auth qeydləri və bərpa linkləri açıq repozitoriyaya daxil edilmir.
