# Domen alınmazdan əvvəl düzəlişlər

Bu mərhələdə əvvəlki sınaqların təkrarı ilə kifayətlənmədən yeni istifadəçi ssenariləri yoxlanıb və aşağıdakı səhvlər düzəldilib.

- **Giriş və bərpa pəncərəsi:** telefon ekranında arxadakı səhifə sürüşmür; fokus pəncərədə qalır, Escape bağlayır və əvvəlki düyməyə qayıdır. Açıq elan və tam ekran şəklin üstündən gələn bərpa keçidi görünən bərpa ekranını açır. Bağlanmış pəncərəni gecikmiş cavab yenidən açmır.
- **Elan göndərişinin təkrarı:** server elanı saxlayıb cavab itəndə eyni açıq formanın yenidən göndərilməsi əvvəlki nəticəni hesab və müraciət açarı ilə tapır. Baza eyni hesab/müraciət açarının ikinci elan yaratmasını bloklayır. Paket sorğusu ayrıca təkrarlanmır. Açar sonrakı redaktələrdə qorunur.
- **Formanın saxlanması:** yükləmə/göndəriş davam edərkən sahələr bağlıdır. Uğursuzluqdan sonra yazılan yeni məlumatlar itmir; əvvəlki göndəriş sonradan tapılarsa, həmin elan üzərində redaktə davam edir. Köhnə hesabın cavabı yeni hesabın formasını sıfırlamır.
- **Şəkil yükləmə:** korlanmış və şəkil kimi açıla bilməyən fayllar qəbul edilmir. Dəstəklənən brauzer dekoderi ilə hazırlanan fayllar su nişanı və ölçü məhdudiyyəti alır. Bir yükləmə uğursuz olanda başlamış digər yükləmələrin bitməsi gözlənilir; həmin açıq formada uğurla yüklənmiş dəyişməz fayllar təkrar göndərilmir.
- **Seçilmişlər:** yaddaş açarı telefon nömrəsi əvəzinə hesab ID-sinə bağlıdır. Eyni telefonlu iki hesab siyahını avtomatik bölüşmür; nömrə dəyişəndə siyahı qalır. Köhnə cihaz siyahısı silinmir, istifadəçinin ayrıca seçimi ilə bir dəfə gətirilə bilər.
- **Gecikmiş elan keçidi:** istifadəçi səhifə, axtarış, filtr və ya başqa bölmə seçəndə əvvəlki paylaşım keçidinin gecikmiş cavabı həmin seçimin üstünə elan pəncərəsi açmır.

## Yoxlama

Yeni brauzer sınaqları HTTP sorğularını tam əvəz edir; real istifadəçi hesabı, elan, ödəniş, SMS və e-poçt əməliyyatı aparmır. Baza sınağı mövcud rollarla sintetik sətirlər yaradır və tranzaksiyanı **ROLLBACK** edir.

`database/listing-submission-idempotency.sql` tətbiq edilib. Yeni sütun və açıq API icazəsi əlavə edilmir; şəxsi trigger funksiyası `anon` və `authenticated` üçün birbaşa çağırıla bilmir. `tests/submission-idempotency-db.sql` üzrə 10 yoxlama keçib. Elanların, paket sorğularının və şəkil obyektlərinin əvvəl/sonra izləri eynidir.

- Tam avtomatik dəst: **60 Node və 146 Chromium brauzer sınağı** keçib. Son əlavə edilmiş eyni hesabda köhnə formanın gecikmiş cavabı üçün ayrıca təkrar dəst **7/7** keçib; bu dəst tam sınaqdakı 6 göndəriş halını da əhatə edir.
- JavaScript sintaksisi və `git diff --check` keçib. İlkin 46 daxili şəklin baytları və 56 istinadının eyniliyi Node sınaqlarında qorunur.
- Canlı yayım üçün yeni göndəriş, şəkil, giriş/bərpa, seçilmişlər və gecikmiş keçid ssenariləri yayımlanmış statik fayllarla ayrıca yoxlanır; yazma tələb edən sorğular həmin yoxlamada da sintetik cavablarla əvəz edilir. Faktiki açıq elan və şəkil yalnız oxunur. Canlı nəticə istifadəçiyə ayrıca bildirilir.

## Əhatənin sərhədləri

Müraciət açarı və uğurlu şəkil yükləmələrinin yaddaşı cari açıq formanın təkrar cəhdlərinə aiddir; səhifə bağlanıb yenidən açılanda yarımçıq formanın bərpası ayrıca funksiya deyil. Seçilmişlər həmin brauzerin yaddaşında saxlanılır; cihazlar arasında sinxronlaşdırma əlavə olunmayıb.

Domen/hostinq keçidi və real bank inteqrasiyası istifadəçinin planına uyğun sonrakı mərhələdir. SMS provayderi olmadığından telefon kodu göndərişi aktiv deyil. Mövcud təhlükəsizlik məsləhətlərində yeni xəbərdarlıq yaranmayıb: admin RPC-lərinin daxili rol yoxlamaları əvvəlki baza sınaqlarında təsdiqlənib; sızdırılmış parol qoruması isə əvvəlki kimi aktiv deyil ([Supabase izahı](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection)). Yeni funksiyaya aid birbaşa icazə verilməyib.
