// Captura a página de pareamento real (HTML/CSS/JS da extensão) nos três estados,
// nos dois temas, com o chrome.* simulado — nenhuma rede além dos arquivos locais.
// Uso: node docs/sdd/v1.9/evidencias/T-14.E5/capturar_pairing.js
"use strict";
const path = require("node:path");
const { readFileSync } = require("node:fs");
const { chromium } = require("@playwright/test");

const raiz = path.resolve(__dirname, "../../../../..");
const ext = (nome) => path.join(raiz, "extension", "meet", nome);
const CENARIOS = [
  { nome: "carregando", chrome: { pronto: false } },
  { nome: "sucesso", chrome: { pronto: true } },
  { nome: "erro", chrome: { lastError: { message: "no worker" } } },
];

(async () => {
  const browser = await chromium.launch();
  for (const tema of ["dark", "light"]) {
    for (const cenario of CENARIOS) {
      const page = await browser.newPage({ viewport: { width: 640, height: 720 }, colorScheme: tema });
      await page.route("**/*", (rota) => {
        const url = rota.request().url();
        const arquivo = url.replace("http://extensao.local/", "");
        const tipos = { html: "text/html", css: "text/css", js: "text/javascript", png: "image/png" };
        const ext_ = arquivo.split(".").pop();
        if (url.startsWith("http://extensao.local/") && tipos[ext_]) {
          return rota.fulfill({ status: 200, contentType: tipos[ext_], body: readFileSync(ext(arquivo)) });
        }
        return rota.abort();
      });
      await page.addInitScript((cfg) => {
        window.chrome = {
          storage: { session: { set: (obj, cb) => cb && cb() } },
          runtime: { lastError: cfg.lastError, sendMessage: (msg, cb) => cb && cb({ pronto: !!cfg.pronto }) },
        };
      }, cenario.chrome);
      await page.goto("http://extensao.local/pairing.html");
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.fill("#codigo", "pair-codigo-sintetico-0000000000");
      await page.click("#parear");
      await page.locator(`#estado[data-estado="${cenario.nome}"]`).waitFor();
      await page.waitForTimeout(300);
      const arquivo = path.join(__dirname, `pairing-${cenario.nome}-640-${tema}.png`);
      await page.screenshot({ path: arquivo });
      console.log(path.relative(raiz, arquivo));
      await page.close();
    }
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
