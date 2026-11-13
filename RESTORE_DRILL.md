# Elan və şəkillərin bərpa sınağı

13 noyabr 2026 tarixində mövcud admin ixracından götürülən həqiqi tətbiq məlumatları ayrıca yerli PostgreSQL mühitinə bərpa edilib. Canlı bazaya məlumat yazılmayıb və elan yayımlanmayıb.

- 12 məlumat mənbəyi, 266 sətir: 10 elan, 5 paket sorğusu, 2 profil, 1 admin qeydi, 247 Storage obyekti və 1 bildiriş irəliləyiş qeydi.
- 247 şəklin orijinal baytları və saxlanma yolları bərpa edilib: 31 047 805 bayt.
- Saytın dəyişdirilməmiş `14-server-backup.js` kodu 31 546 377 baytlıq ZIP yaradıb. Brauzerdə 3 manifest, 8 səhifə və 247 foto oxuması əvvəlcədən götürülmüş nüsxələrlə cavablandırılıb; brauzer istehsal bazasına daxil olmayıb.
- CRC, fayl SHA-256, manifest, sətir sayı və şəkil uyğunluğu yoxlanıb. Bərpa edilmiş 12 mənbənin PostgreSQL-də hesablanan bütün sətir heşləri ilkin server manifesti ilə eynidir.
- 44 məhdudiyyət, o cümlədən 16 xarici açar təsdiqlənib. Növbənin identity sayğacı saxlanılan elan hadisələri və bildiriş/axtarış göstəricilərindən yuxarı qurulur.
- Sonradan canlı manifest təkrar oxunub: bütün mənbələrdə sətir sayı və heşlər ilkin nüsxə ilə eyni qalıb.

[Şəxsi sətirlərsiz nəticə hesabatı](docs/restore/restore-drill-result.json).

## Əhatə

Bu, tətbiq məlumatları və şəkillərin bərpası sınağıdır. Supabase Auth parolları, sessiyalar, SMTP/Edge Function sirləri, platforma ayarları, bütün funksiyalar və RLS siyasətləri bu ZIP-in hissəsi deyil. Yerli xarici açar yoxlaması üçün 2 boş Auth identifikatoru yaradılıb; hesabların girişi bərpa edilməyib. Yerli mühərrik PGlite 0.5.16 / PostgreSQL 18.6-dır.

Tam Supabase bərpası üçün ayrıca platforma/baza nüsxəsi, sxem miqrasiyaları və server ayarları da lazımdır. [Supabase bərpa sənədi](https://supabase.com/docs/guides/platform/backups) qeyd edir ki, baza nüsxəsi Storage fayllarının baytlarını saxlamır; şəkillər ayrıca qorunmalıdır. Tətbiq ZIP-i bu faylları daxil edir. Bu sınaq avtomatik bərpa və ya avtomatik ehtiyat nüsxə xidməti quraşdırmır.

## Təkrar sınaq

`tools/restore_drill.py` yalnız yerli çıxış qovluğu qəbul edir; canlı baza ünvanına bərpa əmri yoxdur. Yeni boş `0700` qovluğu istifadə edilir, mövcud fayllar əvəz edilmir. Şəxsi JSON, ZIP və şəkillər Git repozitoriyasından kənarda, `0600` fayl icazəsi ilə saxlanılır.

1. Pinned yerli asılılığı qurun: `npm ci --prefix tools/restore-drill`. Python Playwright və Chromium da tələb olunur.
2. Mövcud admin ixracının manifest/səhifələrini bir `REPEATABLE READ READ ONLY` tranzaksiyasında götürün; hər səhifə 100 sətirdir. Sxem metadatası ayrıca saxlanılır. Çıxışda şəxsi sətirlər var: onları söhbətə və GitHub-a əlavə etməyin.
3. Mövcud ZIP-dən yerli bərpa sınağını başladın:

```sh
python3 tools/restore_drill.py \
  --archive /private/application-backup.zip \
  --snapshot /private/snapshot.json \
  --schema /private/schema.json \
  --work-dir /private/new-empty-drill \
  --pglite-module tools/restore-drill/node_modules/@electric-sql/pglite
```

`--archive` verilməzsə, alət saxlanılan manifest/səhifələrdən saytın ZIP kodunu işlədir. Çatışmayan şəkilləri yalnız sabit layihənin ictimai Storage ünvanından 4 paralel GET ilə götürür. Kvota və vaxt hədləri tətbiq olunur; təsadüfi URL və başqa baza əməliyyatı qəbul edilmir. Şəkil artıq özəl keşdədirsə, ölçüsü yenidən yoxlanır və təkrar yüklənmir.

Snapshot formatı: `manifest` mövcud admin manifestidir, `resources.<ad>.pages` isə `items`, `hashes` və `next_cursor` saxlayan dəqiq səhifə cavablarıdır. Sxem faylındakı `tables` siyahısı hər mənbənin sxem/cədvəl adını, sütun tiplərini, null/default/identity/generated məlumatını və PK/unique/check/FK məhdudiyyətlərini saxlayır. Sxem yalnız etibarlı öz baza metadatasından götürülməlidir.

Yoxlamalar:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_restore_drill.py' -v
node --test tests/restore-drill-pg.test.cjs
```

18 arxiv yoxlaması zədələnmiş fayl, natamam/yad mənbə, uyğunsuz heş, təkrar yol, keçid və böyük sıxılmış arxivi rədd edir. 4 ayrıca PostgreSQL sınağı boş/dolu hadisə növbəsini, saxlanılan göstəriciləri və identity daşmasını yoxlayır. Bunlar saxta məlumatlarla yerli işləyir.
