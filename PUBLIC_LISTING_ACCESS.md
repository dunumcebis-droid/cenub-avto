# Açıq elan oxuma icazəsi

Tətbiq olunan Supabase miqrasiyası: `20261106154847_allow_public_listing_columns`.
Layihə: `iqdtehqxusfiwokrzceo`.

İstifadəçi təsdiqlənmiş və gələcəkdə təsdiqlənəcək elanların avtomobil məlumatlarının, şəkillərinin, əlaqə telefonlarının, əlavə forma məlumatlarının və VIP/paket məlumatlarının açıq oxunmasına konkret icazə verib.

## Dəyişiklik

`anon` rolu yalnız aşağıda göstərilən 28 sütunu oxuya bilər. Sayt eyni açıq sütun siyahısından istifadə edir. Daxili `paket_tesdiq_qeydi` sütunu oxuma icazəsinə daxil deyil.

Mövcud RLS qaydası ziyarətçilərə yalnız `veziyyet = 'aktiv'` olan elanları göstərir. Bu qayda, digər siyasətlər və daxil olmuş istifadəçilərin mövcud icazələri dəyişdirilməyib. Profillərə, admin və ödəniş sorğusu cədvəllərinə yeni icazə verilməyib. Elan qeydləri, şəkillər və VIP vəziyyətləri dəyişdirilməyib.

```sql
-- Preserve the existing active-only RLS policy and all authenticated permissions.
-- Internal package approval notes are intentionally excluded.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'elanlar' AND c.relrowsecurity
  ) THEN
    RAISE EXCEPTION 'Listing RLS must be enabled before granting public reads';
  END IF;
END $$;
GRANT SELECT (id,satici_id,marka,model,il,qiymet,yurus,seher,tesvir,veziyyet,yaradildi,neqliyyat_novu,nesil,ban_novu,yanacaq,suretler_qutusu,muherrik_hecmi,at_gucu,reng,bazar_ucun,oturacaq_sayi,techizat,sekiller,telefon,ca_data,paket_adi,paket_baslayir,paket_bitir) ON TABLE public.elanlar TO anon;
```

## Tətbiqdən sonra yoxlamalar

- Açıq REST sorğusu: HTTP 200; 2 aktiv elan; 0 gözləyən/rədd edilmiş elan.
- Daxili admin qeydinə açıq REST sorğusu: HTTP 401, giriş rədd edilir.
- 28 sütunda oxuma icazəsi var, daxili qeyddə yoxdur.
- Bütün 7 elanın əvvəl/sonra məlumat, şəkil və paket hash-ləri eynidir.
- Mövcud RLS siyasətləri, cədvəl icazələri və RLS konfiqurasiyası eynidir.
- Real API ilə yoxlanmış HTML: 2 real şəkil yüklənib, marka/model/qiymət/il/yürüş düzgündür; 1440/375 px görünüş, detallar və 1 VIP elan yoxlanıb.
- 14 Node testi, 7 brauzer testi və 8 JavaScript blokunun sintaksis yoxlaması keçib.

