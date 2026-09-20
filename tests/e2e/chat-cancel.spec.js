const { test, expect } = require("@playwright/test");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");


const raiz = resolve(__dirname, "../..");
const modelo = readFileSync(resolve(raiz, "templates/assistente.html"), "utf8")
  .replace(/\{\{[^}]*\}\}/g, "#");
const js = readFileSync(resolve(raiz, "static/assistente.js"), "utf8");


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
      if (String(url).endsWith("/api/transcricoes")) {
        return Promise.resolve({ ok: true, json: async () => [] });
      }
      if (String(url).endsWith("/api/modelos")) {
        return Promise.resolve({ ok: true, json: async () => [] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    };
  });
  await page.addScriptTag({ content: js });
}


test("cancelar fecha o upstream: stop e Esc abortam o fetch", async ({ page }) => {
  await carregar(page);
  await page.selectOption("#transcricao", []);
  await page.evaluate(() => {
    const sel = document.getElementById("transcricao");
    const op = document.createElement("option");
    op.value = "reuniao.txt";
    op.textContent = "reuniao.txt";
    sel.appendChild(op);
    sel.value = "reuniao.txt";
    document.getElementById("modelo").innerHTML = "<option>llama3</option>";
    document.getElementById("input").value = "resuma";
  });
  await page.click("#send");
  await expect
    .poll(() => page.evaluate(() => window.__sinais.length))
    .toBe(1);

  await page.click("#stop");
  await expect
    .poll(() => page.evaluate(() => window.__sinais[0] && window.__sinais[0].aborted))
    .toBe(true);
});
