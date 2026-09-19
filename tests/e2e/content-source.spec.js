const { test, expect } = require("@playwright/test");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");


const raiz = resolve(__dirname, "../..");
const manifest = JSON.parse(
  readFileSync(resolve(raiz, "extension/meet/manifest.json"), "utf8")
);
const contentScript = readFileSync(resolve(raiz, "extension/meet/content.js"), "utf8");


test("a extensão referencia e executa content.js real em contexto isolado", async ({ page }) => {
  expect(manifest.content_scripts[0].js).toContain("content.js");
  await page.setContent("<main></main>");
  await page.evaluate(() => {
    class WebSocketFalsa {
      static OPEN = 1;

      constructor() {
        this.readyState = WebSocketFalsa.OPEN;
      }

      send(payload) {
        window.__eventosMeetTeste.push(JSON.parse(payload));
      }

      close() {
        this.readyState = 3;
      }
    }

    window.__eventosMeetTeste = [];
    window.WebSocket = WebSocketFalsa;
    window.setInterval = () => 0;
  });
  await page.addScriptTag({ content: contentScript });
  await page.evaluate(() => {
    const bloco = document.createElement("section");
    bloco.setAttribute("data-caption-block", "");
    bloco.innerHTML =
      '<span data-speaker-name="Pessoa Sintética"></span>' +
      '<span data-caption-text>vamos revisar o cronograma</span>';
    document.body.append(bloco);
  });

  await expect
    .poll(() => page.evaluate(() => window.__eventosMeetTeste))
    .toContainEqual(expect.objectContaining({
      nome: "Pessoa Sintética",
      tipo: "legenda",
      texto: "vamos revisar o cronograma"
    }));
});
