# Bərpa məktubunun göndərən ünvanı

İstənilən göndərən: **Cənub Avto <cenubavtoelan@gmail.com>**. Saytdakı dəstək ünvanı bu ünvandır. Məktubun faktiki `From` sahəsi isə Supabase Auth-un SMTP konfiqurasiyasından gəlir; HTML-də ünvan yazmaq onu dəyişmir.

Bu mərhələdə SMTP göndərəninin dəyişdirilməsi **tamamlanmayıb**. Mövcud Supabase alətlərində Auth/SMTP ayarlarını dəyişmək funksiyası yoxdur; icra mühitinə Gmail SMTP və ya Supabase Management API girişi verilməyib. İşləyən parol bərpası saxlanılıb, istifadəçilərin giriş ünvanları və bərpa məktubunun alıcısı dəyişdirilməyib. Heç bir e-poçt göndərilməyib.

## Hazır konfiqurasiya

[Layihənin SMTP səhifəsi](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/smtp):

| Sahə | Dəyər |
| --- | --- |
| Custom SMTP | Aktiv |
| Sender email | `cenubavtoelan@gmail.com` |
| Sender name | `Cənub Avto` |
| Host | `smtp.gmail.com` |
| Port | `587` (STARTTLS); alternativ `465` (TLS) |
| Username | `cenubavtoelan@gmail.com` |
| Password | Google App Password — birbaşa Supabase-in məxfi sahəsinə daxil edilir |

Gmail hesabında iki mərhələli doğrulama aktiv olduqdan sonra [Google App Password](https://myaccount.google.com/apppasswords) yaradılır. Adi Gmail parolu və tətbiq parolu söhbətə, repozitoriyaya və ya frontend koduna yazılmamalıdır. SMTP yalnız bütün sahələr hazır olanda aktivləşdirilməlidir; yarımçıq konfiqurasiya məktub göndərişini poza bilər. Custom SMTP üçün Supabase Pro planı tələb olunmur.

Quraşdırmadan sonra göndərən adı/ünvanı yenidən oxunmalı, sahibinin ayrıca icazəsi ilə bir sınaq məktubu göndərilməli, məktubun `From` ünvanı, çatdırılması və bərpa ekranının açılması yoxlanmalıdır. Bərpa linkləri və parollar hesabatlara daxil edilməməlidir.

Rəsmi mənbələr: [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [Google SMTP ilə Supabase](https://supabase.com/kb/troubleshooting/using-google-smtp-with-supabase-custom-smtp-ZZzU4Y), [Google App Password](https://support.google.com/accounts/answer/185833?hl=en).
