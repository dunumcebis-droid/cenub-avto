# Şəkil yoxlamasının sürəti

Çox şəkil seçiləndə hər şəkil üçün ayrıca sorğu və dörd işçi uzun ardıcıl növbə yaradırdı. Tək sorğunun normal emal müddəti bir neçə saniyə olsa belə, 36 şəkil doqquz ardıcıl dövr tələb edirdi. Vaxtı bitən xarici sorğu da növbəni saxlayırdı.

Yeni axın 6-lıq qruplarla, iki paralel sorğu ilə işləyir. Bütün görüntülər ayrı göndərilir və ayrıca nəticə/təsdiq alır. Qəbul edilmiş faylın hesab, bölmə və bayt izi uyğun gələndə əvvəlki nəticə istifadə olunur. Hazırlanmış faylların keşi və iki dekoder həddi təkrar işin və telefon yaddaşı yükünün qarşısını alır. Ekran görüntüsü, yanlış bölmə, əlaqəsiz şəkil və qeyri-müəyyən nəticə qaydaları qüvvədədir.

Yoxlama: **100 Node və 178 Chromium brauzer sınağı** keçib. Bunlara 40 server yoxlaması, 27 şəkil interfeysi sınağı və 4 toplu yükləmə/keş sınağı daxildir.

Yoxlama sübutları:

- 12 şəkil: 2 paralel qrup sorğusu; 12 ayrı sorğu getmir.
- Qismən rədd: 6 fayldan 5 təsdiq saxlanır, təkrar cəhddə yalnız 1 fayl göndərilir.
- Şəbəkə xətası: JPEG-lər yenidən dekodlaşdırılmır; təsdiqsiz URL yaranmır.
- Eyni şəkli yenidən seçmək: həmin bölmədə əlavə model sorğusu yoxdur; bölmə dəyişəndə yenidən yoxlanır.
- Server: 6 ayrı görüntüyə bir model çağırışı, ciddi indeks/say yoxlaması, ayrıca təsdiq/iz, ölçü və vaxt hədləri.

Proqram sınaqları real şəbəkəyə yazmır. Gecikmənin faktiki azalması şəkil sayı, telefon, şəbəkə və provayderin yükündən asılıdır; nəticə sübutsuz sabit saniyə rəqəmi ilə təqdim edilmir.
