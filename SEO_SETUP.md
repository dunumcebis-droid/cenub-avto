# AvtoUnvan SEO ayarları

SEO saytın axtarış sistemləri tərəfindən tapılmasını və məzmununun düzgün anlaşılmasını asanlaşdırır. Bu hazırlıq Google-da indekslənmə, nəticə sırası və ya dərhal ziyarətçi artımı vəd etmir.

## Cari ünvan və statik səhifələr

Hazırda istifadə edilən ünvan **https://dunumcebis-droid.github.io/cenub-avto/**-dur. İstifadəçi **avtounvan.vip** domenini aldığını təsdiqləyib; yeni hostinqin aktivləşməsi və HTTPS yayımı hələ yoxlanmayıb. Ona görə repozitoriyanın SEO ünvanları hazırda işləyən GitHub ünvanından hazırlanır. Ayrıca köçürmə paketində isə SEO nəticələri `https://avtounvan.vip/` əsasında yaradılıb və yoxlanılıb.

`seo.config.json` SEO üçün əsas mənbədir: sayt ünvanı, brend, açıq dəstək əlaqələri, mövcud loqo, səhifə başlıqları, təsvirlər və Google təsdiq tokeni burada saxlanılır. Faylda parol, API açarı və şəxsi elan məlumatı saxlanılmır.

- Ana səhifə, haqqımızda, dəstək, istifadə qaydaları və məxfilik siyasəti üçün ayrıca başlıq, təsvir, Open Graph və Twitter metadata var. `sitemap.xml` bu beş açıq səhifənin tam ünvanlarını göstərir.
- Ana səhifənin ilkin HTML-ində doğru `WebSite` və `Organization` JSON-LD məlumatı var: AvtoUnvan adı, mövcud loqo, şüar, dəstək e-poçtu və telefonu. Ünvan, reytinq, rəy sayı və işləməyən `SearchAction` əlavə edilmir.
- Dörd məlumat səhifəsi öz tam `canonical` ünvanını göstərir. Ana səhifə eyni zamanda `?ad=...` elan keçidlərini açdığı üçün ilkin HTML-də `canonical` yoxdur; həmin ünvanı `assets/js/21-seo.js` açılan marşruta uyğun yaradır. Ana səhifənin ilkin `og:url` dəyəri bu skript üçün əsas sayt ünvanıdır.
- `reset-password.html` ilkin HTML-də `noindex, nofollow` saxlayır. Bərpa səhifəsi sitemap-a daxil edilmir, açıq paylaşım metadata-sı və canonical almır. Məxfilik **siyasəti** isə ziyarətçilər üçün açıq məlumat səhifəsidir və sitemap-a daxildir.
- Sitemap-a şəxsi kabinet, giriş/bərpa tokenləri, filtr variantları və ya bazadan elan nüsxələri yazılmır. Elan keçidlərinin tapılması tətbiqdəki açıq elan keçidləri ilə təmin edilir; bu statik generator elan bazasını oxumur.

Sitemap-da süni `lastmod`, `priority` və `changefreq` yoxdur. Generator tarixləri hər işə salınanda dəyişdirmir.

## Açıq elanlar və səhifələmə

Elan başlıqları həqiqi `href="?ad=..."` keçidləridir: adi toxunuş mövcud elan pəncərəsini açır, ayrıca vərəqdə açmaq da işləyir. Filtrsiz, standart sıralamada səhifə düymələri `?page=2` kimi izlənə bilən keçidlərdir; birbaşa həmin ünvan açılanda uyğun səhifə yüklənir. Filtrlənmiş və başqa cür sıralanmış nəticələr ayrıca indekslənmir.

Açılmış aktiv, açıq elan üçün başlıq, təsvir, canonical və sosial metadata faktiki avtomobil məlumatlarından hazırlanır. `Car` və `Offer` JSON-LD-si yalnız mövcud qiymət, şəkil və xüsusiyyətlərdən istifadə edir. Elan bağlananda əsas səhifənin metadata-sı bərpa edilir. Admin önbaxışı, şəxsi kabinet, giriş ekranı, satılmış və əlçatmaz elanlar açıq avtomobil sxemi yaratmır; uyğun indeksləmə məhdudiyyəti alır.

## Yenidən yaratmaq və yoxlamaq

Bu alət Node.js ilə işləyir, əlavə paket, şəbəkə və build mərhələsi tələb etmir:

```sh
node tools/generate-seo.cjs
node tools/generate-seo.cjs --check
```

Birinci əmr altı HTML faylındakı `<!-- SEO:BEGIN -->` / `<!-- SEO:END -->` bloklarını, `sitemap.xml` və `robots.txt` fayllarını yeniləyir. İkinci əmr heç nə yazmadan yaradılmış faylların konfiqurasiyaya uyğunluğunu yoxlayır; köhnə nəticə varsa uğursuz çıxış kodu verir. Eyni konfiqurasiya eyni nəticəni yaradır. Metadata dəyişikliklərini `seo.config.json`-da edin, sonra generatoru işə salın; həmin bloklara əl ilə edilmiş dəyişikliklər növbəti generasiyada əvəzlənir.

## GitHub Pages layihə yolunun məhdudiyyətləri

Bu repozitoriyanın `robots.txt` faylı **/cenub-avto/robots.txt** ünvanında yayımlanır. Google robots qaydalarını hostun kökündəki **https://dunumcebis-droid.github.io/robots.txt** ünvanından oxuyur. Layihə daxilindəki fayl kök robots qaydası sayılmır; onun Google üçün işlədiyini və ya bərpa səhifəsini blokladığını iddia etmirik. Ona görə sitemap birbaşa Search Console-a təqdim edilməli, indeksdən kənar səhifələrin göstərişi öz HTML-ində `noindex` ilə verilməlidir. Google-un bu göstərişi oxuya bilməsi üçün səhifənin crawl edilməsi qadağan olunmur.

