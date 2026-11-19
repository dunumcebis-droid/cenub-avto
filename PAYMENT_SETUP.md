# Bank ödənişinin aktivləşdirilməsi

İstifadəçinin əvvəlki qərarına görə VÖEN və ABB ilə merchant/internet ekvayrinq hesabı açılmalıdır. Bankın müqaviləsi və inteqrasiya girişləri verilməyib. Buna görə sayt kartdan pul çıxarmır, avtomatik ödəniş uğuru göstərmir və paket seçimini bank ödənişi kimi təqdim etmir. Mövcud adminə paket sorğusu axını işləyir.

Bank hazır olduqda aşağıdakılar tamamlanır:

- Bankın verdiyi rəsmi test/istehsal inteqrasiya sənədi, API ünvanları və merchant girişləri alınır. Məxfi açarlar yalnız serverin məxfi ayarlarına yerləşdirilir; söhbətə, HTML/JavaScript-ə və GitHub-a əlavə edilmir.
- Sifarişin paket/qiymət/müddəti serverdə mövcud qiymətlərlə yoxlanır: Təcili 1 AZN (elan satılanadək, gün limiti yoxdur); Üstün/Premium 5 AZN və 10 gün; Önə çıxarılan/VIP 10 AZN və 15 gün. Sərfəli/Standart yeni sifarişlərdə yoxdur. İstifadəçi brauzerindən «ödənilib» iddiası qəbul edilmir.
- Bankın təsdiq cavabı serverdə sənədləşdirilmiş qayda ilə doğrulanır; eyni ödəniş iki dəfə tətbiq edilmir. Ödənişin və elanın moderasiya təsdiqi ayrı qalır.
- Bankın sınaq mühitində uğur, imtina, yarımçıq dönüş, təkrar bildiriş və geri qaytarma halları yoxlanır. Real pul sınağı ayrıca icazə ilə edilir.
- Bank funksiyası aktivləşəndə saytın ödəniş bildirişləri və qaydalar/məxfilik mətnləri faktiki axına uyğun yenilənir.

Mövcud bank hesabı və sənədləri olmadan provayderin API-sini və ya real kart əməliyyatını uydurmaq olmaz. Bu mərhələdə heç bir real ödəniş və bank əməliyyatı edilməyib.
