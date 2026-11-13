# 13 noyabr 2026 — sürət və məhdud yük yoxlaması

Bu yoxlama iki fərqli sübutu ayırır: canlı xidmətin qısa paralel oxuma sınağı və yalnız yerli, sintetik məlumatla dolu bazanın sorğu ölçümü. Nəticələr serverin maksimum tutumunu və ya neçə tam istifadəçiyə zəmanət verdiyini göstərmir.

## Canlı xidmət

[Təkrarlanan sınaq](../../tests/performance/live-readiness.py) cəmi **79 HTTP sorğusu** göndərib: 4 statik GET, bir ilkin oxuma və 1/5/10/20 paralellik həddində 74 `ca_browse_listings` oxuma sorğusu. Hamısı HTTP 200 ilə bitib. Xəta, kvota cavabı, real məlumat yazılması, hesaba giriş, e-poçt, model və şəkil yükləmə əməliyyatı olmayıb.

| Paralel HTTP sorğu həddi | Sorğu sayı | p50 | p95 | Ən yavaş |
| --- | ---: | ---: | ---: | ---: |
| 1 | 4 | 621 ms | 763 ms | 763 ms |
| 5 | 10 | 360 ms | 655 ms | 655 ms |
| 10 | 20 | 264 ms | 659 ms | 722 ms |
| 20 | 40 | 326 ms | 689 ms | 720 ms |

İlkin ayrıca sorğu 1532 ms çəkib. Hər iş yeni HTTPS bağlantısından istifadə edib; ölçülərə bu bulud mühitinin şəbəkə, proksi və TLS xərci daxildir. p95 kiçik nümunənin göstəricisidir. Bunlar tam brauzer sessiyası və ya həqiqi 20 nəfərin bütün hərəkətləri deyil.

Həmin anda canlı bazada **0 aktiv elan** olub. Buna görə bu nəticə dolu canlı siyahının sürətini təsdiqləmir. Sintetik məlumat ayrıca mühitdə yoxlanılır; real sayta sınaq elanları yayımlanmır.

HTML/CSS/əsas JavaScript üçün gzip cavabları müşahidə olunub. Əsas JS 888145 baytdan 184461 daşınan bayta sıxılıb; bu, mobil cihazın JavaScript icra vaxtının ölçümü deyil. [Tam say və vaxt hesabatı](live-readiness-result.json) yalnız ölçüləri, statik fayl izlərini və ümumi elan sayını saxlayır; məxfi sətir və açar saxlamır.

Yenidən işə salmaq üçün:

```sh
python3 tests/performance/live-readiness.py --run-live
```

`--run-live` verilmədikdə heç bir sorğu göndərilmir. Skript URL və əməliyyat siyahısını sabit saxlayır, 79 ümumi sorğu / 20 paralel iş / hər sorğuya 15 saniyə / ümumilikdə 180 saniyə hədlərini tətbiq edir. 429, 5xx, başqa xəta və ya cavab formasının uyğunsuzluğunda növbəti işlər dayandırılır. Bu əmri fasiləsiz dövrəyə çevirmək üçün nəzərdə tutulmayıb.

## Əhatə olunmayanlar

Bu ölçü bank/model/SMS provayderinin tutumunu, müxtəlif ölkələrdə mobil interneti, çoxsaylı şəkil göndərişini və uzunmüddətli yüksək trafiki ölçmür. Gerçək elan və trafik artdıqca eyni ölçüləri yeniləmək, server kvotalarını və xərcləri izləmək lazımdır. Canlı məlumatların bərpası və admin şikayətindən keçid ayrıca yoxlamalardır.

## Düzəlişdən sonrakı yoxlama

`--run-live --post-migration` variantı yalnız bir ilkin və 20 paralel oxuma sorğusu göndərir (21 ümumi hədd). Bu mərhələdə 21/21 cavab uğurludur; paralel mərhələnin p95 göstəricisi 973 ms, maksimumu 1062 ms olub. İlk 79 və son 21 sorğu birlikdə bu işdə 100 məhdud canlı oxuma sorğusudur. Şəbəkə/proksi dəyişkənliyi və boş canlı nəticə səbəbindən bu rəqəmlərdən SQL sürət artımı çıxarılmır.

[Dolu bazanın ayrıca ölçmələri və 472 davranış müqayisəsi](populated-browse.md) 10 000 sintetik aktiv elanla aparılıb. Əvvəl bütün elanların geniş məlumatları hesablanırdı; indi filtr üçün lazım olan sahələr və səhifəyə düşən elanlar işlənir. Açıq cavab və giriş qaydaları qorunub.
