# Qalan elan platforması funksiyaları

## Yekun davranış

- Açıq elanlarda hər səhifədə 24 nəticə var. 0–24 nəticədə səhifələmə gizlidir; 25-dən başlayaraq əvvəlki/növbəti və 1, 2, 3… nömrələri görünür. Çox sayda səhifədə cari səhifəyə yaxın düymələr və ilk/son səhifə saxlanılır; bütün nömrələr bir anda yığılmır.
- Elanın «Paylaş» düyməsi yalnız həmin açıq elanın `?ad=UUID` linkini paylaşır/kopyalayır. Yeni telefonda link səhifədə yüklənmiş nəticələrdən asılı olmadan ayrıca anonim, yalnız `aktiv` elan sorğusu ilə açılır. Gözləyən/rədd edilmiş elanlar, yanlış linklər, admin baxışı və bərpa tokenləri paylaşılmır.
- Admin hər kartdan «Şəkillər və tam məlumat» baxışını açır: tam təsvir, bütün məlumatlar, 36-dək şəkil və tam ekran qalereyası. İcazə hər sorğuda serverdə cari admin üzvlüyü ilə yoxlanır. Şəxsi baxış açıq siyahı/cache-ə əlavə olunmur, bağlananda və hesab dəyişəndə DOM və yaddaşdan təmizlənir.
- Yeni `terms.html` və `privacy.html` səhifələri faktiki xidmət, qiymət/müddətlər, moderasiya, açıq telefon/fotolar, arxiv və tam silinmə üçün dəstək yolunu izah edir. Şirkət/VÖEN/ünvan və saxlanma müddəti uydurulmur. Əsas footer-lər, qeydiyyat və elan formaları bu səhifələrə keçid verir; əvvəlki demo mətni qaydalar pəncərəsindən çıxarılıb.
- Ehtiyat nüsxə aləti yalnız admin üçün serverdən elanlar, paket sorğuları, profillər, admin siyahısı və bütün cari `elan-sekilleri` obyektlərinin baytlarını ZIP-ə yığır. Məxfi Auth parolları/tokenləri və server sistem ayarları ixrac edilmir. Bu, tətbiq məlumatlarının nüsxəsidir; PostgreSQL disk nüsxəsi deyil. Sətir sayı, ardıcıl səhifə hash-ləri və son server manifesti yoxlanmadan uğur göstərilmir. Şəkil çatışmazlığı, məlumat dəyişikliyi, dayandırma və hesab dəyişməsi natamam uğur yaratmır. Dəstəklənən brauzerdə birbaşa fayla yazılır; Blob rejimində 512 MiB, ZIP32 formatında 4 GiB həddi aşılarsa aydın xəta verilir, məlumat kəsilmir.
- Şəxsi kabinetdə SMS provayderi üçün hazır telefon təsdiqi axını var. Provayder bağlıdırsa kod göndərildiyi iddia edilmir. Aktiv provayderdə koddan sonra serverin cari hesab üzrə `phone_confirmed_at` sübutu yoxlanır; dəyişdirilə bilən profil iddiası etibarlı sayılmır. E-poçtla giriş və bərpa saxlanılır.

## Baza və icazələr

`admin_detail_and_verified_application_export` miqrasiyası tətbiq edilib. [SQL istinadı](database/admin-read-export.sql). İmtiyazlı oxuma funksiyaları API-yə açılmayan `ca_private` sxemindədir; ictimai RPC-lər `SECURITY INVOKER`-dir. Anonim EXECUTE yoxdur; daxil olmuş adi istifadəçi və saxta `user_metadata.admin=true` iddiası rədd edilir. Parametrlər resurs allowlist-i, UUID cursor və 1–200 səhifə ölçüsü ilə məhduddur.

[Gerçək bazada read-only yoxlama](tests/admin-preview-export-db.sql) bütün beş mənbənin səhifələnməsini və hash bərabərliyini, tam admin baxışını, anonim/adi hesab rəddini və yanlış parametrləri yoxlayıb. Tranzaksiya geri qaytarılıb. Əvvəl/sonra bütün tətbiq cədvəllərinin və şəkil metadatasının hash-ləri eynidir. Yeni təhlükəsizlik məsləhəti yaranmayıb.

## Sınaqlar

- 60/60 Node, əvvəlki 46 şəkil və 56 istinadın eyniliyi daxil olmaqla.
- 117/117 brauzer sınağı, 173,025 saniyə. Bütün API cavabları sınaq məlumatları ilə əvəz olunur; real elan, ödəniş, parol, SMS və ya e-poçt dəyişikliyi edilmir.
- Yeni ssenarilər: 7 səhifə/paylaşım, 6 admin baxışı, 6 ZIP nüsxə, 6 telefon təsdiqi. ZIP faylları ayrıca oxunaraq sətirlər, orijinal foto baytları, CRC və SHA-256 yoxlanır; streaming və Blob çıxışı əhatə olunur.
- 12 mətn/görünüş və 12 gerçək qaydalar/məxfilik səhifəsi ölçüsü 240–1440 px aralığında keçib. JavaScript sintaksisi və diff formatı yoxlanıb.

## Xarici xidmətlər

Real bank ödənişi VÖEN/ABB merchant müqaviləsi və bank girişlərini gözləyir. SMS xidməti hesabı olmadığı üçün real SMS aktivləşdirilməyib. Heç bir ödənişli xidmət açılmayıb və real göndəriş edilməyib. Hazır addımlar: [SMS_SETUP.md](SMS_SETUP.md), [PAYMENT_SETUP.md](PAYMENT_SETUP.md).
