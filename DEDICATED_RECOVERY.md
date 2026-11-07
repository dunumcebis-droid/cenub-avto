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

## Canlı yayım

[d622d3a](https://github.com/dunumcebis-droid/cenub-avto/commit/d622d3a377ac990a6f34568b675cdb1a6d13aef7) tətbiq commit-i [Pages yayımı 42418018077](https://github.com/dunumcebis-droid/cenub-avto/actions/runs/42418018077) ilə uğurla yayımlanıb. Yeni səhifə, etibarsız sintetik token üçün təkrar forma, 320/375 px və üfüqi görünüş, qalan sayt səhifələri canlıda yoxlanıb. JavaScript xətası və gözlənilməz yazı cəhdi yoxdur.

Bütün 63 statik fayl və 46 şəkil yoxlanmış tətbiq commit-i ilə bayt səviyyəsində eynidir. Canlı yoxlama real hesab tokeni və ya parolu istifadə etmir; real məktub sınağının nəticəsi bu hesabatın iddiası deyil. Məktubdakı etibarlı keçid istifadəçi tərəfindən ayrıca yoxlanmalıdır. Səhifəni tokensiz açmaq yalnız yeni link istəmək formasını göstərir.

Hesabatlar: [frontend dəstləri](tests/reports/dedicated-recovery-frontend.json), [görünüşlər](tests/reports/dedicated-recovery-layouts.json), [canlı sintetik keçidlər](tests/reports/dedicated-recovery-live.json), [63 statik fayl](tests/reports/dedicated-recovery-static-live.json). Sonrakı hesabat commit-i tətbiq fayllarını dəyişmir.

Ümumi SMTP/yönləndirmə ayarları [EMAIL_SENDER_SETUP.md](EMAIL_SENDER_SETUP.md) sənədindədir.
