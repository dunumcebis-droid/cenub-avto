/**
 * AvtoÜnvan Canlı AI Ekspert — Backend Proxy (Node.js + Express + Gemini API)
 * İstifadə:
 *   npm install express
 *   export GEMINI_API_KEY="senin_api_acarin"
 *   node server-gemini-proxy.js
 */

const express = require("express");
const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const MODEL = process.env.GEMINI_MODEL || "gemini-2.5-flash";

app.post("/api/ai-expert", async (req, res) => {
  try {
    const { message, history = [], context = {}, systemInstruction } = req.body || {};
    if (!message || !String(message).trim()) {
      return res.status(400).json({ error: "Mesaj boş ola bilməz." });
    }

    if (!GEMINI_API_KEY) {
      return res.status(503).json({
        error: "GEMINI_API_KEY təyin edilməyib; frontend daxili ağıllı mühərrik işləyəcək."
      });
    }

    const contents = [];
    for (const item of history.slice(-8)) {
      if (!item || !item.text) continue;
      contents.push({
        role: item.role === "assistant" ? "model" : "user",
        parts: [{ text: String(item.text) }]
      });
    }

    // Son mesajın təkrarlanmaması üçün yoxla
    const lastContent = contents[contents.length - 1];
    if (!lastContent || lastContent.role !== "user" || lastContent.parts[0].text !== String(message).trim()) {
      contents.push({
        role: "user",
        parts: [{ text: String(message).trim() }]
      });
    }

    const sysPrompt =
      systemInstruction ||
      `Sən AvtoÜnvan avtomobil platformasının canlı AI Ekspertisən. Yalnız Azərbaycan dilində, aydın, səmimi və praktik cavab ver. Hər suala birbaşa cavab ver (bazar qiymətləri, avtomobil seçimi, barter, texniki nasazlıq/səs/titrəmə diaqnostikası, sənədlər, Təcili Satış 1 AZN və VIP Paket 10 AZN / 15 gün). Hazırkı söhbət konteksti: ${JSON.stringify(context)}`;

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${encodeURIComponent(GEMINI_API_KEY)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          systemInstruction: {
            parts: [{ text: sysPrompt }]
          },
          contents,
          generationConfig: {
            temperature: 0.7,
            maxOutputTokens: 700
          }
        })
      }
    );

    if (!response.ok) {
      const errText = await response.text();
      return res.status(response.status).json({ error: "Gemini API xətası", details: errText });
    }

    const data = await response.json();
    const reply =
      data?.candidates?.[0]?.content?.parts
        ?.map((p) => p.text || "")
        .join("")
        .trim() || "";

    if (!reply) {
      return res.status(500).json({ error: "Boş cavab alındı" });
    }

    return res.json({ reply });
  } catch (err) {
    return res.status(500).json({ error: "Server xətası", message: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`AvtoÜnvan AI Ekspert serveri http://localhost:${PORT} ünvanında işləyir`);
});
