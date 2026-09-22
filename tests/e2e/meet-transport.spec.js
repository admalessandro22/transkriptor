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


test("background real valida pareamento e produz envelope cliente v1", async ({ page }) => {
  await page.setContent("<main></main>");
  await page.evaluate(() => {
    window.chrome = { runtime: { id: "abcdefghijklmnop", onMessage: { addListener: () => {} } } };
  });
  await page.addScriptTag({ content: fundoScript });
  const resultado = await page.evaluate(() => {
    const mensagens = [];
    const id = "abcdefghijklmnop";
    const pareado = window.aoReceberMensagem({ tipo: "parear" }, {
      id, frameId: 0, url: `chrome-extension://${id}/pairing.html`
    }, () => {}, { runtimeId: id, conectar: () => {} });
    const sender = { frameId: 0, tab: { id: 3 }, url: "https://meet.google.com/abc-defg-hij" };
    window.aoReceberMensagem({ tipo: "meet-evento", evento: { tipo: "reuniao", ativa: true } },
      sender, null, { enviar: (msg) => mensagens.push(msg) });
    const hello = mensagens[0];
    const sessao = window.aceitarSessao({ tipo: "sessao", connection_id: hello.connection_id,
      tab_id: "3", session_id: "sessao-sintetica", meeting_key: "sala-sintetica" });
    return { pareado, sessao, hello, envelope: window.montarEnvelope(
      { tipo: "legenda", nome: "Pessoa Sintética", texto: "fala sintética", caption_id: "c-1", caption_revision: 1 },
      sender, { wallMs: 100, monotonicMs: 50 }) };
  });
  expect(resultado.pareado).toBe(true);
  expect(resultado.sessao).toBe(true);
  expect(resultado.hello).toMatchObject({ tipo: "hello", tab_id: "3", meeting_hint: "abc-defg-hij" });
  expect(resultado.envelope).toMatchObject({ schema_version: 1, session_id: "sessao-sintetica",
    tab_id: "3", meeting_key: "sala-sintetica", kind: "caption", client_wall_ms: 100,
    client_monotonic_ms: 50, caption_id: "c-1", caption_revision: 1 });
  expect(JSON.stringify(resultado.envelope)).not.toMatch(/token|received_monotonic_ns/);
  const valido = await page.evaluate(() => window.validarSenderMeet({
    frameId: 0,
    tab: { id: 3 },
    url: "https://meet.google.com/abc-defg-hij"
  }));
  expect(valido).toBe(true);
  const subframe = await page.evaluate(() => window.validarSenderMeet({
    frameId: 2,
    tab: { id: 3 },
    url: "https://meet.google.com/abc-defg-hij"
  }));
  expect(subframe).toBe(false);
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
    .toContainEqual(expect.objectContaining({
      tipo: "meet-evento",
      evento: expect.objectContaining({ nome: "Pessoa Sintética" })
    }));
});

test("content preserva id e revisão da legenda sem enviar título da aba", async ({ page }) => {
  await page.setContent("<main></main>");
  await page.evaluate(() => {
    window.__eventosMeetTeste = [];
    window.chrome = { runtime: { sendMessage: (msg) => window.__eventosMeetTeste.push(msg) } };
    window.setInterval = () => 0;
    document.title = "TÍTULO-CANÁRIO";
  });
  await page.addScriptTag({ content: parserScript });
  await page.addScriptTag({ content: contentScript });
  await page.evaluate(() => {
    const bloco = document.createElement("section");
    bloco.setAttribute("data-caption-block", "");
    bloco.setAttribute("data-caption-id", "cap-sintetica");
    bloco.setAttribute("data-caption-revision", "4");
    bloco.setAttribute("data-participant-id", "p-caption");
    bloco.innerHTML = '<span data-speaker-name="Pessoa Sintética"></span>' +
      '<span data-caption-text>fala sintética</span>';
    document.body.append(bloco);
  });
  await expect.poll(() => page.evaluate(() => window.__eventosMeetTeste)).toContainEqual(
    expect.objectContaining({ evento: expect.objectContaining({
      caption_id: "cap-sintetica", caption_revision: 4, participant_id: "p-caption",
    }) })
  );
  expect(JSON.stringify(await page.evaluate(() => window.__eventosMeetTeste))).not.toContain("TÍTULO-CANÁRIO");
});

test("content preserva id do participante na atividade", async ({ page }) => {
  await page.setContent("<main></main>");
  await page.evaluate(() => {
    window.__eventosMeetTeste = [];
    window.chrome = { runtime: { sendMessage: (msg) => window.__eventosMeetTeste.push(msg) } };
    window.setInterval = () => 0;
  });
  await page.addScriptTag({ content: parserScript });
  await page.addScriptTag({ content: contentScript });
  await page.evaluate(() => {
    const tile = document.createElement("div");
    tile.setAttribute("data-self-name", "Pessoa Sintética");
    tile.setAttribute("data-requested-participant-id", "p-123");
    document.body.append(tile);
  });
  await expect.poll(() => page.evaluate(() => window.__eventosMeetTeste)).toContainEqual(
    expect.objectContaining({ evento: expect.objectContaining({
      tipo: "ativo", participant_id: "p-123", nome: "Pessoa Sintética",
    }) })
  );
});
