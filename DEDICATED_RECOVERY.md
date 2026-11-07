# Ayrıca parol bərpası səhifəsi

Yeni bərpa məktubları `reset-password.html` səhifəsini açır. Səhifə Auth hesabı yoxlandıqdan sonra «Yeni parol yarat» başlığını, iki parol xanasını və yadda saxlama düyməsini göstərir. Köhnə və ya təsdiq məlumatı olmayan keçid üçün yeni link istəmək forması var. Ana səhifədə əvvəlki bərpa keçidlərinin dəstəyi saxlanılır.

Yeni səhifə ayrıca HTML və kiçik JavaScript faylından ibarətdir. Başlıq skripti URL-dəki məxfi məlumatı resurslardan əvvəl təmizləyir. Token yalnız yaddaşda saxlanılır; cari giriş sessiyası və brauzer saxlancı dəyişdirilmir. Parol yalnız istifadəçi göndərdikdə, yoxlanmış hesabın tokeni ilə yenilənir. Gecikmiş cavab başqa bərpa hesabını və ya yeni səhifə vəziyyətini əvəz etmir. Səhifədən çıxışda parol/token təmizlənir.

## Yoxlamalar

| Dəst | Nəticə |
| --- | --- |
| Mövcud Node yoxlamaları, şəkillərin eyniliyi daxil | 60/60 |
| Bütün mövcud brauzer axınları və 10 yeni bərpa ssenarisi | 79/79; 120,953 saniyə |
| Gecikmiş saxta sorğular üçün gözləmələrdən sonra ayrıca bərpa dəsti | 10/10; 7,777 saniyə |
| Yeni səhifənin 3 vəziyyətdə görünüş yoxlamaları | 15/15 |

Brauzer dəsti tam saxta API cavabları ilə işləyir: etibarlı fragment və token hash, query təmizlənməsi, səhv/vaxtı bitmiş keçid, açıq e-poçt sorğusu, parol uyğunluğu, tək göndəriş, düzgün hesab ID-si, gecikmiş cavablar və cari girişin qorunması yoxlanıb. 320/375 px və üfüqi ekranlarda forma əlçatandır. Görünüş dəsti 320, 375, 430, üfüqi 768 və 1440 px ölçülərdə saxta vəziyyətlərdən istifadə edir. Bu dəstlər real məktub və parol əməliyyatı etmir.

Yeni səhifə və skriptlə tətbiqin statik fayl sayı 63 olur; 46 ilkin şəkil dəyişdirilmir. Şəxsi Auth/göndəriş qeydləri, tokenlər və bərpa linkləri açıq repozitoriyaya daxil edilmir. Real yeni məktub sınağı ayrıca icazə ilə aparılır.

Canlı yayım nəticəsi əlavə ediləcək. Ümumi SMTP/yönləndirmə ayarları [EMAIL_SENDER_SETUP.md](EMAIL_SENDER_SETUP.md) sənədindədir.
