# Bərpa məktubunun göndərən ünvanı

Cari göndərən: **AzAvto <azavto44@gmail.com>**. Saytdakı cari dəstək ünvanı da bu ünvandır. **19 noyabr 2026 vəziyyəti:** yeni Gmail SMTP ayarları Supabase-də saxlanılıb; real bərpa məktubunun çatması və `From` sahəsində `AzAvto <azavto44@gmail.com>` görünməsi istifadəçi tərəfindən təsdiqlənib. Məktubun `From` sahəsi Supabase Auth-un SMTP konfiqurasiyasından gəlir; HTML-də ünvan yazmaq onu dəyişmir.

SMTP tətbiq parolu yalnız Supabase-in məxfi ayarında saxlanılıb; söhbətə və repozitoriyaya yazılmayıb. İstifadəçilərin hesab ünvanları və bərpa məktublarının alıcısı bu göndərən ünvanından ayrıdır.

## Sayta yönləndirmə

[Supabase URL Configuration](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/url-configuration) bölməsində `Site URL` ünvanı `https://dunumcebis-droid.github.io/cenub-avto/` olmalıdır. Bərpa sorğusu `https://dunumcebis-droid.github.io/cenub-avto/reset-password.html` ünvanını istifadə edir. Bu ayrıca səhifə birbaşa parol bərpasını göstərir. Əvvəlki bərpa keçidləri ana səhifədə də işlənir. Eyni scheme/host/port Supabase tərəfindən qəbul edilir; əlavə callback ünvanları ayrıca `Redirect URLs` siyahısında saxlanıla bilər.

`Site URL` ümumi sayt ünvanıdır; ona bərpa işarəsi əlavə edilmir. SMTP göndərənindən əlavə, yönləndirmə ünvanı da düzgün qurulmalıdır.

## Cari SMTP ayarları

[Layihənin SMTP səhifəsi](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/smtp):

| Sahə | Dəyər |
| --- | --- |
| Custom SMTP | Aktiv |
| Sender email | `azavto44@gmail.com` |
| Sender name | `AzAvto` |
| Host | `smtp.gmail.com` |
| Port | `465` (TLS) |
| Username | `azavto44@gmail.com` |
| Password | Gmail hesabının Google App Password-u — yalnız Supabase-in məxfi sahəsində saxlanılır |

Gmail hesabında iki mərhələli doğrulama aktiv olduqdan sonra [Google App Password](https://myaccount.google.com/apppasswords) yaradılır. Adi Gmail parolu və tətbiq parolu söhbətə, repozitoriyaya və ya frontend koduna yazılmamalıdır. SMTP yalnız bütün sahələr hazır olanda aktivləşdirilməlidir; yarımçıq konfiqurasiya məktub göndərişini poza bilər. Custom SMTP üçün Supabase Pro planı tələb olunmur.

19 noyabr 2026-da bir real bərpa sorğusu `HTTP 200` qaytarıb; istifadəçi məktubun çatmasını və göndərəni təsdiqləyib. Bu yoxlama SMTP göndərənini və çatdırılmanı təsdiqləyir. Yeni məktubdakı keçidin açılması və parol dəyişikliyi bu yoxlamada təkrar aparılmayıb; əvvəlki bərpa axınının yoxlamaları ayrıca sənədləşdirilib. Məxfi bərpa linkləri, tokenlər və alıcının hesab məlumatları açıq repozitoriyada saxlanmamalıdır.

Rəsmi mənbələr: [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [Google SMTP ilə Supabase](https://supabase.com/kb/troubleshooting/using-google-smtp-with-supabase-custom-smtp-ZZzU4Y), [Google App Password](https://support.google.com/accounts/answer/185833?hl=en).
