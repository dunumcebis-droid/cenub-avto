# Təcili paket və iki sütun — 19 noyabr 2026

## Davranış

- Forma: **Təcili — 1 AZN / satılanadək**. Sorğu əvvəlcə gözləyir; admin paket ödənişini yoxlayıb təsdiqləyir, elanı isə ayrıca yayımlayır. Avtomatik bank/kart ödənişi aktivləşdirilməyib.
- Kanonik paket `Tecili`-dir. Paket təsdiqi gözləyən elanı avtomatik yayımlamır; ilk yayım başlanğıcı yazır və bitmə vaxtını boş saxlayır. Redaktədən sonra təkrar yayım başlanğıcı saxlayır, ikinci ödəniş sorğusu yaratmır. Müddətli VIP/Premium/Standart paketləri öz qaydaları ilə işləyir; Təcili gündəlik bitmə əməliyyatına düşmür.
- Yaşıl **TƏCİLİ** nişanı yalnız təsdiqlənmiş aktiv və satılmamış elan üçün görünür. Forma daxilində `pack` və ya paket adı yazmaq bu hüququ vermir. Satılmış, gözləyən, rədd edilmiş və arxivləşdirilmiş elan açıq Təcili nəticələrinə daxil olmur.
- Əsas ekranda ayrıca Təcili seçimi və geniş filtrlərdə seçim var. Nağd/Kredit/Barter, şəhər, qiymət və digər şərtlər birlikdə süzülür. Filtr/səhifə dəyişəndə birinci səhifəyə qayıdır. Təcili seçimi VIP paket filtrini sıfırlayır; sonradan başqa paket seçimi Təcili seçimini təmizləyir.
- Saxlanılan axtarışın `urgent: true` şərti və sayt bildirişinin uyğunlaşdırması açıq siyahı ilə eynidir. `false`/`null` məhdudiyyət yaratmır; başqa tipli qiymətlər serverdə rədd edilir. Şəxsi axtarışlar və daxili admin qeydləri açıq siyahıya əlavə edilməyib.
- Əsas elanlar, VIP və seçilmişlər 320–1440 px enlərdə iki sütundur. Şəkil, nişan, uzun ad, qiymət və müqayisə düymələri mobil ölçüyə uyğunlaşdırılıb.

## Yoxlamalar

- 109 Node yoxlaması keçib; Təcili üçün müddətsizlik, keçmiş tarix, satılmış/gözləyən hal və saxta forma paketinin təsirsizliyi daxildir.
- 18 yeni brauzer sınağı keçib: yeni/redaktə müraciəti, adminin dəqiq sorğuya keçidi, ayrıca ödəniş və yayım təsdiqi, yaşıl nişan, Təcili və satış şərtləri, saxlanılan axtarış, səhifələmə, iki sütun, seçilmişlər, müqayisə, ətraflı baxış və uğursuz göndəriş.
- 43 mövcud kart/paket/satış şərtləri/təkrar göndəriş brauzer sınağı keçib.
- Real bazada 125 Təcili yoxlaması geri qaytarılan tranzaksiyada keçib; bütün əvvəlki elan/şəkil və paket qeydlərinin dəyişmədiyi, şəkil yoxlama ayarlarının bərpa olunduğu təsdiqlənib. Əvvəlki Nağd/Kredit/Barter üzrə 126 və admin paket məlumatları üzrə 26 SQL yoxlaması da keçib. Köhnə admin sınağı üçün yalnız həmin geri qaytarılan tranzaksiyada şəkil tanıma yoxlaması müvəqqəti söndürülüb.
- Admin paket axtarışı `Təcili`, `TƏCİLİ` və `tecili` ilə eyni paketi tapır. Sorğu UUID-si ilə keçidin üstünlüyü və ödəniş statusu filtri saxlanılır; ayrıca SQL istinadı [database/urgent-payment-search.sql](database/urgent-payment-search.sql).
- SQL təcrid edilmiş PostgreSQL-də iki dəfə qurulub; sorğu → ödəniş təsdiqi → ayrıca yayım → redaktədən sonra təkrar yayım → satıldı axını yoxlanıb. Mövcud cron-un yalnız VIP/Premium/Standart paketlərini müddətləndirdiyi yoxlanıb.

Brauzer sınaqlarında API, Auth, şəkil yükləməsi və ödəniş cavabları imitasiya olunur. Real elan, istifadəçi məktubu və ya ödəniş yaradılmır. SQL sınaqları tranzaksiya sonunda geri qaytarılır. Real şəkillər və əvvəlki paket tarixçəsi dəyişdirilmir.
