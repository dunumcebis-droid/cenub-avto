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

Canlı yayım nəticəsi ayrıca qeyd ediləcək. Yeni loqo daxil olmaqla tətbiqin 64 statik faylı var; əvvəlki `assets/images` qovluğundakı 46 şəkil saxlanılır.
