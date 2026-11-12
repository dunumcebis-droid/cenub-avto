# Şəkli tam ekranda açma və elan pəncərəsi

İstifadəçinin bildirdiyi iki hal əvvəlcə mobil toxunma yolu ilə təkrarlanıb: elandakı şəkilə toxunmaq böyütmə açmırdı; üzən müqayisə/ehtiyat nüsxə/qaydalar/admin düymələri elanın üstündə qalırdı.

İndi şəklin özünə və «Böyüt» düyməsinə toxunanda tam ekran baxışı açılır. Eyni orijinal URL və su nişanı saxlanılır. +/−, 100%-ə sığdırma, iki dəfə toxunma/siçan klikləməsi, iki barmaqla 1–4× böyütmə, böyüdülmüş şəkli hərəkət etdirmə və adi vəziyyətdə yana sürüşdürmə var. Əvvəlki/növbəti düymələri və say/bölmə göstəricisi görünür. Bağlama elanı açıq saxlayır və baxılan şəkli onun qalereyasında seçir.

Tam ekran ayrıca modal pəncərədir. Escape və brauzerin geri düyməsi yalnız yuxarıdakı şəkil baxışını bağlayır; fokus və səhifə sürüşdürmə vəziyyəti bərpa olunur. Elan pəncərəsi bağlananda baxış da təmizlənir. Səhifə alətləri modal pəncərələr açıq olanda `hidden` və `inert` olur, bağlananda bərpa edilir. Yeni elanı açanda qalereya yuxarıdan başlayır. Qalereyanın boş kənarları saytın tünd fonuna uyğundur.

## Yoxlamalar

- Yeni toxunma ssenariləri: **8/8**, 16,327 saniyə. Gerçək brauzer toxunması və CDP touch hadisələri işlədilir; yalnız JavaScript funksiyasına çağırışla kifayətlənilmir.
- Şəkilə toxunma, həqiqətən dəyişən şəkil ölçüsü, iki barmaq, sürüşdürmə, iki dəfə toxunma və siçanla iki klik, 36 şəkil arasında keçid, seçilmiş şəklin saxlanması, gizli/admin alətləri, fokus/Tab, Escape, geri düyməsi, boş/tək/açılmayan şəkil və telefonun üfüqi vəziyyəti əhatə olunur. İlk yoxlamada toxunmadan sonra yaranan ikinci `dblclick` hadisəsinin yaxınlaşdırmanı geri qaytardığı tapılıb və düzəldilib.
- Əlaqəli sınaqlar: **5/5** su nişanı, **7/7** kart/elan görünüşü, **8/8** müqayisə pəncərəsi. Su nişanı sınağı kabinetin asinxron yenilənməsinin bitməsini gözləyir.
- **60/60** Node yoxlaması; bütün əvvəlki 46 şəkil/56 istinad qorunur. Klassik skript sırası yeni baxış modulunu da yoxlayır. **12** JavaScript faylının sintaksisi və diff formatı keçib.
- 240×320, 240×812, 320×812, 375×812, 430×932, 768×1024, 1440×1000 və 812×375 ölçülərində ayrıca inteqrasiya olunmuş 8 görünüş yoxlaması keçib; düymələr və su nişanı çərçivədədir.

Brauzer sınaqlarının bütün şəbəkəsi sınaq məlumatları ilə əvəz olunur. Storage, elan, admin təsdiqi, ödəniş, parol və ya e-poçt əməliyyatı edilmir. İstinadlar: [yeni toxunma sınaqları](tests/test_photo_viewer_browser.py), [nəticələr](tests/reports/photo-viewer-frontend.json).
