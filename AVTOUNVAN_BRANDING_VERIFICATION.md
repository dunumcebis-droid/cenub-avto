# AvtoUnvan brend və əlaqə yoxlaması — 20 noyabr 2026

Cari brend **AvtoUnvan**, dəstək və admin ünvanı **avtounvan@gmail.com**, telefon **0709091997**-dir. Şüar **Xəyal etdiyin avtomobili kəşf et** saxlanılıb. Domen və hostinq alınıb; sayt **https://avtounvan.vip/** ünvanında HTTPS ilə işləyir. `www` ünvanı da eyni ictimai faylları göstərir.

## Cari canlı vəziyyət — 20 noyabr 2026

İstifadəçi yenilənmiş ictimai ZIP-i hostinqin `/domains/avtounvan.vip/public_html` qovluğunda açıb. Yeni domenin **76/76 ictimai faylı** 200 cavabı qaytarır və cari mənbə ilə bayt-bayt eynidir. Altı HTML səhifəsində yeni brend və loqo görünür; e-poçt göstərilən hissələrdə yalnız `avtounvan@gmail.com` var. Görünən mətnlərdə əvvəlki brend qalmayıb. Ana səhifə, dəstək, parol bərpası və CSS `www` üzərindən də apex ilə eynidir.

Altı səhifənin mobil və masaüstü **12 canlı görünüşü** yoxlanılıb. Faktiki açıq elan baxışında iki ictimai oxuma sorğusu **200** qaytarıb. Bu yoxlamalarda agent real hesab, parol, elan, e-poçt və ya şəkil təhlili yaratmayıb.

Edge Functions **`ca-admin-email-change` v5** və **`ca-photo-review` v7** aktivdir; hər ikisində **`verify_jwt=true`** saxlanılıb. Faktiki işləyən HTTPS apex və `www`, həmçinin mövcud GitHub origin-i üçün uyğunluq və icazəsiz originlərin rədd edilməsi daxil olmaqla **14/14 CORS yoxlaması** keçib. Giriş yoxlamaları və admin səlahiyyəti qaydaları qorunub.

İstifadəçinin Supabase ekran görüntüsündə **Site URL** `https://avtounvan.vip/` olaraq saxlanılıb, **Redirect URLs** siyahısında bu dörd ünvan görünür:

- `https://avtounvan.vip/`
- `https://avtounvan.vip/reset-password.html`
- `https://www.avtounvan.vip/`
- `https://www.avtounvan.vip/reset-password.html`

İstifadəçiyə yeni domenin bərpa səhifəsindən `avtounvan@gmail.com` üçün təzə məktub istəmək və son məktubdakı keçidi açmaq tapşırılıb. İstifadəçi **«Hazirdi parolu deyisdim»** deyərək real bərpa axınında parolunu uğurla dəyişdirdiyini təsdiqləyib. Bu, sahibin real sınağıdır; agent müstəqil Auth yazması etməyib və parolu görməyib. SMTP göndərəni əvvəl təsdiqlənmiş **AvtoUnvan <avtounvan@gmail.com>** olaraq qalır. [SMTP və bərpa vəziyyəti](EMAIL_SENDER_SETUP.md).

Google Search Console sahiblik təsdiqi və sitemap təqdimatı ayrıca addımdır; onların tamamlandığı təsdiqlənməyib.

## Brend dəyişikliyinin tarixçəsi — 19 noyabr 2026

Aşağıdakı ölçülər, sınaq sayları və commit/yayım identifikatorları 19 noyabr tarixli brend və Gmail keçidinin sübutlarıdır. Həmin vaxt domen və yeni hostinq hələ alınmamışdı; əsas yayım GitHub Pages idi. Cari 20 noyabr vəziyyəti yuxarıda göstərilir.

İstifadəçinin avtomobil silueti və **AVTO ÜNVAN** yazısı şəffaf fonlu ayrıca PNG-yə uyğunlaşdırılıb: `assets/branding/avtounvan-logo.png`, **2176×723**. Tünd başlıqda CSS qara silueti ağ göstərir; boz düzbucaqlı yoxdur. Altı səhifənin şəkil ölçüləri və SEO metadata-sı həmin assetə uyğundur.

Altı səhifənin başlığı, logo təsviri, alt yazısı, dəstək keçidləri, qaydalar pəncərəsi, paylaşım mətni və dinamik SEO yenilənib. Yeni foto su nişanı **AVTOUNVAN**-dır. Mövcud şəkillərə yazılmış köhnə nişanlar və saxlanılmış şəkillər yenidən yazılmayıb. 46 ilkin faylın uzunluğu və SHA-256-si, 56 istinad identifikatoru qorunub. Texniki saxlanc açarları, RPC/API ünvanları, hesablar, elanlar, paketlər və formatlar dəyişdirilməyib.

### Yerli yoxlama — 19 noyabr

- **128 Node**, **5 statik SEO** sınağı keçir.
- **9 SEO + 5 su nişanı + 15 admin Gmaili** imitasiya edilmiş brauzer sınağı keçir. Serverin 17 təhlükəsizlik ssenarisi ümumi Node sayına daxildir.
- Altı səhifə × 375/1440 px = **12 görünüş**: logo tamdır, fon uyğun gəlir, en daşması və başlıq düymələrinin örtüşməsi yoxdur. Paylaşım yeni brenddir; hazırlanmış JPEG yeni su nişanını daşıyır. Brauzer səhvi yoxdur.
- Bütün avtomatik Auth/API/provayder cavabları imitasiya edilir. Real məktub, parol, elan, şəkil və ödəniş yaradılmır.
- SEO generatorunun `--check` yoxlaması keçir. Search Console təsdiqi istifadəçinin qərarı ilə domen/hostinq qoşulandan sonraya saxlanılıb.

