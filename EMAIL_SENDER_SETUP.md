# Bərpa məktubunun göndərən ünvanı

İstənilən göndərən: **AvtoUnvan <avtounvan@gmail.com>**. Saytdakı dəstək ünvanı da budur. **Cari vəziyyət:** istifadəçi bu Gmail üçün tətbiq parolunu yaratdığını və yeni SMTP sahələrini Supabase panelində saxladığını bildirib. Yeni göndərənin real bərpa məktubunda görünməsi hələ ayrıca təsdiqlənməyib. HTML-də e-poçtu dəyişmək Supabase Auth-un `From` sahəsini dəyişmir.

Hazırkı işlək parol bərpası kodu saxlanılıb. İstifadəçilərin giriş ünvanları və bərpa məktubunun alıcısı dəstək/göndərən ünvanından ayrıdır. Adminin öz giriş ünvanı ayrıca qorunan əməliyyatla yenilənir; [ADMIN_EMAIL_CHANGE.md](ADMIN_EMAIL_CHANGE.md).

## Yeni Gmail üçün hazır SMTP sahələri

[Supabase SMTP ayarları](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/smtp):

| Sahə | İstənilən dəyər |
| --- | --- |
| Custom SMTP | Bütün sahələr hazır olanda aktiv |
| Sender email | `avtounvan@gmail.com` |
| Sender name | `AvtoUnvan` |
| Host | `smtp.gmail.com` |
| Port | `465` (TLS) |
| Username | `avtounvan@gmail.com` |
| Password | Yeni Gmail hesabına məxsus Google App Password; yalnız Supabase-in məxfi sahəsində |

Google-da əvvəl **avtounvan@gmail.com** hesabını seçin. İki addımlı doğrulama aktiv olduqdan sonra [tətbiq parolu yaradın](https://myaccount.google.com/apppasswords). Adi Gmail parolu işlədilmir. Köhnə göndərənin tətbiq parolu yeni Gmailə aid deyil. Tətbiq parolunu söhbətə, HTML-ə, repozitoriyaya və ya ekran şəklinə göndərməyin; onu birbaşa Supabase Password sahəsinə daxil edib ayarları birlikdə saxlayın.

SMTP dəyişdirilməsi üçün qoşulmuş Supabase alətində Auth konfiqurasiya-yeniləmə funksiyası yoxdur və yeni Gmailin məxfi tətbiq parolu icra mühitinə verilməyib. Bu son sahə hesab sahibinin panelində doldurulur. Custom SMTP üçün Supabase Pro tələb olunmur; pulsuz paket saxlanılır.

## Bərpa səhifəsinə yönləndirmə

Sayt hələ **https://dunumcebis-droid.github.io/cenub-avto/** ünvanındadır. Domen və hostinq alınmayıb. [URL Configuration](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/url-configuration) içində `Site URL` bu əsas ünvan olmalıdır; ayrıca bərpa səhifəsi **https://dunumcebis-droid.github.io/cenub-avto/reset-password.html**-dır. Yeni brend adına əsasən alınmamış domenə yönləndirmə yaradılmır.

## Tamamlanmanı yoxlamaq

Ayarlar saxlandıqdan sonra istifadəçi öz hesabı üçün bir bərpa məktubu istəyə bilər. `From` sahəsi **AvtoUnvan <avtounvan@gmail.com>** olmalı, keçid **Yeni parol yarat** ekranını açmalıdır. Məxfi keçid və parol paylaşılmır. Yeni göndərənin çatdırılması real məktubla hələ yoxlanılmayıb; avtomatik sınaqlar məktub göndərişini imitasiya edir.

Rəsmi mənbələr: [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [Google SMTP ilə Supabase](https://supabase.com/kb/troubleshooting/using-google-smtp-with-supabase-custom-smtp-ZZzU4Y), [Google App Password](https://support.google.com/accounts/answer/185833?hl=en).
