const { test, expect } = require("@playwright/test");
const { carregarPagina, selecionarReuniao, fixtures } = require("./helpers");


async function pronto(page) {
  await page.waitForFunction(() => document.getElementById("transcricao").options.length > 0 && document.getElementById("modelo").options.length > 0);
}


test("chip envia a intenção sem colar o prompt no campo", async ({ page }) => {
  const ctx = await carregarPagina(page, "assistente");
  await pronto(page);
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await expect(page.locator("#chips .tk-chip")).toHaveCount(6);
  await page.locator('#chips .tk-chip[data-intent="resumir"]').click();
  await expect(page.locator("#chat")).toContainText("Resumo executivo");
  const pedido = ctx.pedidos.find((p) => p.url.endsWith("/api/chat"));
  const corpo = JSON.parse(pedido.corpo);
  expect(corpo.pergunta).toContain("resumo executivo");
  await expect(page.locator("#input")).toHaveValue("");
  await expect(page.locator("#chat .msg-row.user .bubble")).toContainText("Atue como um analista");
});


test("modo editar mostra o prompt no campo antes de enviar", async ({ page }) => {
  const ctx = await carregarPagina(page, "assistente");
  await pronto(page);
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await page.click("#chips-editar");
  await expect(page.locator("#chips-editar")).toHaveAttribute("aria-pressed", "true");
  await page.locator('#chips .tk-chip[data-intent="decisoes"]').click();
  await expect(page.locator("#input")).toHaveValue(/analista de negócios/);
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/api/chat"))).toHaveLength(0);
});


test("markdown com tabela renderiza como table e o streaming não salta ao concluir", async ({ page }) => {
  let liberar = null;
  const partes = ["## Resumo executivo\n\n| Tarefa | Prazo |\n|---|---|\n| Integ", "ração | sexta |\n\n- risco"];
  await carregarPagina(page, "assistente", {
    chat: () => new Promise((res) => { liberar = () => res(partes.join("")); }),
  });
  await pronto(page);
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await page.fill("#input", "tarefas");
  await page.click("#send");
  await expect(page.locator("#stop")).toBeVisible();
  liberar();
  await expect(page.locator("#chat table")).toHaveCount(1);
  await expect(page.locator("#chat th").first()).toHaveText("Tarefa");
  await expect(page.locator("#chat td").nth(1)).toHaveText("sexta");
  await expect(page.locator("#chat .msg-row.ai .msg-copy")).toBeVisible();
  const altura1 = await page.locator("#chat .msg-row.ai").last().evaluate((el) => el.getBoundingClientRect().height);
  await page.waitForTimeout(300);
  const altura2 = await page.locator("#chat .msg-row.ai").last().evaluate((el) => el.getBoundingClientRect().height);
  expect(altura2).toBe(altura1);
});


test("copiar negado mostra erro na mensagem e reenviar repete a pergunta", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new DOMException("negado", "NotAllowedError")) }, configurable: true });
  });
  const ctx = await carregarPagina(page, "assistente");
  await pronto(page);
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await page.fill("#input", "primeira");
  await page.click("#send");
  await expect(page.locator("#chat .msg-row.ai .msg-copy").first()).toBeVisible();
  await page.locator("#chat .msg-row.ai .msg-copy").first().click();
  await expect(page.locator("#chat .msg-row.ai .msg-copy").first()).toContainText("Erro ao copiar");
  await page.locator('#chat .msg-row.user [data-acao="reenviar"]').first().click();
  await expect.poll(() => ctx.pedidos.filter((p) => p.url.endsWith("/api/chat")).length).toBe(2);
});


test("estado vazio de primeiro uso tem três passos e a coluna de leitura é limitada em 1920", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1000 });
  await carregarPagina(page, "assistente");
  await pronto(page);
  await expect(page.locator("#empty .empty-passos li")).toHaveCount(3);
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await page.fill("#input", "oi");
  await page.click("#send");
  await expect(page.locator("#chat .msg-row.ai .bubble")).toContainText("Resumo executivo");
  const largura = await page.locator("#chat .msg-row.ai").last().evaluate((el) => el.getBoundingClientRect().width);
  expect(largura).toBeLessThanOrEqual(900);
});


test("setas navegam entre os chips e Escape cancela a geração", async ({ page }) => {
  let liberar = null;
  await carregarPagina(page, "assistente", { chat: () => new Promise((res) => { liberar = () => res("x"); }) });
  await pronto(page);
  await page.locator('#chips .tk-chip[data-intent="resumir"]').focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator('#chips .tk-chip[data-intent="pontos"]')).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(page.locator('#chips .tk-chip[data-intent="resumir"]')).toBeFocused();
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await page.fill("#input", "lenta");
  await page.click("#send");
  await expect(page.locator("#stop")).toBeVisible();
  await page.locator("#input").focus();
  await page.keyboard.press("Escape");
  await expect(page.locator("#chat")).toContainText("(cancelado)");
  await expect(page.locator("#send")).toBeVisible();
  if (liberar) liberar();
});
