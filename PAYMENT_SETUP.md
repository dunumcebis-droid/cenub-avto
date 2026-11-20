# Epoint ödənişinin qoşulması

20 noyabr 2026: istifadəçi Epoint seçib, VÖEN və biznes bank hesabının hazır olduğunu bildirib. Tacir qeydiyyatı davam edir; fəaliyyət kodunun anketdə uyğunlaşdırılması üçün Epoint dəstəyinə müraciət edilib. Tacir təsdiqi və API açarları hələ alınmayıb. Mövcud paket müraciəti və admin təsdiqi axını işləyir; avtomatik kart ödənişi aktiv deyil.

## Qeydiyyatdan asılı olmayan hazırlıq

Server üçün ayrıca protokol modulu `supabase/functions/_shared/epoint-protocol.mjs` və yalnız imitasiya edilmiş şəbəkə cavabları ilə işləyən `tests/epoint-protocol.test.cjs` hazırlanıb. Modul imzalanmış ödəniş/status sorğularını, bildirişin imza və məbləğ yoxlamasını, məhdud HTTPS yönləndirmələrini və qeyri-müəyyən sorğu nəticələrinin təhlükəsiz qaytarılmasını əhatə edir. Bu, öz-özünə paket təsdiqləyən ödəniş xidməti deyil.

Modulun müstəqil yoxlaması:

```sh
node --test tests/epoint-protocol.test.cjs
```

17 protokol sınağı və ayrıca 17 müstəqil yoxlama keçib. Mövcud kodla birlikdə tam Node dəsti 166/166 uğurludur. [Yoxlanmış əhatə və qalan işlər](tests/reports/epoint-preparation-20261120.json) qeydə alınıb; bunlar həqiqi tacir mühitində keçirilmiş ödəniş sınaqları deyil.

Modul saytda istifadə edilmir və 77 fayllıq hostinq paketinə daxil deyil. Bu hazırlıqda yeni Edge Function, baza cədvəli, ictimai ödəniş düyməsi və ya real provayder əməliyyatı yaradılmır.

## Təsdiqlənmiş protokol

Rəsmi sənədə görə ödəniş yaratmaq üçün `https://epoint.az/api/1/request`, status sorğusu üçün `https://epoint.az/api/1/get-status` istifadə olunur. Sorğu `data` və `signature` forma sahələri ilə göndərilir; imza orijinal base64 sətrinin üzərində Epoint-in sənədləşdirdiyi SHA-1 düsturu ilə hesablanır. Bu imza düsturu HMAC deyil.

Ödənişin valyutası bu saytda AZN olaraq sabitlənəcək. Bildiriş və status sxemində valyuta sahəsi həmişə sənədləşdirilməyib; ona görə əsas etibar serverdə saxlanılan dəyişməz sifarişə verilir. Ziddiyyətli valyuta qəbul edilmir. Müştəri ödənişinin əməliyyat kodu `100`-dür; kart qeydiyyatı ödəniş təsdiqi sayıla bilməz. `success` nəticəsi yalnız yoxlanmış sifarişlə uyğun gələndə maliyyə müşahidəsi kimi qəbul edilir; `returned` geri qaytarılmadır, `server_error` isə status sorğusunun xətasıdır.

Provayder eyni sifariş ID-si ilə təkrar yaratma sorğusunun təhlükəsizliyinə zəmanət vermir. Göndərilmiş sorğunun cavabı itərsə, yeni ödəniş avtomatik yaradılmamalıdır. Saytda görünən uğurlu dönüş ünvanı ödənişin sübutu deyil.

`decodeVerifiedEpointCallback` yalnız imzalanmış məhdud məlumatı qaytarır; ödənişə və paketə hüquq vermir. `validateEpointObservation` saxlanılan sifarişə uyğunluğu yoxlayır, imzanı özü yoxlamır. Hər iki mərhələdən sonra atomik baza qeydi tələb olunur. Modul təkrar bildirişi yeni ödənişdən ayıran davamlı yaddaş saxlamır.