Google-un ayrıca **sayt adı** funksiyası domen və subdomen köklərində işləyir; `/cenub-avto/` kimi alt qovluqlar üçün ayrıca sayt adı dəstəklənmir. `WebSite` məlumatının əlavə edilməsi hazırkı layihə ünvanında axtarış nəticəsində mütləq «AvtoUnvan» sayt adı göstəriləcəyi demək deyil.

Elan məzmunu JavaScript və açıq API cavabından sonra göstərilir. Google-un render etməsi tələb olunur; JavaScript işlətməyən sosial paylaşım botları ilkin ümumi AvtoUnvan metadata-sını görə bilər. Hər elan üçün serverdən hazır HTML və sosial önbaxış ayrı gələcək hosting işi tələb edir.

## Google Search Console-a qoşmaq

İstifadəçinin qərarı ilə sahiblik təsdiqi şəxsi domen və hostinq qoşulandan sonra aparılacaq. Sahiblik hələ təsdiqlənməyib; `googleSiteVerification` hazırda boşdur. Konfiqurasiyada saxta təsdiq tokeni yoxdur və bu iş Search Console-a sitemap göndərildiyi iddiasını etmir.

1. [Google Search Console](https://search.google.com/search-console/) açın və **URL prefix** xüsusiyyəti yaradın: `https://dunumcebis-droid.github.io/cenub-avto/`.
2. Sahiblik yoxlamasında **HTML tag** üsulunu seçin. Verilən `<meta name="google-site-verification" content="...">` içində yalnız açıq `content` tokenini `seo.config.json` → `googleSiteVerification` sahəsinə köçürün.
3. `node tools/generate-seo.cjs` işə salın və dəyişiklikləri mövcud GitHub Pages yayımı ilə yayımlayın. Token yalnız ana səhifənin HTML-inə əlavə edilir.
4. Search Console-da **Verify** seçin. Sonra **Sitemaps** bölməsinə `sitemap.xml` əlavə edin. Tam ünvan: https://dunumcebis-droid.github.io/cenub-avto/sitemap.xml.
5. **URL Inspection** ilə ana səhifəni və bir açıq elan URL-ni yoxlayın. Canlı testin render edilmiş HTML-ində məzmunu, tək canonical-ı və robots göstərişini yoxlayın; lazım gəlsə indekslənmə sorğusu göndərin. Sayt adı `Rich Results Test` tərəfindən yoxlanmır; JSON-LD üçün [Schema Markup Validator](https://validator.schema.org/) istifadə edilə bilər.

Google-un saytın yeni vəziyyətini tapması və işləməsi vaxt ala bilər. Sitemap təqdimatı URL-lərin indekslənməsinə zəmanət vermir; Search Console hesabatında sonrakı vəziyyət ayrıca izlənməlidir.

## Öz domeninə keçəndə

Yalnız istifadəçinin sahibi olduğu və sayta həqiqətən qoşulmuş domen üçün `seo.config.json` içindəki `baseUrl` dəyişdirilir. Ünvan `https://` ilə başlamalı və `/` ilə bitməlidir. Sonra generatoru və yoxlama əmrini işə salıb hazır faylları yayımlayın. Canonical, Open Graph/Twitter şəkil ünvanları, JSON-LD və sitemap eyni mənbədən yenilənir; kökdə yayımlanan `robots.txt` artıq həmin host üçün uyğun yerdə olacaq.

Domenin DNS/HTTPS ayarları, əvvəlki ünvandan yönləndirmə və hesab/bərpa keçidlərinin domenə uyğunlaşdırılması ayrıca hosting və giriş konfiqurasiyasıdır; SEO generatoru bunları dəyişdirmir. Yeni ünvan üçün Search Console sahiblik yoxlamasını yenidən edin, həmin xüsusiyyətin tokenini istifadə edin və yeni sitemap-ı təqdim edin.

`avtounvan.vip` üçün əvvəlcə hostinq aktivləşdirilməli, ictimai ZIP `public_html` daxilində açılmalı, DNS hostinqə bağlanmalı və HTTPS yoxlanmalıdır. Bundan sonra Supabase Auth **Site URL** `https://avtounvan.vip/` seçilir; **Redirect URLs** siyahısına `https://avtounvan.vip/` və `https://avtounvan.vip/reset-password.html` əlavə olunur. Keçid dövründə mövcud GitHub ünvanları saxlanılır. `www` yalnız ayrıca işləməsi təsdiqlənəndən sonra əlavə edilə bilər. SMTP göndərəni `avtounvan@gmail.com` olaraq qalır. Əsas `baseUrl` yalnız yeni HTTPS sayt yoxlanandan sonra yenilənəcək.

`.github/workflows/recover-pages.yml` əvvəlki konkret ilişmiş yayımı ləğv etmək üçündür. SEO generatoru həmin workflow-u dəyişdirmir və işə salmır; SEO üçün hosting rejimi dəyişdirilməyib.

## Google-un rəsmi istinadları

19 noyabr 2026 tarixində tətbiq olunan yanaşma rəsmi sənədlərlə tutuşdurulub:

- [JavaScript SEO: keçidlər, canonical, noindex və render](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
- [Canonical URL seçimi](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- [Sitemap yaratmaq və təqdim etmək](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [robots.txt-in yerləşməsi və qaydaları](https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec)
- [Google sayt adları və alt qovluq məhdudiyyəti](https://developers.google.com/search/docs/appearance/site-names)
- [Organization metadata-sı](https://developers.google.com/search/docs/appearance/structured-data/organization)
