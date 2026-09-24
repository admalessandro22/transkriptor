// Gera o snapshot ARIA (o que um leitor de tela anuncia: papéis, nomes, estados)
// de cada página da Central e da galeria, com fixtures sintéticas, para o roteiro
// do Narrador. Uso: node docs/sdd/v1.9/evidencias/T-14.F1/aria_snapshots.js
"use strict";
const path = require("node:path");
const { mkdirSync, writeFileSync } = require("node:fs");
const { chromium } = require("@playwright/test");
const { carregarPagina } = require("../../../../../tests/e2e/helpers");

const PAGINAS = ["inicio", "reunioes", "assistente", "participantes", "configuracoes", "diagnostico", "galeria"];
const destino = path.join(__dirname, "aria");
mkdirSync(destino, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  for (const pagina of PAGINAS) {
    const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
    await carregarPagina(page, pagina);
    await page.waitForTimeout(500);
    const snapshot = await page.locator("body").ariaSnapshot();
    writeFileSync(path.join(destino, `${pagina}.yaml`), snapshot + "\n");
    const linhas = snapshot.split("\n").length;
    const semNome = (snapshot.match(/^\s*- (button|link|textbox|combobox|listbox|checkbox|switch)$/gm) || []).length;
    console.log(`${pagina}: ${linhas} linhas, controles sem nome acessível: ${semNome}`);
    await page.close();
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
