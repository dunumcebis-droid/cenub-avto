# AvtoUnvan brend və əlaqə yoxlaması — 19 noyabr 2026

Cari brend **AvtoUnvan**, dəstək ünvanı **avtounvan@gmail.com**, telefon **0709091997**-dir. Şüar **Xəyal etdiyin avtomobili kəşf et** saxlanılıb. Domen və yeni hostinq hələ alınmayıb; real GitHub Pages ünvanı dəyişməyib.

İstifadəçinin avtomobil silueti və **AVTO ÜNVAN** yazısı şəffaf fonlu ayrıca PNG-yə uyğunlaşdırılıb: `assets/branding/avtounvan-logo.png`, **2176×723**. Tünd başlıqda CSS qara silueti ağ göstərir; boz düzbucaqlı yoxdur. Altı səhifənin şəkil ölçüləri və SEO metadata-sı həmin assetə uyğundur.

Altı səhifənin başlığı, logo təsviri, alt yazısı, dəstək keçidləri, qaydalar pəncərəsi, paylaşım mətni və dinamik SEO yenilənib. Yeni foto su nişanı **AVTOUNVAN**-dır. Mövcud şəkillərə yazılmış köhnə nişanlar və saxlanılmış şəkillər yenidən yazılmayıb. 46 ilkin faylın uzunluğu və SHA-256-si, 56 istinad identifikatoru qorunub. Texniki saxlanc açarları, RPC/API ünvanları, hesablar, elanlar, paketlər və formatlar dəyişdirilməyib.

## Yerli yoxlama

- **125 Node**, **5 statik SEO** sınağı keçir.
- **9 SEO + 5 su nişanı + 13 admin Gmaili** imitasiya edilmiş brauzer sınağı keçir. Serverin 14 təhlükəsizlik ssenarisi ümumi Node sayına daxildir.
- Altı səhifə × 375/1440 px = **12 görünüş**: logo tamdır, fon uyğun gəlir, en daşması və başlıq düymələrinin örtüşməsi yoxdur. Paylaşım yeni brenddir; hazırlanmış JPEG yeni su nişanını daşıyır. Brauzer səhvi yoxdur.
- Bütün avtomatik Auth/API/provayder cavabları imitasiya edilir. Real məktub, parol, elan, şəkil və ödəniş yaradılmır.
- SEO generatorunun `--check` yoxlaması keçir. Search Console təsdiqi istifadəçinin qərarı ilə domen/hostinq qoşulandan sonraya saxlanılıb.

## Server və sahibin son addımları

Qorunan `ca-admin-email-change` funksiya yeni hədəflə **v2 ACTIVE**, `verify_jwt=true` olaraq yayımlanıb. Çağıranın JWT-si, Auth istifadəçisi və admin RPC-si yoxlanmadan xidmət açarı oxunmur. Yazma yalnız mövcud adminin e-poçtunu yeniləyir; parol/rol/profil/UUID yazma atributu yoxdur. [Admin axını](ADMIN_EMAIL_CHANGE.md).

Hazırkı admin `?admin-email=1` keçidində **Admin Gmailini dəyiş** düyməsini basmalıdır. Yeni ünvanla real Auth hesabı dəyişikliyi hələ tətbiq edilməyib.

İstifadəçi yeni Gmaildə **AvtoUnvan** tətbiq parolunu yaratdığını və SMTP sahələrini Supabase-də saxladığını təsdiqləyib. Tətbiq parolu söhbətə/koda alınmayıb. Yeni göndərəndən real məktubun çatması hələ yoxlanılmayıb. [SMTP ayarları](EMAIL_SENDER_SETUP.md).

Frontend-in canlı yayımı və real Gmail/admin nəticələri ayrıca yoxlanılacaq; bu sənəd onları əvvəlcədən tamamlanmış saymır.
