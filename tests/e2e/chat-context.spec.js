const { test, expect } = require("@playwright/test");
const { carregarPagina, selecionarReuniao } = require("./helpers");


const REUNIOES = [
  { arquivo: "a.txt", data: "01/01/2026 10:00", tipo: "transcricao", tamanho_kb: 1, protegida: false, com_sua_voz: null },
  { arquivo: "b.txt", data: "02/01/2026 10:00", tipo: "transcricao", tamanho_kb: 2, protegida: false, com_sua_voz: null }
];


async function carregar(page, modo = { tipo: "instantaneo" }) {
  const controle = { liberar: null };
  const ctx = await carregarPagina(page, "assistente", {
    api: (url) => {
      if (url.includes("/api/transcricoes")) return REUNIOES;
      if (url.endsWith("/api/modelos")) return ["llama3"];
      return undefined;
    },
    chat: (req) => {
      const texto = "resposta sobre " + JSON.parse(req.postData()).pergunta;
      if (modo.tipo === "instantaneo") return texto;
      return new Promise((res) => { controle.liberar = () => res(texto); });
    }
  });
  await page.waitForFunction(() => document.getElementById("transcricao").options.length === 2 && document.getElementById("modelo").options.length === 1);
  ctx.pedidosChat = () => ctx.pedidos.filter((p) => p.url.endsWith("/api/chat")).map((p) => JSON.parse(p.corpo));
  ctx.controle = controle;
  return ctx;
}


async function perguntar(page, texto) {
  await page.fill("#input", texto);
  await page.click("#send");
}


test("12a pergunta recebe resposta (janela respeita orcamento)", async ({ page }) => {
  const ctx = await carregar(page);
  await selecionarReuniao(page, "a.txt");
  for (let i = 1; i <= 12; i++) {
    await perguntar(page, "pergunta " + i);
    await expect(page.locator("#chat")).toContainText("resposta sobre pergunta " + i);
  }
  const ultimo = ctx.pedidosChat().at(-1);
  expect(ultimo.meeting_id).toBe("a.txt");
  expect(ultimo.historico.length).toBeLessThanOrEqual(20);
  expect(typeof ultimo.generation_id).toBe("string");
});


test("A para B nao mistura historico nem DOM", async ({ page }) => {
  const ctx = await carregar(page);
  await selecionarReuniao(page, "a.txt");
  await perguntar(page, "conteudo exclusivo A");
  await expect(page.locator("#chat")).toContainText("conteudo exclusivo A");

  await selecionarReuniao(page, "b.txt");
  await expect(page.locator("#chat")).not.toContainText("conteudo exclusivo A");
  await perguntar(page, "pergunta B");
  await expect(page.locator("#chat")).toContainText("resposta sobre pergunta B");
  const ultimo = ctx.pedidosChat().at(-1);
  expect(ultimo.meeting_id).toBe("b.txt");
  expect(JSON.stringify(ultimo.historico)).not.toContain("conteudo exclusivo A");
});


test("stream tardio de A nao aparece em B", async ({ page }) => {
  const ctx = await carregar(page, { tipo: "lento" });
  await selecionarReuniao(page, "a.txt");
  await page.fill("#input", "pergunta lenta A");
  await page.click("#send");
  await expect.poll(() => ctx.pedidosChat().length).toBe(1);
  await selecionarReuniao(page, "b.txt");
  if (ctx.controle.liberar) ctx.controle.liberar();
  await page.waitForTimeout(300);
  await expect(page.locator("#chat")).not.toContainText("resposta sobre pergunta lenta A");
});


test("limpar durante geracao nao reintroduz resposta", async ({ page }) => {
  const ctx = await carregar(page, { tipo: "lento" });
  await selecionarReuniao(page, "a.txt");
  await page.fill("#input", "pergunta para limpar");
  await page.click("#send");
  await expect.poll(() => ctx.pedidosChat().length).toBe(1);
  await page.click("#limpar");
  if (ctx.controle.liberar) ctx.controle.liberar();
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
