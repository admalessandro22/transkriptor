const { test, expect } = require("@playwright/test");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");


const raiz = resolve(__dirname, "../..");
const manifest = JSON.parse(
  readFileSync(resolve(raiz, "extension/meet/manifest.json"), "utf8")
);
const contentScript = readFileSync(resolve(raiz, "extension/meet/content.js"), "utf8");
const parserScript = readFileSync(resolve(raiz, "extension/meet/parser.js"), "utf8");
const fundoScript = readFileSync(resolve(raiz, "extension/meet/background.js"), "utf8");
const pairingHtml = readFileSync(resolve(raiz, "extension/meet/pairing.html"), "utf8");
const pairingJs = readFileSync(resolve(raiz, "extension/meet/pairing.js"), "utf8");


test("manifesto MV3: service worker, sem segredo no content script", async () => {
  expect(manifest.manifest_version).toBe(3);
  expect(manifest.background.service_worker).toBe("background.js");
  expect(manifest.permissions).toContain("storage");
  expect(manifest.content_scripts[0].js).toEqual(["parser.js", "content.js"]);
  expect(contentScript).not.toMatch(/new\s+WebSocket/);
  expect(contentScript).not.toMatch(/MEET_WS_TOKEN/);
});


test("pareamento real guarda o código e aciona o service worker", async ({ page }) => {
  await page.setContent(pairingHtml);
  await page.evaluate(() => {
    window.__guardado = null;
    window.__enviado = [];
    window.chrome = {
      storage: {
        session: {
          set: (obj, cb) => {
            window.__guardado = obj;
            if (cb) cb();
          }
        }
      },
      runtime: {
        sendMessage: (msg, cb) => {
          window.__enviado.push(msg);
          if (cb) cb({ pronto: false });
        },
        lastError: undefined
      }
    };
  });
  await page.addScriptTag({ content: pairingJs });
  await page.fill("#codigo", "pair-codigo-de-uso-unico-12345");
  await page.click("#parear");
  await expect
    .poll(() => page.evaluate(() => window.__guardado))
    .toEqual({ meetWsToken: "pair-codigo-de-uso-unico-12345" });
  await expect
    .poll(() => page.evaluate(() => window.__enviado))
    .toEqual([{ tipo: "parear" }]);
  await expect(page.locator("#estado")).not.toBeEmpty();
});


test("background real valida remetente e anexa a aba", async ({ page }) => {
  await page.setContent("<main></main>");
  await page.evaluate(() => {
    window.chrome = { storage: {}, runtime: {} };
  });
  await page.addScriptTag({ content: fundoScript });
  const valido = await page.evaluate(() => window.validarSender({
    frameId: 0,
    tab: { id: 3 },
    url: "https://meet.google.com/abc-defg-hij"
  }));
  expect(valido).toBe(true);
  const subframe = await page.evaluate(() => window.validarSender({
    frameId: 2,
    tab: { id: 3 },
    url: "https://meet.google.com/abc-defg-hij"
  }));
  expect(subframe).toBe(false);
  const envelope = await page.evaluate(() => window.montarEnvelope(
    { nome: "Ana", tipo: "ativo" },
    { tab: { id: 3 } }
  ));
  expect(envelope).toMatchObject({ nome: "Ana", tabId: 3 });
});


test("content real entrega legenda ao fundo no navegador", async ({ page }) => {
  await page.setContent("<main></main>");
  await page.evaluate(() => {
    window.__eventosMeetTeste = [];
    window.chrome = {
      runtime: {
        sendMessage: (msg) => {
          window.__eventosMeetTeste.push(msg);
        }
      }
    };
    window.setInterval = () => 0;
  });
  await page.addScriptTag({ content: parserScript });
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
    .toEqual([expect.objectContaining({
      tipo: "meet-evento",
      evento: expect.objectContaining({ nome: "Pessoa Sintética" })
    })]);
});