### Server və sahibin addımları — 19 noyabr

Qorunan `ca-admin-email-change` funksiya həmin tarixdə yeni hədəflə **v3 ACTIVE**, `verify_jwt=true` olaraq yayımlanıb. Çağıranın JWT-si, Auth istifadəçisi və admin RPC-si yoxlanmadan xidmət açarı oxunmur. Yazma yalnız mövcud adminin giriş e-poçtunu və ya mövcud `user_metadata.email` sətrini eyni ünvana uyğunlaşdırır; parol/rol/profil/UUID və digər metadata üçün yazma atributu yoxdur. Təkrar təmiz əməliyyat yazma etmir. Serverin təsdiq siqnalı ilə brauzer sessiyasındakı e-poçt sahəsi də uyğunlaşdırılır. [Admin axını](ADMIN_EMAIL_CHANGE.md).

İstifadəçi qorunan düymə ilə dəyişikliyi tamamlayıb. Yeni ünvan və e-poçt identikliyi, eyni UUID/profil və admin üzvlüyü, təsdiqlənmiş e-poçt canlı bazadan yoxlanılıb. Əvvəlki giriş ünvanına aid hesab sayı sıfırdır. Parol atributu yazılmayıb.

İstifadəçi yeni Gmaildə **AvtoUnvan** tətbiq parolunu yaratdığını və SMTP sahələrini Supabase-də saxladığını təsdiqləyib. Tətbiq parolu söhbətə/koda alınmayıb. İstifadəçi öz bərpa sınağında məktubun çatmasını və yeni göndərən ünvanını təsdiqləyib. [SMTP ayarları](EMAIL_SENDER_SETUP.md).

### GitHub Pages canlı yoxlaması — 19 noyabr

Frontend **bd97fe8** ilə yayımlanıb; GitHub Pages **44616633345** uğurludur. Yayımlanmış fayllarla **27 brauzer sınağı** (9 SEO, 13 admin, 5 su nişanı) keçir. Əlavə müstəqil canlı görünüş yoxlamasında altı səhifənin **12 görünüşü**, **29 statik faylın bayt uyğunluğu** təsdiqlənib. Real Auth/API/provayder cavabları bu sınaqlarda imitasiya olunub; şəbəkəyə yalnız açıq statik GET sorğuları gedib.

Ayrı anonim, yalnız oxuma yoxlamasında faktiki açıq elan, dinamik Car/Offer metadata-sı və pəncərə bağlananda əsas səhifənin bərpası keçir. 320/375/768/1440 px enlərdə iki sütun saxlanılır, səhifə və HTTP xətası yoxdur. İki real siyahı-oxuma RPC-si icra olunub; analitika yazması imitasiya olunub. Real məktub və məlumat yazması yoxdur.

Server v2 üçün girişsiz preflight **204**, tokensiz/yanlış tokenli POST sorğuları **401** qaytarır. Adminin real e-poçt dəyişikliyini isə avtomatik sınaq yox, istifadəçinin öz qorunan klik əməliyyatı icra edib.

Yeni SMTP sahələrinin saxlanması istifadəçi tərəfindən təsdiqlənib. İstifadəçi öz bərpa sınağında yeni göndərənin real məktubda görünməsini təsdiqləyib. Avtomatik sınaqlar real məktub göndərməyib; 19 noyabr yoxlaması vaxtı həmin məktubdakı yeni keçidin açılması/parol dəyişikliyi ayrıca təsdiqlənməmişdi. Yeni domendə real parol dəyişikliyini istifadəçi 20 noyabrda yuxarıda göstərildiyi kimi təsdiqləyib.


### Gmail təmizləməsi — 19 noyabr

Köhnə ünvanın əlavə hesab qeydində qalması aşkarlandıqdan sonra v3 qorunan əməliyyat və brauzer keşinin uyğunlaşdırılması əlavə olunub. İstifadəçi yeni səhifədə düyməyə basıb və uğur mesajını təsdiqləyib. Son canlı baza yoxlamasında giriş, identiklik və `user_metadata.email` yeni ünvandır; əvvəlki Gmaillər cari profil/metadata/identiklik sahələrində yoxdur. Digər user metadata və app metadata əvvəl/sonra heş müqayisəsində eynidir. Eyni admin UUID-si, rolu və profili qorunub; parol atributu heç bir yeniləmə sorğusuna daxil edilməyib.

Cari repozitoriya fayllarındakı əvvəlki real Gmail istinadlarının sayı **0**-dır. Testlərdə əvvəlki ünvan üçün ümumi saxta nümunə istifadə olunur. Git tarixçəsi və artıq göndərilmiş məktublar yenidən yazılmayıb.

19 noyabr Gmail təmizləməsinin runtime dəyişiklikləri **d44257f**, Pages yayımı **44619722466** ilə uğurla yayımlanıb. Yeni kodla **128/128 Node** və **15/15 admin brauzer** sınağı keçir. Son canlı admin sınağında **46 statik faylın bayt uyğunluğu** təsdiqlənib; Auth/SMTP/provayder cavabları imitasiya olunub, real məktub və hesab yazması yoxdur. Real hesab təmizləməsini istifadəçinin qorunan klik əməliyyatı, real SMTP məktubunu istifadəçinin öz bərpa sınağı icra edib.
