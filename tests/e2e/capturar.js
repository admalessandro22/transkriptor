// Capturas sintéticas para evidência (SDD v1.9).
// Uso: node tests/e2e/capturar.js <task> [pagina=assistente] [larguras=1366]
// Saída: docs/sdd/v1.9/evidencias/<task>/<pagina>-<largura>-<tema>.png
"use strict";
const path = require("node:path");
const { mkdirSync } = require("node:fs");
const { chromium } = require("@playwright/test");
const { carregarPagina } = require("./helpers");

const [task, pagina = "assistente", largurasArg = "1366"] = process.argv.slice(2);
if (!task) { console.error("uso: node tests/e2e/capturar.js <task> [pagina] [larguras]"); process.exit(2); }
const raiz = path.resolve(__dirname, "../..");
const destino = path.join(raiz, "docs", "sdd", "v1.9", "evidencias", task);
mkdirSync(destino, { recursive: true });
const larguras = largurasArg.split(",").map((n) => parseInt(n, 10));

(async () => {
  const browser = await chromium.launch();
  for (const tema of ["dark", "light"]) {
    for (const largura of larguras) {
      const page = await browser.newPage({ viewport: { width: largura, height: largura < 900 ? 760 : 800 }, colorScheme: tema });
      const ctx = await carregarPagina(page, pagina);
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.waitForTimeout(600);
      const arquivo = path.join(destino, `${pagina}-${largura}-${tema}.png`);
      await page.screenshot({ path: arquivo, fullPage: pagina === "galeria" });
      console.log(path.relative(raiz, arquivo), "violacoes:", ctx.violacoes.length);
      await page.close();
    }
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
