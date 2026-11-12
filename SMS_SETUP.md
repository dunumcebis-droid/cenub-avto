# Real SMS təsdiqinin aktivləşdirilməsi

Hazırda SMS xidməti hesabı yoxdur. Sayt kod göndərildiyini və ya nömrənin təsdiqləndiyini uydurmur. E-poçtla giriş və işləyən parol bərpası saxlanılır.

Telefon təsdiqi şəxsi kabinetdə hazırlanıb. Supabase telefon girişi aktiv olduqda istifadəçi nömrəsini yazır, provayder həmin nömrəyə kod göndərir və Supabase kodu yoxlayır. Təsdiq nişanı yalnız cari hesabın serverdən alınmış `phone` və `phone_confirmed_at` məlumatlarına əsaslanır. Dəyişdirilə bilən profil məlumatı təsdiq sübutu deyil. Kodun təsdiqi başqa hesabın sessiyasını quraşdırmır.

Aktivləşdirmək üçün:

1. Azərbaycan nömrələrinə SMS göndərişini dəstəkləyən Supabase SMS provayderində hesab və göndəriş icazəsi açılmalıdır.
2. Supabase layihəsinin Authentication → Sign In / Providers → Phone bölməsində provayderin girişləri yalnız məxfi ayarlara daxil edilir. Açarlar söhbətə, sayt koduna və GitHub-a yazılmır.
3. Real göndəriş qiyməti, Azərbaycan nömrələrinə çatdırılma, göndərən adı və limitlər provayderlə dəqiqləşdirilir.
4. Ayrı icazəli real sınaqda kodun çatması və şəxsi kabinetdə həmin hesabın nömrəsinin təsdiqlənməsi yoxlanır. Qaydalar və məxfilik səhifələrində SMS-in cari statusu yenilənir.

Bu dəyişiklikdə provayder açılmayıb, ödənişli plan alınmayıb və heç bir real SMS göndərilməyib. İstinad: https://supabase.com/docs/guides/auth/phone-login
