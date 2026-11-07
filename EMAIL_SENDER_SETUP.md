# Bərpa məktubunun göndərən ünvanı

Göndərən: **Cənub Avto <cenubavtoelan@gmail.com>**. Saytdakı dəstək ünvanı da bu ünvandır. Məktubun `From` sahəsi Supabase Auth-un SMTP konfiqurasiyasından gəlir; HTML-də ünvan yazmaq onu dəyişmir.

SMTP parolu yalnız Supabase-in məxfi ayarında saxlanmalıdır. İstifadəçilərin hesab ünvanları və bərpa məktublarının alıcısı bu göndərən ünvanından ayrıdır.

## Sayta yönləndirmə

[Supabase URL Configuration](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/url-configuration) bölməsində `Site URL` ünvanı `https://dunumcebis-droid.github.io/cenub-avto/` olmalıdır. Bərpa sorğusu `https://dunumcebis-droid.github.io/cenub-avto/?auth=recovery` ünvanını istifadə edir. Bu işarə bərpa məqsədini səhifəyə bildirir. Eyni scheme/host/port Supabase tərəfindən qəbul edilir; əlavə callback ünvanları ayrıca `Redirect URLs` siyahısında saxlanıla bilər.

`Site URL` ümumi sayt ünvanıdır; ona bərpa işarəsi əlavə edilmir. SMTP göndərənindən əlavə, yönləndirmə ünvanı da düzgün qurulmalıdır.

## SMTP ayarları

[Layihənin SMTP səhifəsi](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/smtp):

| Sahə | Dəyər |
| --- | --- |
| Custom SMTP | Aktiv |
| Sender email | `cenubavtoelan@gmail.com` |
| Sender name | `Cənub Avto` |
| Host | `smtp.gmail.com` |
| Port | `465` (TLS); alternativ `587` (STARTTLS) |
| Username | `cenubavtoelan@gmail.com` |
| Password | Google App Password — yalnız Supabase-in məxfi sahəsinə daxil edilir |

Gmail hesabında iki mərhələli doğrulama aktiv olduqdan sonra [Google App Password](https://myaccount.google.com/apppasswords) yaradılır. Adi Gmail parolu və tətbiq parolu söhbətə, repozitoriyaya və ya frontend koduna yazılmamalıdır. SMTP yalnız bütün sahələr hazır olanda aktivləşdirilməlidir; yarımçıq konfiqurasiya məktub göndərişini poza bilər. Custom SMTP üçün Supabase Pro planı tələb olunmur.

Yoxlama zamanı faktiki göndərən ünvanı, çatdırılma və bərpa ekranının açılması təsdiqlənməlidir. Məxfi bərpa linkləri, tokenlər, alıcının hesab məlumatları və göndəriş qeydləri açıq repozitoriyada saxlanmamalıdır.

Rəsmi mənbələr: [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [Google SMTP ilə Supabase](https://supabase.com/kb/troubleshooting/using-google-smtp-with-supabase-custom-smtp-ZZzU4Y), [Google App Password](https://support.google.com/accounts/answer/185833?hl=en).
