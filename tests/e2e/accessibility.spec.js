const { test, expect } = require("@playwright/test");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");


const raiz = resolve(__dirname, "../..");
const modelo = readFileSync(resolve(raiz, "templates/assistente.html"), "utf8")
  .replace(/\{\{[^}]*\}\}/g, "#");
const js = readFileSync(resolve(raiz, "static/assistente.js"), "utf8");


async function carregar(page, roteador) {
  await page.setContent(modelo);
  await page.evaluate((temRoteador) => {
    window.__roteador = temRoteador;
    window.fetch = async (url, opc) => {
      if (String(url).endsWith("/api/transcricoes")) {
        return { ok: true, json: async () => [
          { arquivo: "a.txt", data: "01/01", tipo: "transcricao", tamanho_kb: 1, preview: "fala A", com_sua_voz: false },
          { arquivo: "b.txt", data: "02/01", tipo: "transcricao", tamanho_kb: 2, preview: "fala B", com_sua_voz: false }
        ] };
      }
      if (String(url).endsWith("/api/modelos")) {
        return { ok: true, json: async () => ["llama3"] };
      }
      if (String(url).endsWith("/api/chat")) {
        const bytes = new TextEncoder().encode("resposta acessivel");
        return {
          ok: true,
          body: { getReader: () => {
            let feito = false;
            return { read: async () => {
              if (feito) return { done: true, value: undefined };
              feito = true;
              return { done: false, value: bytes };
            } };
          } }
        };
      }
      if (String(url).endsWith("/api/reunioes")) {
        return { ok: true, json: async () => ["reuniao-x"] };
      }
      if (String(url).endsWith("/resultado")) {
        return { ok: true, json: async () => ({
          schema_version: 1, revision: "rev-1",
          segmentos: [
            { segment_id: "s1", start_ms: 0, end_ms: 1000, audio_source: "loopback", text: "bom dia", speaker_cluster_id: "FALANTE_00", overlap: false }
          ],
          mapeamento: {}, historico: []
        }) };
      }
      return { ok: true, json: async () => ({}) };
    };
    if (!window.navigator.clipboard) {
      Object.defineProperty(window.navigator, "clipboard", {
        value: {
          writeText: () => {
            if (window.__roteador === "clipboard-negado") {
              return Promise.reject(new DOMException("negado", "NotAllowedError"));
            }
            window.__colado = true;
            return Promise.resolve();
          }
        },
        configurable: true
      });
    } else {
      const original = window.navigator.clipboard.writeText.bind(window.navigator.clipboard);
      window.navigator.clipboard.writeText = (t) => {
        if (window.__roteador === "clipboard-negado") {
          return Promise.reject(new DOMException("negado", "NotAllowedError"));
        }
        return original(t);
      };
    }
  }, roteador || null);
  await page.addScriptTag({ content: js });
  await page.waitForFunction(() => document.getElementById("transcricao").options.length === 2);
}


test("foco entra no drawer, circula dentro e volta ao fechar", async ({ page }) => {
  await carregar(page);
  await page.click("#abrir-participantes");
  await expect(page.locator("#reuniao-participantes")).toBeFocused();
  await expect(page.locator("#reuniao-revisao")).toContainText("rev-1");
  const ordem = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    ordem.push(await page.evaluate(() => document.activeElement.id || document.activeElement.tagName));
  }
  expect(ordem.every((id) => id !== "BODY")).toBe(true);
  await page.keyboard.press("Escape");
  await expect(page.locator("#abrir-participantes")).toBeFocused();
});


test("clipboard negado mostra erro visivel", async ({ page }) => {
  await carregar(page, "clipboard-negado");
  await page.evaluate(() => {
    const sel = document.getElementById("transcricao");
    sel.value = "a.txt";
    document.getElementById("input").value = "oi";
  });
  await page.click("#send");
  await page.waitForFunction(() => !document.getElementById("copiar-resposta").disabled);
  await page.click("#copiar-resposta");
  await expect(page.locator("#copiar-resposta")).toContainText("Erro ao copiar");
});


test("filtro preserva selecao e telas nao estouram", async ({ page }) => {
  await carregar(page);
  await page.selectOption("#transcricao", "b.txt");
  await page.fill("#busca-transcricao", "fala B");
  await expect(page.locator("#transcricao")).toHaveValue("b.txt");
  for (const largura of [375, 860, 1366]) {
    await page.setViewportSize({ width: largura, height: 800 });
    await page.click("#abrir-participantes");
    const estouro = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(estouro).toBeLessThanOrEqual(1);
    await page.click("#fechar-participantes");
  }
});
