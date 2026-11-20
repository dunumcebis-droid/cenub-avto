# Bərpa məktubunun göndərən ünvanı

Cari göndərən: **AvtoUnvan <avtounvan@gmail.com>**. Saytdakı dəstək ünvanı da budur. **Cari vəziyyət:** istifadəçi bu Gmail üçün tətbiq parolunu yaratdığını və yeni SMTP sahələrini Supabase panelində saxladığını bildirib. İstifadəçi öz bərpa sınağında məktubun gəldiyini və göndərənin **AvtoUnvan <avtounvan@gmail.com>** olduğunu təsdiqləyib. HTML-də e-poçtu dəyişmək Supabase Auth-un `From` sahəsini dəyişmir.

Hazırkı işlək parol bərpası kodu saxlanılıb. İstifadəçilərin giriş ünvanları və bərpa məktubunun alıcısı dəstək/göndərən ünvanından ayrıdır. Adminin öz giriş ünvanı ayrıca qorunan əməliyyatla yenilənir; [ADMIN_EMAIL_CHANGE.md](ADMIN_EMAIL_CHANGE.md).

## İstifadəçinin saxladığı SMTP sahələri

[Supabase SMTP ayarları](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/smtp):

| Sahə | Dəyər |
| --- | --- |
| Custom SMTP | Aktiv |
| Sender email | `avtounvan@gmail.com` |
| Sender name | `AvtoUnvan` |
| Host | `smtp.gmail.com` |
| Port | `465` (TLS) |
| Username | `avtounvan@gmail.com` |
| Password | Yeni Gmail hesabına məxsus Google App Password; yalnız Supabase-in məxfi sahəsində |

Google-da əvvəl **avtounvan@gmail.com** hesabını seçin. İki addımlı doğrulama aktiv olduqdan sonra [tətbiq parolu yaradın](https://myaccount.google.com/apppasswords). Adi Gmail parolu işlədilmir. Köhnə göndərənin tətbiq parolu yeni Gmailə aid deyil. Tətbiq parolunu söhbətə, HTML-ə, repozitoriyaya və ya ekran şəklinə göndərməyin; onu birbaşa Supabase Password sahəsinə daxil edib ayarları birlikdə saxlayın.

SMTP dəyişdirilməsi üçün qoşulmuş Supabase alətində Auth konfiqurasiya-yeniləmə funksiyası yoxdur və yeni Gmailin məxfi tətbiq parolu icra mühitinə verilməyib. Bu son sahə hesab sahibinin panelində doldurulur. Custom SMTP üçün Supabase Pro tələb olunmur; pulsuz paket saxlanılır.

## Bərpa səhifəsinə yönləndirmə

Əsas sayt **https://avtounvan.vip/**, ayrıca bərpa səhifəsi **https://avtounvan.vip/reset-password.html**-dır. İstifadəçi [URL Configuration](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/auth/url-configuration) içində `Site URL` sahəsini bu əsas ünvanla saxlayıb. Ekran şəklində dörd `Redirect URL` təsdiqlənib: əsas və `www` hostlarının hər ikisi üçün `/` və `/reset-password.html`. Formalar açıldıqları domenin bərpa səhifəsinə yönləndirir. Əvvəlki GitHub Pages yayımı əlavə ünvan olaraq qalır; əsas domenin SMTP göndərəni `avtounvan@gmail.com`-dur.

## Tamamlanmanı yoxlamaq

`From` sahəsi **AvtoUnvan <avtounvan@gmail.com>** olmalı, yeni məktubun keçidi **Yeni parol yarat** ekranını açmalıdır. Yeni göndərən və məktubun çatması istifadəçinin əvvəlki real bərpa sınağı ilə təsdiqlənib. **20 noyabr 2026:** yeni domenin dörd yönləndirmə ünvanı saxlandıqdan sonra istifadəçiyə `https://avtounvan.vip/reset-password.html` səhifəsindən təzə məktub istəmək və ən yeni keçidi açmaq tapşırılıb; istifadəçi parolunu uğurla dəyişdirdiyini bildirib. Məxfi keçid və parol alınmayıb. Avtomatik sınaqlar real məktub göndərmir və parol dəyişdirmir; bu real əməliyyatı hesab sahibi yerinə yetirib.

Rəsmi mənbələr: [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [Google SMTP ilə Supabase](https://supabase.com/kb/troubleshooting/using-google-smtp-with-supabase-custom-smtp-ZZzU4Y), [Google App Password](https://support.google.com/accounts/answer/185833?hl=en).
