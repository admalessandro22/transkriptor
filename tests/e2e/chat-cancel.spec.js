const { test, expect } = require("@playwright/test");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");


const raiz = resolve(__dirname, "../..");
const modelo = require("./helpers").template("assistente");
const js = readFileSync(resolve(raiz, "static/assistente.js"), "utf8");
const jsLista = readFileSync(resolve(raiz, "static/js/reunioes.js"), "utf8");
const { selecionarReuniao } = require("./helpers");


async function carregar(page) {
  await page.setContent(modelo);
  await page.evaluate(() => {
    window.__sinais = [];
    window.fetch = (url, opc) => {
      if (String(url).endsWith("/api/chat")) {
        return new Promise((_, rejeitar) => {
          const sinal = opc && opc.signal;
          window.__sinais.push(sinal || null);
          if (sinal) {
            sinal.addEventListener("abort", () => rejeitar(new DOMException("abortado", "AbortError")));
          }
        });
      }
      if (String(url).startsWith("/api/transcricoes")) {
        return Promise.resolve({ ok: true, json: async () => [{ arquivo: "reuniao.txt", data: "01/01/2026 10:00", tipo: "transcricao", tamanho_kb: 1, protegida: false, com_sua_voz: null }] });
      }
      if (String(url).endsWith("/api/modelos")) {
        return Promise.resolve({ ok: true, json: async () => ["llama3"] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    };
  });
  await page.addScriptTag({ content: jsLista });
  await page.addScriptTag({ content: js });
}


test("cancelar fecha o upstream: stop e Esc abortam o fetch", async ({ page }) => {
  await carregar(page);
  await page.waitForFunction(() => document.getElementById("transcricao").options.length === 1);
  await selecionarReuniao(page, "reuniao.txt");
  await page.fill("#input", "resuma");
  await page.click("#send");
  await expect
    .poll(() => page.evaluate(() => window.__sinais.length))
    .toBe(1);

  await page.click("#stop");
  await expect
    .poll(() => page.evaluate(() => window.__sinais[0] && window.__sinais[0].aborted))
    .toBe(true);
});
