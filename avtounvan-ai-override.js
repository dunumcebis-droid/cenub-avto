/**
 * AvtoÜnvan — AI Ekspert Override v4 (avtounvan-ai-override.js)
 * Səhifədəki sabit "AI Seçim Tövsiyəsi: ..." şablonunu və digər sabit cavabları
 * tutub suala uyğun dinamik cavabla əvəz edir.
 */
(function () {
  const TARGET_PHRASES = [
    "ai seçim tövsiyəsi",
    "aşağı yanacaq sərfiyyatı və ehtiyat hissələrinin əlçatanlığı baxımından",
    "müqayisə etmək üçün kəşf et bölməsindəki filtrlərdən istifadə edə bilərsiniz",
    "bazar koridorunda satılır",
    "təcili satış (1 azn",
    "vip paket (10 azn",
    "ai bazar analizi"
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

  async function computeDynamicReply(questionText) {
    const q = (questionText && questionText.trim()) || getLastUserQuestion();
    if (typeof window.askAiExpert === "function") {
      return await window.askAiExpert(q);
    }
    return `Sualınız ("${q}") qəbul olundu. Hansı marka/model, il və ya mövzu (qiymət, nasazlıq, alış, satış, barter) barədə dəqiqləşdirmək istəyirsiniz?`;
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

      [100, 350, 800, 1500].forEach((ms) => {
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
        if (/göndər|gonder|send/i.test(label)) {
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
