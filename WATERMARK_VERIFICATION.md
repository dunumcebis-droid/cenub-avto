# Elan şəkillərində su nişanı

Yeni yüklənən və brauzerin hazırlaya bildiyi şəkillər mövcud 1440 px maksimum ölçü və JPEG sıxılmasından sonra mərkəzdə yarımşəffaf «CƏNUB AVTO» yazısı alır. Yazı saxlanan JPEG-in piksellərinə daxil edilir. Yalnız uğurla hazırlanmış faylların adında `-ca-wm1.jpg` işarəsi olur; brauzerin aça bilmədiyi köhnə fallback axını orijinal faylı yanlış işarələmədən saxlayır. Göndərişin Content-Type sahəsi faktiki Blob növünə uyğundur.

Əvvəlki elanların bütün URL-ləri, faylları, şəkil sırası və qrupları saxlanılır. Onların üzərində yazı yalnız ekranda göstərilir; orijinal yüklənmiş fayllar kütləvi dəyişdirilmir. Kartlar, seçilmişlər, böyük qalereya, kiçik qalereya şəkilləri və şəxsi kabinet əhatə olunur. Əvvəldən yeni yazısı olan fayllar yalnız öz Storage ünvanı, bucket və dəqiq fayl adı ilə tanınır və ikinci yazı almır. Saytın əsas şəkli, kataloq nümunələri və loqosu dəyişmir.

Yazı şəkil açılandan sonra görünür; boş və ya açılmayan şəkillərdə gizlidir. Siçan və toxunma hadisələrini tutmur. Ölçüsü göstərilən şəklin eninə və hündürlüyünə uyğunlaşır; portret və çox geniş panorama şəkillərində də foto sərhədlərində qalır. Mobil qalereyanın əvvəlki 48vh hündürlüyü saxlanılır. Elan formasında su nişanı barədə qısa qeyd var.

## Yoxlama

- 60/60 Node yoxlaması; ilkin 46 şəklin və 56 istinadın eyniliyi daxil olmaqla.
- 79/79 mövcud brauzer yoxlaması: 142,176 saniyə.
- 5/5 yeni brauzer yoxlaması: 22,961 saniyə. Hazırlanmış və göndərilmiş real JPEG baytlarının mərkəzində yazı pikselləri, dəyişməyən kənar rəngləri, ölçü sərhədi, saxta Storage göndərişi və decoder fallback yoxlanır.
- Yeni görünüş yoxlamaları 320/375/1440 px ölçülərində portret, landşaft və 4000×100 panorama şəkillərini, işləyən qalereya/seçilmişlər düymələrini, saxlanan orijinal URL-ləri, ikiqat yazının qarşısının alınmasını, HTML qaçışlarını və açılmayan şəkilləri əhatə edir.
- 11 JavaScript faylının sintaksisi və diff formatı keçib. Baza sxemi, icazələr, mövcud elanlar, VIP sorğuları və hesablar dəyişdirilmir.

Brauzer testlərində bütün API cavabları sınaq məlumatları ilə əvəz olunur. Heç bir həqiqi Storage yükləməsi, elan dəyişikliyi, e-poçt və ya parol əməliyyatı edilmir. İstinad: [yeni brauzer testləri](tests/test_watermark_browser.py), [frontend nəticələri](tests/reports/watermark-frontend.json).
