// Captura o mesmo diálogo de confirmação na Central (Configurações → pausar) com o
// texto vindo de confirmacoes.py (T-14.E4).
// Uso: node docs/sdd/v1.9/evidencias/T-14.E4/capturar_central.js
"use strict";
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const { chromium } = require("@playwright/test");
const { carregarPagina } = require("../../../../../tests/e2e/helpers");

const raiz = path.resolve(__dirname, "../../../../..");
const textos = JSON.parse(execFileSync("python", ["-c", "import json,confirmacoes;print(json.dumps(confirmacoes.consequencia('pausar_gravacao')))"], { cwd: raiz, encoding: "utf-8" }));

(async () => {
  const browser = await chromium.launch();
  for (const tema of ["dark", "light"]) {
    const page = await browser.newPage({ viewport: { width: 1366, height: 800 }, colorScheme: tema });
    const cfg = { deteccao_ativa: true, diarizacao_ativa: true, identificar_minha_voz: false, usar_nomes_meet: true, modo_legendas_meet: false, criptografar_transcricoes: true, protection_mode: "compatible", modelo_whisper: "auto", iniciar_com_windows: false, perfil_voz_existe: false, modelos_whisper: ["auto", "small"] };
    const api = (url, req) => {
      if (!url.endsWith("/api/config")) return undefined;
      if (req.method() === "GET") return cfg;
      return { status: 409, body: JSON.stringify({ erro: "Confirmação necessária", acao: "pausar_gravacao", ...textos }) };
    };
    const ctx = await carregarPagina(page, "configuracoes", { api });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator("#cfg-deteccao_ativa").click();
    await page.locator("#dialogo-confirmacao").waitFor({ state: "visible" });
    await page.waitForTimeout(400);
    const arquivo = path.join(__dirname, `central-pausar-dialogo-1366-${tema}.png`);
    await page.screenshot({ path: arquivo });
    console.log(path.relative(raiz, arquivo), "violacoes:", ctx.violacoes.length);
    await page.close();
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