Cari sənəddə məbləğin tipi `Number`, bəzi nümunələrdə isə mətn kimi göstərilib. Hazırlanan sorğu sənədləşdirilən rəqəm tipindən istifadə edir və qəpiklə dəyərin dəqiq geri çevrilməsini tələb edir. Həqiqi tacir mühitində uyğunluq ayrıca yoxlanmalıdır.

## Canlı qoşulmanın qalan hissəsi

1. Epoint tacir qeydiyyatını və fəaliyyət məlumatlarını təsdiqləyir. Sayt, uğurlu/uğursuz dönüş və server nəticə ünvanları razılaşdırılır. Provayderin faktiki HTTPS ödəniş səhifəsi domenləri, bildirişə gözlənilən cavab və təkrar göndərmə qaydası dəqiqləşdirilir; sənəddəki nümunə bank domeni həqiqi ünvan kimi istifadə edilmir.
2. Ödəniş sifarişi bazada sahiblik yoxlaması ilə mövcud paket müraciətindən yaradılır. Paket, qəpiklə məbləğ və AZN valyutası dəyişməz saxlanılır: Təcili 100 qəpik/satılanadək, Üstün 500 qəpik/10 gün, Önə çıxarılan 1000 qəpik/15 gün. Yeni Standart sifarişləri qəbul edilmir. Qiymət brauzerdən götürülmür.
3. Məxfi ödəniş cədvəli və atomik tətbiq funksiyası hazırlanıb sınaqdan keçirilir. Eyni provayder əməliyyatı ikinci dəfə paket verməməlidir. Yeni ödəniş rezervasiyası əvvəlki əl ilə admin təsdiqi/rəddi ilə uzlaşdırılmalıdır. Ödənişin təsdiqi elanın moderasiyasını əvəz etmir.
4. İmzalanmış bildiriş və server status sorğusu saxlanılan sifariş ID-si, provayder əməliyyatı, məbləğ və əməliyyat növü ilə tutuşdurulur. Elan satılıb, arxivləşib və ya müraciət artıq başqa yolla tamamlanıbsa, pulun gəldiyi qeyd olunur və hal ayrıca araşdırmaya çıxarılır. Gecikmiş uğur cavabı geri qaytarılmış ödənişi yenidən aktivləşdirməməlidir.
5. Müştəri düyməsi və nəticə ekranı sahibinə məxsus sifarişlə işləyir. Dönüş ünvanları serverdə sabit verilir, brauzerin sorğusundan götürülmür. Məxfi açar [Supabase Edge Function Secrets](https://supabase.com/docs/guides/functions/secrets) vasitəsilə serverdə saxlanılır. Açar söhbətə, GitHub-a və açıq JavaScript-ə yazılmır.
6. Ödəniş tarixçəsi üçün bərpa/uzlaşdırma qaydası tamamlanır. Mövcud admin ZIP ixracının 12 mənbəlik siyahısı gələcək ödəniş cədvəlini avtomatik əhatə etmir.
7. Bütün axın təsdiqlənmiş test mühitində yoxlanır: uğur, imtina, itmiş cavab, təkrar/paralel bildiriş, saxta dönüş, məbləğ fərqi, əl ilə təsdiqlə yarış və geri qaytarma. Real pul sınağı ayrıca razılaşdırılır. Qaydalar və məxfilik mətnləri faktiki ödəniş axınına uyğun yenilənir.

## Rəsmi mənbələr

- [Epoint API PDF, v1.0.3](https://epointbucket.s3.eu-central-1.amazonaws.com/files/instructions/API%20Epoint%20en.pdf)
- [Ödəniş yaratma](https://developer.epoint.az/az/checkout/request), [bildirişlər](https://developer.epoint.az/en/callbacks), [status sorğusu](https://developer.epoint.az/az/status/get-status)
- [Epoint qeydiyyatı](https://epoint.az/az/registration) və [rəsmi dəstək](https://epoint.az/az/contact): +99470 242 99 66, +99412 488 64 47

Texniki əsas PDF və cari sənəd çıxarışları ilə tutuşdurulub. Developer portalının birbaşa oxunuşu bəzi sorğularda 403 qaytarıb. Burada provayderin real cavab domenləri və bildiriş cavab formatı yoxlanmış kimi təqdim edilmir.
