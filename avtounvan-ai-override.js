/**
 * AvtoÜnvan — AI Ekspert Override v6 (avtounvan-ai-override.js)
 * Səhifədəki sabit "AI Seçim Tövsiyəsi: ..." şablonunu və digər sabit cavabları
 * tutub suala uyğun dinamik cavabla əvəz edir.
 * Həmçinin mövcud window.askAiExpert və ya səhifədəki köhnə cavab funksiyalarını əhatə edir.
 */
(function () {
  const TARGET_PHRASES = [
    "ai seçim tövsiyəsi",
    "aşağı yanacaq sərfiyyatı və ehtiyat hissələrinin əlçatanlığı baxımından",
    "müqayisə etmək üçün kəşf et bölməsindəki filtrlərdən istifadə edə bilərsiniz",
    "bazar koridorunda satılır",
    "təcili satış (1 azn",
    "vip paket (10 azn",
    "ai bazar analizi",
    "toyota camry hybrid, hyundai tucson və ya byd seal u dm-i"
  ];

  function looksLikeFixedTemplate(text) {
    if (!text || typeof text !== "string") return false;
    const low = text.toLowerCase();
    return TARGET_PHRASES.some((p) => low.includes(p));
  }

  function getLastUserQuestion() {
    if (window.avtoUnvanAi && Array.isArray(window.avtoUnvanAi.history)) {
      for (let i = window.avtoUnvanAi.history.length - 1; i >= 0; i--) {
        if (window.avtoUnvanAi.history[i].role === "user" && window.avtoUnvanAi.history[i].text) {
          return window.avtoUnvanAi.history[i].text;
        }
      }
    }
    const input = document.querySelector(
      "input[placeholder*='Sual'], input[placeholder*='sual'], textarea[placeholder*='Sual'], textarea[placeholder*='sual'], input[type='text'], textarea"
    );
    if (input && input.value && input.value.trim()) {
      return input.value.trim();
    }
    return "Avtomobil üzrə kömək";
  }

  function buildFallbackAnswer(questionText) {
    const q = (questionText || "").trim();
    const low = q.toLowerCase();

    if (!q || low === "avtomobil üzrə kömək") {
      return "Avtomobil üzrə kömək etməyə hazıram. Hansı marka/model, il, qiymət aralığı və ya nasazlıq barədə soruşmaq istəyirsiniz?";
    }

    if (low.includes("qiymət") || low.includes("qiymet") || low.includes("nə qədər") || low.includes("ne qeder")) {
      return `"${q}" üzrə bazar qiyməti avtomobilin buraxılış ili, yürüşü (km), texniki vəziyyəti və mühərrik/komplektasiyasından asılı olaraq dəyişir. Dəqiq qiymət aralığı üçün marka, model, il və təxmini büdcəni yazın.`;
    }

    if (low.includes("səs") || low.includes("ses") || low.includes("titrəmə") || low.includes("titre") || low.includes("mühərrik") || low.includes("muherrik") || low.includes("əyləc") || low.includes("eylec") || low.includes("nasaz") || low.includes("xarab")) {
      return `"${q}" ilə bağlı ilkin texniki yoxlamada mühərrik yastıqları, asqı (xodovoy) elementləri, əyləc diskləri/balataları və ya transmissiya/yağ vəziyyəti nəzərdən keçirilməlidir. Avtomobilin markasını, ilini və səsin/titrəmənin nə vaxt yarandığını qeyd edin.`;
    }

    if (low.includes("sat") || low.includes("barter") || low.includes("təcili") || low.includes("tecili") || low.includes("vip")) {
      return `"${q}" məqsədi üçün elanda aydın şəkillər, real yürüş, texniki baxış məlumatı və bazar uyğun qiymət göstərmək satışı sürətləndirir. Hansı avtomobili satmaq və ya dəyişmək istəyirsiniz?`;
    }

    return `"${q}" sorğunuz üzrə seçim və ya tövsiyə üçün avtomobilin buraxılış ili, büdcəniz və əsas üstünlüyünüz (yanacaq sərfiyyatı, ailəvi genişlik, komfort və ya sürətli satış) barədə məlumat verin, sizə uyğun variantları sıralayım.`;
  }

  async function computeDynamicReply(questionText) {
    const q = (questionText && questionText.trim()) || getLastUserQuestion();
    if (typeof window.askAiExpert === "function") {
      try {
        const res = await window.askAiExpert(q);
        if (res && typeof res === "string" && !looksLikeFixedTemplate(res)) {
          return res;
        }
      } catch (e) {
        // Fallback below
      }
    }
    return buildFallbackAnswer(q);
  }

  const replacedNodes = new WeakSet();
  async function scanAndReplaceTemplates(root = document.body) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const candidates = [];
    let node;
    while ((node = walker.nextNode())) {
      if (!node.nodeValue || replacedNodes.has(node)) continue;
      if (looksLikeFixedTemplate(node.nodeValue)) {
        candidates.push(node);
      }
    }
    for (const textNode of candidates) {
      replacedNodes.add(textNode);
      const q = getLastUserQuestion();
      const dynamicText = await computeDynamicReply(q);
      if (dynamicText && textNode.nodeValue !== dynamicText) {
        textNode.nodeValue = dynamicText;
      }
    }
  }

  function bindComposerInterceptor() {
    const findInput = () => {
      const els = Array.from(document.querySelectorAll("input, textarea"));
      return (
        els.find((el) => /sual|yazın|yazin|soruş|sorus|mesaj/i.test(el.placeholder || "")) ||
        els[0] ||
        null
      );
    };

    const triggerDynamicFlow = async (explicitText) => {
      const inp = findInput();
      const text = (explicitText || (inp && inp.value) || "").trim();
      if (!text) return;

      if (window.avtoUnvanAi && typeof window.avtoUnvanAi._updateContext === "function") {
        window.avtoUnvanAi._updateContext(text);
        window.avtoUnvanAi.history.push({ role: "user", text, time: Date.now() });
      }

      [80, 250, 600, 1200, 2200].forEach((ms) => {
        setTimeout(() => {
          scanAndReplaceTemplates(document.body);
        }, ms);
      });
    };

    document.addEventListener(
      "click",
      (ev) => {
        const btn = ev.target.closest("button, [role='button']");
        if (!btn) return;
        const label = (btn.innerText || btn.textContent || "").trim();
        if (/göndər|gonder|send/i.test(label) || btn.type === "submit") {
          const inp = findInput();
          const val = inp ? inp.value.trim() : "";
          if (val) {
            triggerDynamicFlow(val);
          }
        }
      },
      true
    );

    document.addEventListener(
      "keydown",
      (ev) => {
        if (ev.key === "Enter" && !ev.shiftKey) {
          const active = document.activeElement;
          if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
            const val = active.value.trim();
            if (val) {
              triggerDynamicFlow(val);
            }
          }
        }
      },
      true
    );
  }

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const added of m.addedNodes) {
        if (added.nodeType === 1) {
          scanAndReplaceTemplates(added);
        }
      }
    }
  });

  function init() {
    bindComposerInterceptor();
    if (document.body) {
      scanAndReplaceTemplates(document.body);
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
