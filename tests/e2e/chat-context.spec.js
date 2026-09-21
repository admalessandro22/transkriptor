const { test, expect } = require("@playwright/test");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");


const raiz = resolve(__dirname, "../..");
const modelo = readFileSync(resolve(raiz, "templates/assistente.html"), "utf8")
  .replace(/\{\{[^}]*\}\}/g, "#");
const js = readFileSync(resolve(raiz, "static/assistente.js"), "utf8");


async function carregar(page, modoChat) {
  await page.setContent(modelo);
  await page.evaluate((modo) => {
    window.__pedidos = [];
    window.__modoChat = modo || { tipo: "instantaneo" };
    window.__liberarStream = null;
    window.fetch = async (url, opc) => {
      if (String(url).endsWith("/api/transcricoes")) {
        return { ok: true, json: async () => [
          { arquivo: "a.txt", data: "01/01", tipo: "transcricao", tamanho_kb: 1, preview: "fala A", com_sua_voz: false },
          { arquivo: "b.txt", data: "02/01", tipo: "transcricao", tamanho_kb: 2, preview: "fala B", com_sua_voz: false }
        ] };
      }
      if (String(url).endsWith("/api/modelos")) {
        return { ok: true, json: async () => [] };
      }
      if (String(url).endsWith("/api/chat")) {
        const corpo = JSON.parse(opc.body);
        window.__pedidos.push(corpo);
        const texto = "resposta sobre " + corpo.pergunta;
        if (window.__modoChat.tipo === "instantaneo") {
          const bytes = new TextEncoder().encode(texto);
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
        return {
          ok: true,
          body: { getReader: () => ({ read: () => new Promise((res) => {
            window.__liberarStream = () => res({ done: false, value: new TextEncoder().encode(texto) });
          }) }) }
        };
      }
      return { ok: true, json: async () => ({}) };
    };
  }, modoChat);
  await page.addScriptTag({ content: js });
  await page.waitForFunction(() => document.getElementById("transcricao").options.length === 2);
  await page.evaluate(() => {
    const sel = document.getElementById("modelo");
    const op = document.createElement("option");
    op.value = "llama3";
    op.textContent = "llama3";
    sel.appendChild(op);
    sel.value = "llama3";
  });
}


async function perguntar(page, texto) {
  await page.fill("#input", texto);
  await page.click("#send");
}


test("12a pergunta recebe resposta (janela respeita orcamento)", async ({ page }) => {
  await carregar(page);
  await page.selectOption("#transcricao", "a.txt");
  for (let i = 1; i <= 12; i++) {
    await perguntar(page, "pergunta " + i);
    await expect(page.locator("#chat")).toContainText("resposta sobre pergunta " + i);
  }
  const ultimo = await page.evaluate(() => window.__pedidos.at(-1));
  expect(ultimo.meeting_id).toBe("a.txt");
  expect(ultimo.historico.length).toBeLessThanOrEqual(20);
  expect(typeof ultimo.generation_id).toBe("string");
});


test("A para B nao mistura historico nem DOM", async ({ page }) => {
  await carregar(page);
  await page.selectOption("#transcricao", "a.txt");
  await perguntar(page, "conteudo exclusivo A");
  await expect(page.locator("#chat")).toContainText("conteudo exclusivo A");

  await page.selectOption("#transcricao", "b.txt");
  await expect(page.locator("#chat")).not.toContainText("conteudo exclusivo A");
  await perguntar(page, "pergunta B");
  const ultimo = await page.evaluate(() => window.__pedidos.at(-1));
  expect(ultimo.meeting_id).toBe("b.txt");
  const junta = JSON.stringify(ultimo.historico);
  expect(junta).not.toContain("conteudo exclusivo A");
});


test("stream tardio de A nao aparece em B", async ({ page }) => {
  await carregar(page, { tipo: "lento" });
  await page.selectOption("#transcricao", "a.txt");
  await page.fill("#input", "pergunta lenta A");
  await page.click("#send");
  await page.waitForFunction(() => window.__pedidos.length === 1);
  await page.selectOption("#transcricao", "b.txt");
  await page.evaluate(() => window.__liberarStream && window.__liberarStream());
  await page.waitForTimeout(300);
  await expect(page.locator("#chat")).not.toContainText("resposta sobre pergunta lenta A");
});


test("limpar durante geracao nao reintroduz resposta", async ({ page }) => {
  await carregar(page, { tipo: "lento" });
  await page.selectOption("#transcricao", "a.txt");
  await page.fill("#input", "pergunta para limpar");
  await page.click("#send");
  await page.waitForFunction(() => window.__pedidos.length === 1);
  await page.click("#limpar");
  await page.evaluate(() => window.__liberarStream && window.__liberarStream());
  await page.waitForTimeout(300);
  await expect(page.locator("#chat")).not.toContainText("resposta sobre pergunta para limpar");
});


test("pergunta digitada sobrevive a validacao reprovada", async ({ page }) => {
  await carregar(page);
  await page.evaluate(() => {
    document.getElementById("modelo").innerHTML = "";
    document.getElementById("modelo").value = "";
  });
  await page.fill("#input", "nao apague isto");
  await page.click("#send");
  await expect(page.locator("#input")).toHaveValue("nao apague isto");
});
