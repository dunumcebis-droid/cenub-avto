# Dəstək və admin Gmaili — 19 noyabr 2026

İstifadəçinin seçdiyi ünvan: **azavto44@gmail.com**. Dəstək səhifəsi, qaydalar, məxfilik səhifəsi və qaydalar pəncərəsinin bütün e-poçt keçidləri bu ünvandır. Dəstək telefonu `0709091997`-dir.

## Mövcud admin hesabının yenilənməsi

**19 noyabr 2026 vəziyyəti:** mövcud admin hesabının giriş ünvanı `azavto44@gmail.com` olaraq bazadan təsdiqlənib; istifadəçi yeni ünvanla daxil olduğunu təsdiqləyib. Hesabın UUID-si, profili və admin üzvlüyü saxlanılıb. Parol dəyişdirilməyib.

Köməkçi axın üçün sayta hazırkı admin hesabı ilə daxil olub `?admin-email=1` keçidini açın və **Admin Gmailini dəyiş** düyməsinə basın. Keçid yalnız giriş pəncərəsini və ya yoxlanmış admin bölməsini açır; öz-özünə hesabı dəyişmir. Uğurlu nəticə giriş ünvanını göstərir. Mövcud parol istifadə olunur.

Hesab dəyişikliyi istifadəçinin açıq admin sessiyasını tələb edir. Qoşulmuş MCP alətlərində Auth Admin istifadəçi-yeniləmə əməliyyatı yoxdur. İdarə olunan `auth.users` və `auth.identities` cədvəllərinə birbaşa dəyişiklik edilməyib. Köməkçi funksiya e-poçtu yalnız istifadəçinin düyməyə basmasından sonra standart Auth Admin API-si ilə yeniləyir.

Server: `supabase/functions/ca-admin-email-change/{index.ts,handler.mjs}`. Funksiya `verify_jwt: true` ilə yayımlanıb. POST yalnız boş JSON obyektini qəbul edir:

1. Bearer tokeni Auth `/user` vasitəsilə yoxlanır və istifadəçi ID-si oradan alınır.
2. Eyni istifadəçinin tokeni ilə `cenub_admin_yoxla` nəticəsi tam `true` olmalıdır.
3. Yalnız bundan sonra serverin məxfi xidmət açarı oxunur və standart `PUT /auth/v1/admin/users/{id}` əməliyyatına yalnız `{email:'azavto44@gmail.com'}` göndərilir.

İstifadəçi başqa hesab ID-si, ünvan, parol və ya metadata ötürə bilməz. Artıq bu ünvandan istifadə edən admin üçün əməliyyat yenidən hesabı yazmadan uğur qaytarır. Xidmət açarı, tokenlər və provayderin daxili xətaları cavaba daxil edilmir. Anonim/yanlış token, qeyri-admin, başqa origin, yanlış üsul və həddən artıq və ya əlavə sahəli sorğu rədd edilir. Gözləmə müddəti məhduddur.

UUID, profil/elan əlaqələri və admin üzvlüyü dəyişdirilmir; parol atributu API sorğusunda yoxdur. Brauzer yalnız gözlənilən hesab ID-si, ünvan və status qayıtdıqda uğur göstərir; gecikmiş başqa sessiya cavabları istifadə edilmir. Şəbəkə xətası təkrar sınana bilər. SMTP göndərən hesabı bu dəstək/admin giriş dəyişikliyindən ayrı konfiqurasiyadır.

## Yoxlama

- Canlı bazadan yeni admin ünvanı, eyni hesab UUID-si, profil və admin üzvlüyü təsdiqlənib; istifadəçi yeni ünvanla girişini təsdiqləyib. Hesab identifikatoru və məxfi sessiya məlumatları sənəddə saxlanılmır.
- 124 Node yoxlaması keçib: əvvəlki 111 və 13 yeni server təhlükəsizlik ssenarisi. Auth və admin yoxlamaları bitmədən xidmət açarının oxunmadığı və yazmanın başlamadığı ayrıca yoxlanıb.
- 40 brauzer sınağı keçib: 13 yeni admin Gmaili və 27 mövcud giriş/admin pəncərəsi ssenarisi.
- Altı səhifə və qaydalar pəncərəsində 5 e-poçt keçidi yeni ünvandır; 5 telefon keçidi saxlanılıb.
- Canlı Edge Function üçün girişsiz preflight `204`, tokensiz və yanlış tokenli POST sorğuları `401` qaytarıb. Bu yoxlamalarda hesab yenilənməsi yoxdur.
- Avtomatik brauzer sınaqlarında bütün şəbəkə cavabları imitasiya edilir; real məktub, parol dəyişikliyi, elan və ödəniş yaradılmır.
