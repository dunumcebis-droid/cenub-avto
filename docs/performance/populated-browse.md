# Təcrid edilmiş elan siyahısı sürət sınağı

Bu sınaq canlı Supabase bazasına qoşulmur. Rəsmi PostgreSQL 17.7 Alpine obrazı sabit digest ilə işlədilir. Docker konteynerində şəbəkə, port yayımı və host qovluğu yoxdur; 2 CPU və 768 MiB yaddaş həddi var. Sınaq bitdikdə öz yaratdığı konteyner silinir.

Sintetik məlumat: 10 000 aktiv və satılmamış elan, 250 satılmış, 250 gözləyən və 250 rədd edilmiş elan. Hər elanda 12 saxta foto URL-i, texniki məlumatlar, təsvir, aktiv paketlər və əvvəlki obyekt/mətn JSON formatları var. Foto faylları və real istifadəçi məlumatları yoxdur.

Yerli sınaqda tətbiqin `ca_browse_listings` funksiyası və rəqəm/mətn köməkçiləri repozitoriyadan olduğu kimi götürülür. Standart komanda `database/browse-performance.sql` mövcuddursa həmin son versiyanı quraşdırır; `--baseline` əvvəlki `database/marketplace-features.sql` versiyasını ayrıca ölçür. Hesabat icra edilən funksiya və istinad mənbəyinin SHA-256 izlərini ayrı saxlayır.

Bütün ölçmələr `anon` rolu, RLS və 30 ictimai sütuna məhdud SELECT ilə aparılır. Daxili paket qeydi sütunu qəsdən mövcuddur, bu rola oxuma icazəsi verilmir. Sahib/admin siyasətləri sintetik `authenticated` modelləridir; canlı Auth sxeminin tam bərpası deyil.

Yoxlamalar:

- İlk səhifə, 200-cü və 417-ci səhifə, marka/şəhər/qiymət filtri, qiymətə görə artan və azalan sıralama üçün gözlənilən ID-lər, sıra, say və səhifə sayı dəqiq müqayisə edilir.
- Hər sorğunun tam JSON ölçüsü və bir isti `EXPLAIN ANALYZE` icra vaxtı yazılır. Bir ölçmənin p50/p95 sahələri eyni müşahidədir; ayrıca sabit statistik nəticə sayılmamalıdır.
- `pgbench` 1, 5, 10 və 20 paralel baza sessiyasında standart siyahını, sonra 20 sessiyada birləşmiş filtri oxuyur. Hər müştəri bir tranzaksiya, 1 sessiyalı mərhələ 3 tranzaksiya icra edir; tranzaksiyada yalnız rol/vaxt həddi və SELECT var. Sorğu həddi 15 saniyə, proses həddi 60 saniyədir. Bir mərhələ dayansa növbəti başlanmır.
- Uğurlu tranzaksiyaların p50/p95 vaxtları və tamamlanmamış tranzaksiyalar ayrıca saxlanılır. Bu ölçü HTTP, şəkil baytları, brauzer və model xidmətini əhatə etmir; 20 baza sessiyası «20 real istifadəçiyə zəmanət» deyil.

Təkrar icra (yerli Docker xidməti tələb olunur):

```sh
node tests/performance/populated-browse.cjs
```

Nəticə `tests/performance/populated-browse-result.json` faylına yazılır. Təkrar icra həmin ölçmə hesabatını yeniləyir. Köhnə versiyanın ayrıca diaqnostikası üçün başqa nəticə yolu və `--baseline` istifadə edilir. `--setup-only`, `--keep-container`, `--container=ca-browse-benchmark-...` və `--reference` yalnız eyni lokal sınağın müqayisəsi üçün köməkçi seçimlərdir; saxlanılmış konteyneri operator iş bitdikdən sonra silməlidir.

Əvvəlki materiallaşdırılan geniş sorğuda 10 000 aktiv sintetik elanla paralel mərhələ 15 saniyəlik sorğu həddinə çatıb. Bu, canlı saytın o anda dayanması demək deyil. İslah edilmiş versiyanın ölçmələri və dəqiq müqayisə aşağıdakı JSON hesabatları ilə ayrıca qeyd olunur; ilk uğursuz köhnə icrada ölçmə mərhələsi saxlanmadığı üçün həmin ilkin qeyddən dəqiq paralel sessiya həddi çıxarılmır.

## Yekun nəticə

[472 dəqiq JSON müqayisəsi](browse-parity-result.json) anonim, sahib, admin və başqa daxil olmuş hesab kontekstində keçib. Mətn/obyekt JSON, natamam köhnə məlumatlar, bütün filtrlər, təchizat, paket müddətləri, sıralama, boş nəticə və səhifə hədləri müqayisə edilib. 29 sütunlu açıq cavab eynidir; daxili qeyd sütunu və satılmış/gözləyən elanlar açılmayıb. Sınaq dəyişiklikləri yalnız təcrid edilmiş bazada geri qaytarılıb.

[Son ölçmə](populated-browse-result.json) tam və uğurludur. 10 000 aktiv sintetik elanda standart sorğunun tək isti ölçməsi **50,844 ms**, marka/şəhər/qiymət filtrinin ölçməsi **130,530 ms** olub. 20 paralel baza sessiyasında standart siyahı p95 **339,592 ms**, birləşmiş filtr p95 **1108,307 ms** nəticə verib; bütün 58 tranzaksiya tamamlanıb. Digər mərhələlər 1/5/10 sessiyadır. Sorğu rəqəmləri şəkil yüklənməsi və şəbəkə vaxtı deyil.

`browse_late_projection_performance` miqrasiyası canlıya tətbiq edilib. Sonra canlı bazada geri qaytarılan 155 icazə/həyat dövrü yoxlaması keçib. [21 oxuma sorğusundan ibarət canlı son yoxlama](live-readiness-after.json) da uğurludur; bu anda canlı aktiv elan sayı 0 olduğu üçün dolu bazaya aid sürət rəqəmləri yalnız yuxarıdakı ayrıca mühitdən gəlir.
