# Şəkillərin avtomatik yoxlanması

**Real Gemini tanıması qoşulub və normal hesab girişi ilə yoxlanıb.** Açar Supabase Secrets-də qalır; brauzerə və repozitoriyaya alınmır. Standart model `gemini-3.5-flash-lite`-dır. Aktiv rejimi özəl baza konfiqurasiyası müəyyən edir: `enabled:true` bütün hesablar üçün yoxlamanı açır; `enabled:false, admin_preview:true` yalnız admin sınağıdır.

Yeni şəkillər ən çox 6 ayrıca görüntü ilə bir model sorğusunda yoxlanır. Brauzer iki qrup sorğusunu paralel göndərir; hər şəklin öz sahibi, bölməsi, SHA-256 izi, saxlanılan yolu və təsdiqi var. Eyni şəkil başqa bölməyə köçürüləndə yenidən yoxlanır.

## Qoşulma

1. [Google AI Studio](https://aistudio.google.com/) və ya [OpenAI API](https://platform.openai.com/) hesabında şəkilləri qəbul edən modelə giriş yaradın. Provayderin qiymətini, hesab limitini və xərcləmə xəbərdarlığını əvvəlcədən təyin edin. API istifadəsi ayrıca ödəniş yarada bilər.
2. [Supabase → Edge Functions → Secrets](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/functions/secrets) bölməsinə aşağıdakı dəyərləri əlavə edin. **Gizli açarı söhbətə, saytın JavaScript faylına və ya GitHub-a yazmayın.**

| Dəyişən | Google Gemini | OpenAI |
| --- | --- | --- |
| `PHOTO_REVIEW_PROVIDER` | `gemini` | `openai` |
| `PHOTO_REVIEW_MODEL` | İstəyə görə; verilməsə `gemini-3.5-flash-lite` işlənir | Hesabda işləyən, şəkil və strukturlaşdırılmış JSON cavabını dəstəkləyən modelin tam ID-si |
| API açarı | `GEMINI_API_KEY` | `OPENAI_API_KEY` |

İcazəli sayt ünvanları `https://dunumcebis-droid.github.io`, `https://cenubavto.az` və `https://www.cenubavto.az`-dır. Yerli inkişaf və ya başqa host üçün `PHOTO_REVIEW_ALLOWED_ORIGINS` dəyişənində icazəli origin-lər vergüllə ayrılaraq verilir. Bu dəyişən veriləndə siyahını bütöv göstərmək lazımdır.

Gemini standartı üçün `GEMINI_API_KEY` kifayətdir; `PHOTO_REVIEW_PROVIDER` verilməsə `gemini` seçilir. OpenAI üçün model ID-si ayrıca göstərilməlidir. Konfiqurasiyanın mövcudluğu uğurlu real tanıma nəticəsini əvəz etmir. `SUPABASE_URL`, `SUPABASE_ANON_KEY` və `SUPABASE_SERVICE_ROLE_KEY` server mühitində qalır, brauzerə ötürülmür.

3. `ca-photo-review` Edge Function-ın server konfiqurasiyası yoxlanır. Hesaba daxil olmuş istifadəçinin `/functions/v1/ca-photo-review/status` sorğusunda `configured: true` görünməsi yalnız konfiqurasiyanın mövcudluğunu bildirir; modelin uğurla şəkil tanıdığını sübut etmir.
4. Nəzarətli sınaqda real ön, arxa, yan, salon, mühərrik və detal fotoları, yanlış bölməyə qoyulmuş fotolar, ekran görüntüləri və avtomobilə aid olmayan şəkillər yoxlanır. Şübhəli görünüşlər üçün də nəticə qiymətləndirilir.
5. Bu sınaqdan sonra avtomatik yoxlama bazadakı xidmət bayrağı ilə ayrıca aktivləşdirilir. Admin sınağı `enabled:false, admin_preview:true`, ümumi rejim isə `enabled:true, admin_preview:false` ilə seçilir. Aktivləşdirmə kod/baza üzrə işi aparan şəxs tərəfindən edilir. Hazırlıq tamamlanmadan bayrağı açmaq yeni şəkillərin göndərilməsini dayandıra bilər.

## Aktiv olanda davranış

Hər yeni şəkil seçilən bölmə ilə uyğun olmalıdır: ön, arxa, yan, salon, mühərrik və ya avtomobilə aid digər detal. Aydın görünən ekran interfeysi, əlaqəsiz şəkil, uyğunsuz bölmə və qeyri-müəyyən nəticə xəbərdarlıqla rədd edilir. Xidmətin xətası və ya limitə çatması təsdiq kimi qəbul edilmir.

Server əvvəlcə istifadəçinin girişini yoxlayır, sonra şəkli qiymətləndirir. Qəbul edilən şəkil server tərəfindən `checked` yoluna yazılır; təsdiq hesab, bölmə, saxlanılan yol və faylın SHA-256 izi ilə əlaqələndirilir. Müştəri bu yoldakı şəkli əvəz edə bilmir. Aktiv baza yoxlaması yeni şəkillərin təsdiqsiz elan məlumatına əlavə edilməsini də bloklamaq üçün nəzərdə tutulub. Əvvəlki şəkillər öz elan və bölməsində qorunur.

Yoxlama görsənən məzmunu qiymətləndirir: ekran hissələri kəsilib yalnız avtomobil qalıbsa, şəklin ekran görüntüsündən gəldiyini hər dəfə müəyyən etmək mümkün deyil. Son yayım üzrə admin yoxlaması saxlanılır.

## Kod

- Server: `supabase/functions/ca-photo-review/handler.mjs`
- Giriş nöqtəsi: `supabase/functions/ca-photo-review/index.ts`
- Brauzer: `assets/js/18-photo-review.js`
- Server sınaqları: `tests/photo-review-server.test.cjs`

## Elan yaratmadan real sınaq

Saytda öz admin hesabınıza daxil olun, «Elan yerləşdir» bölməsində bir yeni şəkil seçin və **«Şəkilləri yoxla»** düyməsinə basın. Marka, model və qiyməti doldurmağa ehtiyac yoxdur. Bu düymə elan yaratmır və elanı yayımlamır. Uyğun şəkil serverdə yoxlanıb saxlanılır, nəticə formadadır; sonradan adi göndəriş həmin nəticəni təkrar model sorğusu olmadan istifadə edir.

Əvvəl düzgün ön foto, sonra eyni fotonu arxa bölmədə yoxlayın. Özündə şəxsi məlumat və açar olmayan avtomobil elanı ekran görüntüsü ilə mənfi sınaq aparıla bilər. Kvota/giriş xətası təsdiq sayılmır; fayllar formadan silinmir.

Cari model qaydaları: [Google model məlumatı](https://aistudio.google.com/docs/models/gemini-3.5-flash-lite), [miqrasiya izahı](https://aistudio.google.com/docs/whats-new-gemini-3.6#migrate-to-gemini-3-5-flash-lite).
