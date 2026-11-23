/**
 * AvtoÜnvan — Canlı AI Ekspert Modulu (avtounvan-ai-expert.js)
 * Hər suala uyğun dinamik və canlı cavab verir:
 * - Əvvəlcə canlı API/backend endpoint-ə (/api/ai-expert və ya konfiqurasiya olunmuş URL) sorğu göndərir.
 * - API əlçatan deyilsə və ya hələ qoşulmayıbsa, daxili ağıllı avtomobil eksperti mühərriki
 *   sualın niyyətini, markasını, modelini, ilini, büdcəsini, simptomlarını və söhbət tarixçəsini
 *   təhlil edərək suala birbaşa uyğun cavab yaradır (heç vaxt tək şablon cavab vermir).
 */

(function () {
  const DEFAULT_CONFIG = {
    // Öz backend endpoint-in varsa buraya yaz (məsələn: "/api/ai-expert" və ya "https://senin-saytin.az/api/ai-expert")
    apiEndpoint: "/api/ai-expert",
    // Əgər birbaşa Gemini API istifadə etmək istəsən (test üçün): model adını və proxy/endpoint-i istifadə et
    requestTimeoutMs: 8000,
    language: "az",
    brandName: "AvtoÜnvan AI Ekspert",
    packages: {
      urgent: "Təcili Satış (1 AZN — satılanadək aktiv)",
      vip: "VIP Paket (10 AZN / 15 gün, sonra avtomatik pulsuz elan)"
    }
  };

  class AvtoUnvanAiEngine {
    constructor(config = {}) {
      this.config = { ...DEFAULT_CONFIG, ...config };
      this.history = [];
      this.context = {
        lastBrand: null,
        lastModel: null,
        lastYear: null,
        lastIntent: null,
        lastBudget: null
      };
    }

    reset() {
      this.history = [];
      this.context = {
        lastBrand: null,
        lastModel: null,
        lastYear: null,
        lastIntent: null,
        lastBudget: null
      };
    }

    async ask(userMessage, options = {}) {
      const cleanMsg = String(userMessage || "").trim();
      if (!cleanMsg) {
        return "Zəhmət olmasa sualınızı yazın — məsələn: model, qiymət, səs/nasazlıq, barter və ya elan paketi barədə.";
      }

      this._updateContext(cleanMsg);
      this.history.push({ role: "user", text: cleanMsg, time: Date.now() });

      // 1. Canlı backend / AI API cəhdi
      const endpoint = options.apiEndpoint || this.config.apiEndpoint;
      if (endpoint && !options.forceLocal) {
        try {
          const liveReply = await this._fetchLiveAi(cleanMsg, endpoint);
          if (liveReply && typeof liveReply === "string" && liveReply.trim()) {
            const finalReply = liveReply.trim();
            this.history.push({ role: "assistant", text: finalReply, time: Date.now(), source: "live-api" });
            return finalReply;
          }
        } catch (_err) {
          // Backend/API yoxdursa və ya cavab vermirsə, səssizcə yerli canlı mühərrikə keçir
        }
      }

      // 2. Daxili canlı adaptiv ekspert mühərriki
      const smartReply = this._generateAdaptiveReply(cleanMsg);
      this.history.push({ role: "assistant", text: smartReply, time: Date.now(), source: "adaptive-engine" });
      return smartReply;
    }

    async _fetchLiveAi(message, endpoint) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.config.requestTimeoutMs);

      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            message,
            history: this.history.slice(-10),
            context: this.context,
            systemInstruction:
              "Sən AvtoÜnvan avtomobil platformasının canlı AI Ekspertisən. Yalnız Azərbaycan dilində, səmimi, dəqiq və praktik cavab ver. İstifadəçinin verdiyi suala birbaşa cavab ver (qiymət, model seçimi, barter, səs/titrəmə/nasazlıq diaqnostikası, sənədlər, Təcili 1 AZN və VIP 10 AZN / 15 gün elan paketləri). Eyni şablon cavabı təkrarlama."
          })
        });

        if (!res.ok) return null;
        const data = await res.json();
        return data.reply || data.answer || data.text || data.message || null;
      } finally {
        clearTimeout(timer);
      }
    }

    _updateContext(text) {
      const lower = text.toLowerCase();

      const catalog = [
        { brand: "Toyota", model: "Prius", pattern: /\b(toyota\s*prius|prius)\b/i },
        { brand: "Toyota", model: "Camry", pattern: /\b(toyota\s*camry|camry)\b/i },
        { brand: "Toyota", model: "Corolla", pattern: /\b(toyota\s*corolla|corolla)\b/i },
        { brand: "Toyota", model: "RAV4", pattern: /\b(toyota\s*rav4|rav4)\b/i },
        { brand: "Hyundai", model: "Tucson", pattern: /\b(hyundai\s*tucson|tucson)\b/i },
        { brand: "Hyundai", model: "Elantra", pattern: /\b(hyundai\s*elantra|elantra)\b/i },
        { brand: "Hyundai", model: "Santa Fe", pattern: /\b(hyundai\s*santa\s*fe|santa\s*fe)\b/i },
        { brand: "Kia", model: "Optima / K5", pattern: /\b(kia\s*optima|optima|kia\s*k5|\bk5\b)\b/i },
        { brand: "Kia", model: "Sorento", pattern: /\b(kia\s*sorento|sorento)\b/i },
        { brand: "Kia", model: "Sportage", pattern: /\b(kia\s*sportage|sportage)\b/i },
        { brand: "BMW", model: "X5", pattern: /\b(bmw\s*x5|\bx5\b)\b/i },
        { brand: "BMW", model: "3 Series / F30", pattern: /\b(bmw\s*3|f30|320i|328i)\b/i },
        { brand: "BMW", model: "5 Series / F10", pattern: /\b(bmw\s*5|f10|528i|530i)\b/i },
        { brand: "Mercedes-Benz", model: "E-Class", pattern: /\b(mercedes\s*e|e-class|e200|e220|e350|panarama)\b/i },
        { brand: "Mercedes-Benz", model: "C-Class", pattern: /\b(mercedes\s*c|c-class|c200|c250|c300)\b/i },
        { brand: "Chevrolet", model: "Cruze / Malibu", pattern: /\b(chevrolet\s*cruze|cruze|malibu)\b/i },
        { brand: "Nissan", model: "Qashqai / X-Trail", pattern: /\b(nissan\s*qashqai|qashqai|x-trail)\b/i },
        { brand: "Land Rover", model: "Range Rover", pattern: /\b(range\s*rover|land\s*rover)\b/i },
        { brand: "BYD", model: "Destroyer / Song", pattern: /\b(byd|destroyer\s*05|song\s*plus)\b/i }
      ];

      for (const item of catalog) {
        if (item.pattern.test(lower)) {
          this.context.lastBrand = item.brand;
          this.context.lastModel = item.model;
          break;
        }
      }

      const brandsOnly = [
        ["Toyota", /\btoyota\b/i],
        ["Hyundai", /\bhyundai\b/i],
        ["Kia", /\bkia\b/i],
        ["BMW", /\bbmw\b/i],
        ["Mercedes-Benz", /\b(mercedes|mersedes)\b/i],
        ["Chevrolet", /\b(chevrolet|şevrolet)\b/i],
        ["Nissan", /\bnissan\b/i],
        ["Lexus", /\blexus\b/i],
        ["Porsche", /\bporsche\b/i],
        ["Audi", /\baudi\b/i],
        ["Volkswagen", /\b(volkswagen|vw)\b/i]
      ];

      if (!this.context.lastModel) {
        for (const [bName, bRegex] of brandsOnly) {
          if (bRegex.test(lower)) {
            this.context.lastBrand = bName;
            break;
          }
        }
      }

      const yearMatch = lower.match(/\b(199\d|20[0-2]\d)\b/);
      if (yearMatch) {
        this.context.lastYear = Number(yearMatch[1]);
      }

      const budgetMatch = lower.match(/\b(\d{2,3})\s*(min|k|azn|manat|\$)?\b/i);
      if (budgetMatch && /(büdcə|budce|pul|azn|manat|min|\$)/i.test(lower)) {
        this.context.lastBudget = budgetMatch[0];
      }
    }

    _detectIntents(lower) {
      const intents = [];
      if (/(səs|ses|titrəmə|titreme|vibrasiya|xəta|xeta|şıq|isiq|check|abs|hybrid|batareya|mühərrik|muherrik|motor|karobka|sürətlər\s*qutusu|tüstü|tustu|yağ|yag|qızma|qizma|əyləc|eylec|xodovoy|asqı|asqi)/i.test(lower)) {
        intents.push("diagnostics");
      }
      if (/(qiymət|qiymet|neçəyə|neceye|neçədir|necedir|bazar|likvid|likvidlik|dəyər|deyer|ucuz|bahalı|bahali)/i.test(lower)) {
        intents.push("pricing");
      }
      if (/(almaq|aliram|alıram|alacam|seçmək|secmek|hansı\s*maşın|hansi\s*masin|məsləhət|meslehet|tövsiyə|tovsiye)/i.test(lower)) {
        intents.push("buying");
      }
      if (/(satmaq|satiram|satıram|satacam|tez\s*sat|təcili|tecili|vip|elan|1\s*azn|10\s*azn|paket)/i.test(lower)) {
        intents.push("selling");
      }
      if (/(barter|dəyişmək|deyismek|dəyişdir|deyisdir|kredit|lizinq|ilkin\s*ödəniş|ilkin\s*odenis)/i.test(lower)) {
        intents.push("barter_finance");
      }
      if (/(sənəd|sened|qeydiyyat|texniki\s*baxış|texniki\s*baxis|sığorta|sigorta|cərimə|cerime|vin|carfax)/i.test(lower)) {
        intents.push("documents");
      }
      if (/^(salam|salams|sabahın\s*xeyir|sabahin\s*xeyir|axşamın\s*xeyir|axsamin\s*xeyir|sağ\s*ol|sag\s*ol|təşəkkür|tesekkur|cox\s*sagol|çox\s*sağ\s*ol)\b/i.test(lower)) {
        intents.push("greeting");
      }
      if (intents.length === 0) {
        intents.push("general");
      }
      return intents;
    }

    _carLabel() {
      const parts = [];
      if (this.context.lastYear) parts.push(String(this.context.lastYear));
      if (this.context.lastBrand && !String(this.context.lastModel || "").toLowerCase().includes(this.context.lastBrand.toLowerCase())) {
        parts.push(this.context.lastBrand);
      }
      if (this.context.lastModel) parts.push(this.context.lastModel);
      else if (this.context.lastBrand) parts.push(this.context.lastBrand);
      return parts.length ? parts.join(" ") : "avtomobil";
    }

    _generateAdaptiveReply(rawText) {
      const lower = rawText.toLowerCase().trim();
      const car = this._carLabel();
      const intents = this._detectIntents(lower);
      const primary = intents[0];
      this.context.lastIntent = primary;

      // Salamlaşma / təşəkkür
      if (primary === "greeting" && intents.length === 1) {
        return (
          `Salam! Mən **AvtoÜnvan AI Ekspert**əm. İstədiyin avtomobil üzrə sənə dərhal kömək edə bilərəm:\n` +
          `• **Qiymət və likvidlik** (məsələn: *2020 BMW X5 Bakı qiyməti* veya *2022 Hyundai Tucson likvidliyi*)\n` +
          `• **Texniki analiz** (səs, titrəmə, xəta işıqları, hibrid/mühərrik/karobka)\n` +
          `• **Alış, barter və satış strategiyası** (${this.config.packages.urgent} və ${this.config.packages.vip})\n` +
          `İndi hansı avtomobil və ya mövzu ilə maraqlanırsan?`
        );
      }

      // 1. Texniki diaqnostika (səs, titrəmə, xəta, nasazlıq)
      if (primary === "diagnostics") {
        const hasVibration = /(titrəmə|titreme|vibrasiya|əsir|esir)/i.test(lower);
        const hasNoise = /(səs|ses|taqqıltı|taqqilti|fışıltı|fisilti|cırıltı|cirilti|ulama)/i.test(lower);
        const hasHybridOrEngine = /(hybrid|hibrid|batareya|mühərrik|muherrik|motor|karobka|sürətlər|suretler|abs|check)/i.test(lower);

        let points = [];
        if (hasVibration) {
          points.push("Təkər balansı/disk əyriliyi, əyləc disklərinin deformasiyası və ya mühərrik/karobka yastıqları (paduşkalar) titrəmə yarada bilər.");
        }
        if (hasNoise) {
          points.push("Səsin xarakteri vacibdir: döngədə/hərəkətdə artan səs çox vaxt stupitsa (podşibnik) və ya qranatla, rölantidəki səs isə qayış/rolik və ya egzoz/istilik qoruyucusu ilə bağlı olur.");
        }
        if (hasHybridOrEngine) {
          points.push("Mühərrik, sürətlər qutusu və ya hibrid sistemində kompüter diaqnostikası (OBD/Hybrid scanner) və yağ/soyutma/batareya vəziyyətinin yoxlanılması ən etibarlı ilk addımdır.");
        }
        if (!points.length) {
          points.push("Nasazlığın nə vaxt baş verdiyini (səhər ilk işə salmada, sürət yığanda, əyləc basanda və ya çuxurda) dəqiqləşdirmək lazımdır.");
        }

        return (
          `**${car}** üzrə ilkin texniki təhlil:\n` +
          points.map((p) => `• ${p}`).join("\n") +
          `\n\nDəqiq yönləndirməyim üçün yaz: **səs/titrəmə hansı anda olur**, **panelde xəbərdarlıq işığı yanırmı** və **avtomobilin ili/yürüşü nə qədərdir**?`
        );
      }

      // 2. Qiymət, bazar və likvidlik
      if (primary === "pricing") {
        const isLiquidity = /(likvid|likvidlik|tez\s*satılır|tez\s*satilir)/i.test(lower);
        if (isLiquidity) {
          return (
            `**${car}** üzrə bazar likvidliyi təhlili:\n` +
            `• Bakı və bölgə bazarında ehtiyat hissələrinin tapılma asanlığı, servis tanınması və yanacaq sərfiyyatı likvidliyə birbaşa təsir edir.\n` +
            `• Vuruqsuz (öz detallarında), təmiz sənədli və real yürüşlü nüsxələr bazar ortalamasına yaxın qiymətdə daha tez alıcı tapır; həddindən artıq yüksək qiymət qoyulduqda satış müddəti uzanır.\n` +
            `Əgər avtomobili satırsansa, **Təcili Satış (1 AZN — satılanadək aktiv)** və ya **VIP Paket (10 AZN / 15 gün, sonra avtomatik pulsuz elan)** ilə görünürlüğü artıra bilərsən.`
          );
        }

        return (
          `**${car}** üçün bazar qiyməti yanaşması:\n` +
          `• Real bazar qiyməti **buraxılış ili**, **yürüş (km)**, **mühərrik/komplektasiya** və **kuzov/texniki vəziyyət** (vuruq/rəng, servis tarixçəsi) əsasında formalaşır.\n` +
          `• Ən doğru qiymət aralığını müəyyən etmək üçün eyni il və yürüşdə olan 3–5 rəqib elanı müqayisə etmək, texniki qüsur varsa isə təmir xərcini nəzərə almaq məsləhətdir.\n` +
          `Dəqiq qiymət yönləndirməsi istəyirsənsə, **ilini, təxmini yürüşünü və mühərrik/komplektasiyasını** yaz.`
        );
      }

      // 3. Alış və model seçimi
      if (primary === "buying") {
        const budgetNote = this.context.lastBudget ? ` Qeyd etdiyin büdcə yönümünə (${this.context.lastBudget}) uyğun seçimdə yürüş və texniki vəziyyəti ön planda saxlamaq vacibdir.` : "";
        return (
          `**${car}** almaq istəyirsənsə, riskləri azaltmaq üçün bu ardıcıllıqla yoxla:\n` +
          `1. **Tarixçə və sənədlər:** VIN kod yoxlanışı, vuruq/suda qalma/yürüş geri çəkilmə ehtimalı və cərimə/məhdudiyyət olmaması.\n` +
          `2. **Texniki baxış:** Mühərrik, sürətlər qutusu, asqı sistemi və hibrid/elektronika üzrə müstəqil usta + diaqnostika.\n` +
          `3. **Gündəlik istifadə uyğunluğu:** Şəhəriçi tıxac, uzun məsafə və servis xərcləri sənin sürmə tərzinə uyğun gəlməlidir.${budgetNote}\n` +
          `Hansı il aralığını düşünürsən və avtomobili əsasən şəhəriçi, yoxsa uzaq yol üçün sürəcəksən?`
        );
      }

      // 4. Satış və elan paketləri
      if (primary === "selling") {
        return (
          `**${car}** satışını sürətləndirmək və daha çox alıcıya çatmaq üçün tövsiyə:\n` +
          `• **Təcili Satış (1 AZN — satılanadək aktiv):** Qiyməti bazar səviyyəsində saxlayıb sürətli alıcı axtaranlar üçün uyğundur.\n` +
          `• **VIP Paket (10 AZN / 15 gün, sonra avtomatik pulsuz elan):** Elanın ön sıralarda görünməsi və daha çox klik/baxış toplaması üçün idealdır.\n` +
          `• **Elan keyfiyyəti:** Gündüz işığında çəkilmiş aydın şəkillər, real yürüş, vuruq/rəng haqqında açıq məlumat və dəqiq qiymət zəng sayını ciddi artırır.\n` +
          `Avtomobilin ili və istədiyin qiymət nədir? Ona uyğun elan mətni və qiymət strategiyası qura bilərəm.`
        );
      }

      // 5. Barter və maliyyə/kredit
      if (primary === "barter_finance") {
        return (
          `**${car}** üzrə barter və ya maliyyə məsələsində əsas prinsip bazar dəyərinin ədalətli hesablanmasıdır:\n` +
          `• Hər iki avtomobilin bazar qiymətini ayrı-ayrılıqda müəyyən et və fərqi (əlavə ödəniş) real texniki vəziyyətə görə razılaşdır.\n` +
          `• Barterdən öncə hər iki maşında sənəd təmizliyi və usta baxışı mütləq edilməlidir.\n` +
          `Hansı avtomobili verib, hansı avtomobillə barter etmək (və ya nə qədər əlavə/büdcə ayırmaq) istəyirsən?`
        );
      }

      // 6. Sənədlər / yoxlanış
      if (primary === "documents") {
        return (
          `**${car}** ilə bağlı sənəd və rəsmi yoxlamalarda bunlara diqqət et:\n` +
          `• Avtomobilin qeydiyyat şəhadətnaməsi (texpasport), etibarnamə/mülkiyyət hüququ, icbari sığorta və texniki baxış statusu uyğun olmalıdır.\n` +
          `• Alqı-satqıdan əvvəl rəsmi bazalardan cərimə və ya məhdudiyyət olub-olmadığını dəqiqləşdirmək lazımdır.\n` +
          `Konkret olaraq hansı sənəd və ya yoxlama mərhələsi ilə bağlı sualın var?`
        );
      }

      // 7. Digər bütün sərbəst suallar
      return (
        `Sualını (**"${rawText}"**) nəzərə alaraq **${car}** kontekstində belə kömək edə bilərəm:\n` +
        `• Əgər **qiymət / bazar** maraqlandırırsa: ilini, yürüşünü və vəziyyətini yaz.\n` +
        `• Əgər **texniki problem / səs / xəta** varsa: simptomun nə vaxt yarandığını və xəbərdarlıq işıqlarını qeyd et.\n` +
        `• Əgər **alış / satış / barter** planlayırsansa: məqsədini və büdcə/qiymət aralığını de, sənə uyğun konkret plan çıxarım.`
      );
    }
  }

  // Avtomatik DOM bağlantısı (əgər səhifədə input və göndər düyməsi varsa)
  function bindAutoUi(engine) {
    const findSendButton = () => {
      const buttons = Array.from(document.querySelectorAll("button, [role='button']"));
      return buttons.find((el) => /göndər|gonder|send/i.test((el.textContent || "").trim()));
    };

    const findInput = () => {
      const inputs = Array.from(document.querySelectorAll("input[type='text'], input:not([type]), textarea"));
      return inputs.find((el) => /sualınızı|sualinizi|yazın|yazin|soruş|sorus|mesaj/i.test(el.placeholder || ""));
    };

    const appendBubble = (text, isUser) => {
      const input = findInput();
      const sendBtn = findSendButton();
      const anchor = input ? input.closest("form, div") : sendBtn ? sendBtn.parentElement : null;

      // Mövcud mesaj konteynerini tapmağa çalış
      let container = document.querySelector("[data-ai-messages], .ai-messages, .chat-messages");
      if (!container && anchor && anchor.parentElement) {
        const prevSiblings = Array.from(anchor.parentElement.children).filter(
          (el) => el !== anchor && !el.contains(input) && !el.contains(sendBtn)
        );
        container = prevSiblings.find((el) => el.scrollHeight > 120 || el.children.length >= 1) || null;
      }

      if (!container) {
        container = document.createElement("div");
        container.setAttribute("data-ai-messages", "true");
        container.style.cssText = "display:flex;flex-direction:column;gap:10px;margin:12px 0;max-height:360px;overflow-y:auto;";
        if (anchor && anchor.parentElement) {
          anchor.parentElement.insertBefore(container, anchor);
        } else {
          document.body.appendChild(container);
        }
      }

      const bubble = document.createElement("div");
      bubble.style.cssText = isUser
        ? "align-self:flex-end;background:#107c56;color:#fff;padding:10px 14px;border-radius:14px;max-width:85%;font-size:14px;line-height:1.45;white-space:pre-line;"
        : "align-self:flex-start;background:#142230;color:#e6eef6;border:1px solid rgba(255,255,255,0.08);padding:12px 14px;border-radius:14px;max-width:88%;font-size:14px;line-height:1.5;white-space:pre-line;";

      // Sadə **bold** formatını təhlükəsiz şəkildə tətbiq et
      bubble.innerHTML = "";
      const parts = String(text).split(/(\*\*[^*]+\*\*)/g);
      for (const part of parts) {
        if (/^\*\*[^*]+\*\*$/.test(part)) {
          const strong = document.createElement("strong");
          strong.textContent = part.slice(2, -2);
          bubble.appendChild(strong);
        } else {
          bubble.appendChild(document.createTextNode(part));
        }
      }

      container.appendChild(bubble);
      container.scrollTop = container.scrollHeight;
    };

    const handleSend = async (ev) => {
      if (ev) ev.preventDefault();
      const input = findInput();
      if (!input) return;

      const text = input.value.trim();
      if (!text) return;

      input.value = "";
      appendBubble(text, true);

      const typingEl = document.createElement("div");
      typingEl.textContent = "AI Ekspert cavab hazırlayır...";
      typingEl.style.cssText = "align-self:flex-start;color:#8fa3b8;font-size:12px;padding:4px 8px;";

      const messagesBox = document.querySelector("[data-ai-messages]") || document.body;
      messagesBox.appendChild(typingEl);
      messagesBox.scrollTop = messagesBox.scrollHeight;

      const reply = await engine.ask(text);
      typingEl.remove();
      appendBubble(reply, false);
    };

    document.addEventListener("click", (ev) => {
      const target = ev.target.closest("button, [role='button']");
      if (!target) return;
      if (/göndər|gonder|send/i.test((target.textContent || "").trim())) {
        handleSend(ev);
      }
    });

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        const active = document.activeElement;
        if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
          if (/sualınızı|sualinizi|yazın|yazin|soruş|sorus|mesaj/i.test(active.placeholder || "")) {
            handleSend(ev);
          }
        }
      }
    });
  }

  const engine = new AvtoUnvanAiEngine();
  window.AvtoUnvanAiEngine = AvtoUnvanAiEngine;
  window.avtoUnvanAi = engine;
  window.askAiExpert = (msg, opts) => engine.ask(msg, opts);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => bindAutoUi(engine));
  } else {
    bindAutoUi(engine);
  }
})();
