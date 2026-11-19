# Paket qiymətləri — 19 noyabr 2026

## Cari seçimlər

| Paket | Qiymət | Müddət |
| --- | --- | --- |
| Pulsuz | 0 AZN | Əlavə önə çıxarma yoxdur |
| Təcili | 1 AZN | Elan satılanadək |
| Üstün / Premium | 5 AZN | 10 gün |
| Önə çıxarılan / VIP | 10 AZN | 15 gün |

Sərfəli / Standart yeni yerləşdirmə seçimindən və əsas paket filtrindən çıxarılıb. Yeni Standart müraciəti serverdə də qəbul edilmir. Əvvəlki paket/ödəniş tarixçəsi və yazılmış bitmə vaxtları qorunur; əvvəlki gözləyən Standart sorğusunu təkrarlamaq və adminin həmin sorğunu tamamlamaq imkanı qalır.

Paket təsdiqi və elanın yayımı ayrı əməliyyatlardır. İlk yayım Premium üçün 10, VIP üçün 15 günlük müddəti başlayır. Redaktədən sonra yeni sifariş seçilmədikdə cari tarixlər saxlanılır. Tarixsiz köhnə təsdiq üçün Premium-un ehtiyat hesablaması brauzer, açıq axtarış və bildiriş uyğunlaşdırmasında eyni 10 gündür. Təcili gün limiti almır.

Yeni etiketlər dəqiq paket adına çevrilir; VIP-in 10 AZN qiyməti Təcili-nin 1 AZN qiyməti ilə qarışmır. Köhnə 15 AZN və 3 AZN etiketləri yeni sifariş yaratmır; belə köhnə səhifədə istifadəçiyə səhifəni yeniləmək bildirilir. Mövcud köhnə sorğu tarixçəsi admin üçün oxunur.

Avtomatik kart/bank ödənişi aktivləşdirilməyib. Məbləğlər forma və qaydalarda göstərilir, paket müraciəti əvvəlki manual admin axınından keçir. Ödəniş provayderi qoşulanda serverdə istifadə ediləcək qiymətlər [PAYMENT_SETUP.md](PAYMENT_SETUP.md) sənədində göstərilib.

## Yoxlamalar

- 111 Node yoxlaması keçib. Premium-un 10 günlük ehtiyat müddəti və əvvəlki ayrıca 5 günlük bitmə tarixinin üstünlüyü yoxlanıb.
- 36 brauzer sınağı keçib: 7 yeni qiymət/seçim, 11 paket bildirişi və 18 Təcili ssenarisi. Yeni VIP, Premium və Təcili seçimi, cari dörd seçim, Sərfəli-nin çıxarılması, əvvəlki elanın şəkil və tarixlərinin redaktədə qorunması əhatə olunub.
- Real bazada 99 yeni paket yoxlaması, 125 Təcili və 126 Nağd/Kredit/Barter regresiyası geri qaytarılan tranzaksiyalarda keçib. Ödəniş/yayım ayrılığı, 15/10 günlük yeni aktivləşdirmə, köhnə 5 günlük yazılmış tarixin saxlanması, köhnə Standart sorğusunun tamamlanması, tarixsiz ehtiyat hesablaması və bildiriş uyğunluğu yoxlanıb. Əvvəlki elan/şəkil və paket qeydlərinin dəyişmədiyi, şəkil yoxlama ayarlarının bərpa olunduğu təsdiqlənib.
- Brauzer sınaqlarında bütün HTTP/API cavabları imitasiya edilir; real elan, şəkil yükləməsi, məktub və ya ödəniş yaradılmır.

SQL istinadı [database/package-pricing.sql](database/package-pricing.sql), geri qaytarılan baza sınağı [tests/package-pricing-db.sql](tests/package-pricing-db.sql) faylındadır.
