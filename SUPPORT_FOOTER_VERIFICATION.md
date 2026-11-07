# Dəstək və alt hissənin görünüşü — 7 noyabr 2026

Sayta «Dəstək xidməti ilə əlaqə» bölməsi əlavə edilib. Telefon `0709091997` (`tel:+994709091997`), e-poçt `cenubavtoelan@gmail.com` (`mailto:`) keçidləridir. Footer-də həmin bölməyə keçid var.

«© 2026 Cənub Avto · Al. Sat. Tap.» yazısının rəngi aydınlaşdırılıb. Admin düyməsi müqayisə/ehtiyat nüsxə/qaydalar düymələri ilə eyni alət panelinə yerləşdirilib. Panel sətrlərə bölünür və hündürlüyü dəyişəndə səhifənin altında uyğun yer ayrılır. Ekranın təhlükəsiz alt sahəsi də nəzərə alınır; footer və düymələr bir-birini örtmür. Admin düyməsinin serverdə doğrulanan görünürlük şərti saxlanılıb.

Şəkillərə, VIP paketlərinə, elanlara və Auth ayarlarına dəyişiklik edilməyib. Parol bərpası göndərəninin yeni Gmail ünvanına keçirilməsi SMTP autentifikasiyasını gözləyir; bu hissə tamamlanmış sayılmır. Dəqiq hazırlıq və quraşdırma sahələri: [EMAIL_SENDER_SETUP.md](EMAIL_SENDER_SETUP.md). İstifadəçilərin giriş e-poçtları və bərpa məktubunun alıcısı dəyişdirilməyib.

## Yerli yoxlama

| Dəst | Nəticə |
| --- | --- |
| Node: mövcud məlumat, sessiya, şəkil eyniliyi yoxlamaları | 58/58 |
| Mövcud admin/parol bərpası brauzer sınaqları | 16/16; 23,462 saniyə |
| Mövcud müqayisə brauzer sınaqları | 8/8; 11,406 saniyə |
| Mövcud paket/bildiriş brauzer sınaqları | 11/11; 22,796 saniyə |
| Qonaq, admin və çıxışdan sonrakı görünüşlər | 21/21 |
| JavaScript sintaksisi və diff formatı | 10 fayl; təmiz |

Görünüşlər 320, 360, 375, 390, 430, 768 və 1440 px enlərdə yoxlanıb. Footer yazısı görünür, düymələr üst-üstə düşmür, səhifə üfüqi daşmır. Hesabdan çıxanda panel üçün ayrılan sahə yenidən uyğunlaşır. Telefon/e-poçt ünvanları və footer keçidi yoxlanıb. Brauzer API-ləri saxtadır; real təsdiq, elan yazısı, zəng və e-poçt göndərişi yoxdur.

Hesabatlar: [frontend](tests/reports/support-footer-frontend.json), [21 görünüş](tests/reports/support-footer-layouts.json).

## Canlı yoxlama

- Tətbiq commit-i: [8e44f65](https://github.com/dunumcebis-droid/cenub-avto/commit/8e44f65659c020ea0898aab57897d47d0f9f4fe5). [Pages yayımı 42396095671](https://github.com/dunumcebis-droid/cenub-avto/actions/runs/42396095671) uğurla bitib.
- Telefon və e-poçt keçidləri, footer-dən dəstək bölməsinə keçid canlı səhifədə yoxlanıb. Heç bir zəng və məktub göndərilməyib.
- 320, 375, 430, 768 və 1440 px enlərdə footer-in tamamı alət panelindən yuxarı görünür; düymələr bir-birini örtmür və üfüqi daşma yoxdur. 375 px ekran görüntüsünə ayrıca baxılıb. Qonaq üçün admin düyməsi gizlidir. Adminin responsive vəziyyətləri saxta API cavabları ilə yuxarıdakı 21 görünüşdə yoxlanıb.
- Canlı serverdən həmin anda oxunan **3 aktiv elan və 2 VIP** 1440/375/320 px görünüşlərdə kartlar, məlumatlar və yüklənmiş foto URL-ləri ilə tutuşdurulub. Detallar, qalereya, əlaqə linkləri, filtr/sıfırlama, BMW seçimi və müqayisə yenilənməsi keçib. Açıq cavabda gözləyən elan və daxili qeyd yoxdur.
- Yayımlanmış bərpa ekranı, saxta etibarsız tokenin Auth tərəfindən rəddi, URL təmizlənməsi və saytın bildiriş pəncərəsi də işləyir. Yeni bərpa məktubu göndərilməyib, parol və SMTP ayarı dəyişdirilməyib.
- Bütün **59 statik fayl**, o cümlədən **46 dəyişdirilməmiş şəkil**, yoxlanmış tətbiq commit-i ilə bayt səviyyəsində eynidir. JavaScript xətası və gözlənilməz yazı cəhdi yoxdur.
- Hesabatlar: [canlı brauzer/API](tests/reports/support-footer-live.json), [bütün statik fayllar](tests/reports/support-footer-static-live.json). Sonrakı hesabat commit-i tətbiq fayllarını dəyişmir.

Sayt başqa telefondan da açıqdır: https://dunumcebis-droid.github.io/cenub-avto/ . Elanlara baxmaq üçün giriş tələb olunmur; şəxsi kabinet və admin əməliyyatları müvafiq hesaba bağlıdır.
