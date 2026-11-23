/**
 * AvtoUnvan — AI Ekspert Override (avtounvan-ai-override.js)
 * Sabit "AI Secim Tovsiyesi: ..." sablonunu ve diger statik cavablari
 * tutub suala uygun dinamik cavabla evez edir.
 */
(function () {
  const TARGET_PHRASES = [
    "ai seçim tövsiyəsi",
    "ai secim tovsiyesi",
    "aşağı yanacaq sərfiyyatı və ehtiyat hissələrinin əlçatanlığı baxımından",
    "müqayisə etmək üçün kəşf et bölməsindəki filtrlərdən istifadə edə bilərsiniz",
    "bazar koridorunda satılır",
    "təcili satış (1 azn",
    "vip paket (10 azn",
    "ai bazar analizi",
    "toyota camry hybrid, hyundai tucson və ya byd seal u dm-i",
    "men toyota prius almaq isteyirem",
    "mən toyota prius almaq istəyirəm"
  ];

  function isTemplateString(text) {
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
    return "Avtomobil uzre komek";
  }

  function buildDynamicReply(questionText) {
    const q = (questionText || "").trim();
    const low = q.toLowerCase();

    if (!q || low === "avtomobil uzre komek") {
      return "Avtomobil uzre komek etmeye haziram. Hansi marka/model, il, qiymet araligi ve ya nasazliq barede sorusmaq isteyirsiniz?";
    }

    if (/^(salam|sal|sagol|sağol|təşəkkür|tesekkur|ok|okay|hi|hello)\b/i.test(low) && low.length <= 25) {
      return "Salam! AvtoUnvan AI Ekspert buradadir. Avtomobil secimi, bazar qiymeti, texniki nasazliq, alis, satis ve ya barter uzre sualinizi yaza bilersiniz.";
    }

    if (low.includes("qiymət") || low.includes("qiymet") || low.includes("nə qədər") || low.includes("ne qeder")) {
      return `"${q}" uzre bazar qiymeti avtomobilin buraxilis ili, yurusu (km), texniki veziyyeti ve muherrik/komplektasiyasindan asili olaraq deyisir. Deqiq qiymet araligi ucun marka, model, il ve texmini budceni yazin.`;
    }

    if (
      low.includes("səs") ||
      low.includes("ses") ||
      low.includes("titrəmə") ||
      low.includes("titre") ||
      low.includes("mühərrik") ||
      low.includes("muherrik") ||
      low.includes("əyləc") ||
      low.includes("eylec") ||
      low.includes("nasaz") ||
      low.includes("xarab")
    ) {
      return `"${q}" ile bagli ilkin texniki yoxlamada muherrik yastiqlari, asqi (xodovoy) elementleri, eylec diskleri/balatalari ve ya transmissiya/yag veziyyeti nezerden kecirilmelidir. Avtomobilin markasini, ilini ve sesin/titremenin ne vaxt yarandigini qeyd edin.`;
    }

    if (low.includes("sat") || low.includes("barter") || low.includes("təcili") || low.includes("tecili") || low.includes("vip")) {
      return `"${q}" meqsedi ucun elanda aydin sekiller, real yurus, texniki baxis melumati ve bazar uygun qiymet gostermek satisi suretlendirir. Hansi avtomobili satmaq ve ya deyismek isteyirsiniz?`;
    }

    return `"${q}" sorgunuz uzre secim ve ya tovsiye ucun avtomobilin buraxilis ili, budceniz ve esas ustunluyunuz (yanacaq serfiyyati, ailevi genislik, komfort ve ya suretli satis) barede melumat verin, size uygun variantlari siralayim.`;
  }

  function replaceInDom(root) {
    if (!root) return;
    const q = getLastUserQuestion();
    const reply = buildDynamicReply(q);

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.nodeValue && isTemplateString(node.nodeValue)) {
        node.nodeValue = reply;
      }
    }

    if (root.querySelectorAll) {
      const all = root.querySelectorAll("*");
      for (const el of all) {
        if (el.children.length === 0 && typeof el.textContent === "string" && isTemplateString(el.textContent)) {
          el.textContent = reply;
        }
      }
    }
  }

  function hookCommonGlobals() {
    const names = [
      "askAiExpert",
      "getAiExpertReply",
      "generateAiReply",
      "sendAiMessage",
      "handleAiSubmit"
    ];
    for (const fnName of names) {
      if (typeof window[fnName] === "function") {
        const orig = window[fnName];
        window[fnName] = async function (...args) {
          const prompt = typeof args[0] === "string" ? args[0] : getLastUserQuestion();
          const res = await orig.apply(this, args);
          if (!res || typeof res !== "string" || isTemplateString(res)) {
            return buildDynamicReply(prompt);
          }
          return res;
        };
      }
    }
  }

  const observer = new MutationObserver(() => {
    replaceInDom(document.body);
  });

  function start() {
    hookCommonGlobals();
    if (document.body) {
      replaceInDom(document.body);
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true
      });
    }
    setInterval(() => {
      if (document.body) {
        replaceInDom(document.body);
      }
    }, 600);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
