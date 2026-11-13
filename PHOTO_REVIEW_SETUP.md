# Şəkillərin avtomatik yoxlanması

**Avtomatik tanıma hazırda aktiv deyil.** Şəkil tanıma xidməti üçün API hesabı və gizli açar qoşulmayıb. Bu mərhələdə hazırlanan proqram sınaqları imitasiya edilmiş xidmət cavablarından istifadə edir; modelin real şəkillərdə dəqiqliyi hələ təsdiqlənməyib. Mövcud elanlar admin yoxlamasında qalır.

## Qoşulma

1. [Google AI Studio](https://aistudio.google.com/) və ya [OpenAI API](https://platform.openai.com/) hesabında şəkilləri qəbul edən modelə giriş yaradın. Provayderin qiymətini, hesab limitini və xərcləmə xəbərdarlığını əvvəlcədən təyin edin. API istifadəsi ayrıca ödəniş yarada bilər.
2. [Supabase → Edge Functions → Secrets](https://supabase.com/dashboard/project/iqdtehqxusfiwokrzceo/functions/secrets) bölməsinə aşağıdakı dəyərləri əlavə edin. **Gizli açarı söhbətə, saytın JavaScript faylına və ya GitHub-a yazmayın.**

| Dəyişən | Google Gemini | OpenAI |
| --- | --- | --- |
| `PHOTO_REVIEW_PROVIDER` | `gemini` | `openai` |
| `PHOTO_REVIEW_MODEL` | Hesabda işləyən, şəkil və strukturlaşdırılmış JSON cavabını dəstəkləyən modelin tam ID-si | Hesabda işləyən, şəkil və strukturlaşdırılmış JSON cavabını dəstəkləyən modelin tam ID-si |
| API açarı | `GEMINI_API_KEY` | `OPENAI_API_KEY` |

İcazəli sayt ünvanları `https://dunumcebis-droid.github.io`, `https://cenubavto.az` və `https://www.cenubavto.az`-dır. Yerli inkişaf və ya başqa host üçün `PHOTO_REVIEW_ALLOWED_ORIGINS` dəyişənində icazəli origin-lər vergüllə ayrılaraq verilir. Bu dəyişən veriləndə siyahını bütöv göstərmək lazımdır.

Model ID-si açıq şəkildə verilməlidir; açarın təkcə əlavə edilməsi funksiyanı hazır etmir. `SUPABASE_URL`, `SUPABASE_ANON_KEY` və `SUPABASE_SERVICE_ROLE_KEY` server mühitində qalır, brauzerə ötürülmür.

3. `ca-photo-review` Edge Function-ın server konfiqurasiyası yoxlanır. Hesaba daxil olmuş istifadəçinin `/functions/v1/ca-photo-review/status` sorğusunda `configured: true` görünməsi yalnız konfiqurasiyanın mövcudluğunu bildirir; modelin uğurla şəkil tanıdığını sübut etmir.
4. Nəzarətli sınaqda real ön, arxa, yan, salon, mühərrik və detal fotoları, yanlış bölməyə qoyulmuş fotolar, ekran görüntüləri və avtomobilə aid olmayan şəkillər yoxlanır. Şübhəli görünüşlər üçün də nəticə qiymətləndirilir.
5. Bu sınaqdan sonra avtomatik yoxlama bazadakı xidmət bayrağı ilə ayrıca aktivləşdirilir. Bayraq indiki mərhələdə sönülüdür; aktivləşdirmə kod/baza üzrə işi aparan şəxs tərəfindən edilir. Hazırlıq tamamlanmadan bayrağı açmaq yeni şəkillərin göndərilməsini dayandıra bilər.

## Aktiv olanda davranış

Hər yeni şəkil seçilən bölmə ilə uyğun olmalıdır: ön, arxa, yan, salon, mühərrik və ya avtomobilə aid digər detal. Aydın görünən ekran interfeysi, əlaqəsiz şəkil, uyğunsuz bölmə və qeyri-müəyyən nəticə xəbərdarlıqla rədd edilir. Xidmətin xətası və ya limitə çatması təsdiq kimi qəbul edilmir.

Server əvvəlcə istifadəçinin girişini yoxlayır, sonra şəkli qiymətləndirir. Qəbul edilən şəkil server tərəfindən `checked` yoluna yazılır; təsdiq hesab, bölmə, saxlanılan yol və faylın SHA-256 izi ilə əlaqələndirilir. Müştəri bu yoldakı şəkli əvəz edə bilmir. Aktiv baza yoxlaması yeni şəkillərin təsdiqsiz elan məlumatına əlavə edilməsini də bloklamaq üçün nəzərdə tutulub. Əvvəlki şəkillər öz elan və bölməsində qorunur.

Yoxlama görsənən məzmunu qiymətləndirir: ekran hissələri kəsilib yalnız avtomobil qalıbsa, şəklin ekran görüntüsündən gəldiyini hər dəfə müəyyən etmək mümkün deyil. Son yayım üzrə admin yoxlaması saxlanılır.

## Kod

- Server: `supabase/functions/ca-photo-review/handler.mjs`
- Giriş nöqtəsi: `supabase/functions/ca-photo-review/index.ts`
- Brauzer: `assets/js/18-photo-review.js`
- Server sınaqları: `tests/photo-review-server.test.cjs`
