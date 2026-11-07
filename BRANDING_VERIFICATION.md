# Yeni loqo və şüar

İstifadəçinin loqosu `assets/branding/cenub-avto-logo.jpg` faylına dəyişdirilmədən köçürülüb. Fayl 42 437 baytdır, ölçüsü 1232×1280, SHA-256 izi `34dbfc142c2317412827da3d377f3e1eee732e9d9ca37fb3b7408e0942bef94f`-dir. Fayl yenidən kodlaşdırılmayıb. CSS görünüşü yalnız boş qara kənarları daraldır; avtomobil konturu, ad və loqodakı şüar tam görünür.

Ana səhifə, dəstək, haqqımızda və parol bərpası səhifələrinin başlıqları bu loqonu göstərir. Köhnə şüar işlək HTML-dən çıxarılıb; yeni şüar **«Xəyal etdiyin avtomobili kəşf et»** alt hissələrdə, məlumat səhifəsində və ana səhifənin metadata-sında istifadə olunur. Loqo ana səhifəyə keçiddir və mətn alternativi var.

Yeni başlığın hündürlüyünə görə keçid nöqtələrinin yuxarı boşluğu ölçülür; «Elanlar» başlığı sabit başlığın arxasında qalmır. Mövcud alət panelinin alt boşluğu saxlanılır. Avtomobil şəkilləri, VIP və hesab/bərpa məntiqi dəyişdirilməyib.

## Yoxlamalar

- Node: **60/60**; ilkin 46 şəklin və 56 istinadın eyniliyi də yoxlanır.
- Bütün brauzer ssenariləri: **79/79**, 112,397 saniyə; API cavabları tam saxtadır.
- Loqo və şüar görünüşləri: **48/48**; 240, 320, 360, 375, 390, 430, 768 və 1440 px. Ana səhifə qonaq/admin/çıxış vəziyyətlərində, üç əlavə səhifə də ayrıca yoxlanıb.
- Əlavə keçid yoxlamalarında «Elanlar» başlığı görünür. Loqonun bütün məzmunu çərçivədədir, düymələr örtülmür və üfüqi daşma yoxdur.
- JavaScript sintaksisi və diff formatı keçib. Bu sınaqlar real məktub, parol, elan və ya admin təsdiqi əməliyyatı etmir.

## Canlı yayım

[5e1ea45](https://github.com/dunumcebis-droid/cenub-avto/commit/5e1ea45f1421056e5114ccb26325b723fe6fd336) tətbiq commit-i [Pages yayımı 42419955451](https://github.com/dunumcebis-droid/cenub-avto/actions/runs/42419955451) ilə uğurla yayımlanıb. Ana səhifə, dəstək, haqqımızda və parol bərpasında 14 canlı ölçü/səhifə yoxlaması keçib: loqo yüklənir, bütün məzmunu görünür, düymələr örtülmür, yeni şüar görünür və köhnəsi yoxdur. 375 px ekran görüntülərinə ayrıca baxılıb.

Bütün 64 statik fayl yoxlanmış tətbiq commit-i ilə bayt səviyyəsində eynidir. Yeni loqo istifadəçinin faylı ilə eynidir; əvvəlki `assets/images` qovluğundakı 46 şəkil saxlanılır. Real açıq elanların məlumatları, qalereya, filtr/sıfırlama, BMW seçimi və müqayisə də yoxlanıb. Əsas avtomobil şəkli yüklənir. Sintetik etibarsız bərpa keçidində təhlükəsiz təkrar forma işləyir. JavaScript xətası və gözlənilməz yazı cəhdi yoxdur.

Hesabatlar: [frontend](tests/reports/brand-logo-frontend.json), [48 görünüş](tests/reports/brand-logo-layouts.json), [canlı sayt](tests/reports/brand-logo-live.json), [64 statik fayl](tests/reports/brand-logo-static-live.json). Canlı Auth yoxlaması yalnız sintetik məlumatdan istifadə edir; real məktub və parol əməliyyatı yoxdur. Sonrakı hesabat commit-i tətbiq fayllarını dəyişmir.
