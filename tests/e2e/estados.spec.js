const { test, expect } = require("@playwright/test");
const { carregarPagina, selecionarReuniao } = require("./helpers");


test("ollama offline mostra cartão no lugar do composer e não dispara toast", async ({ page }) => {
  await carregarPagina(page, "assistente", { api: (url) => (url.endsWith("/api/modelos") ? [] : undefined) });
  await page.waitForFunction(() => document.getElementById("transcricao").options.length > 0);
  await expect(page.locator("#ollama-offline")).toBeVisible();
  await expect(page.locator("#ollama-offline")).toContainText("Ollama não está em execução");
  await expect(page.locator("#ollama-offline .tk-btn")).toContainText("Tentar de novo");
  await expect(page.locator(".input-area")).toBeHidden();
  await expect(page.locator("#chips")).toBeHidden();
  await page.waitForTimeout(300);
  await expect(page.locator("#toast-region .tk-toast")).toHaveCount(0);
});


test("tentar de novo recarrega os modelos e devolve o composer", async ({ page }) => {
  let online = false;
  const ctx = await carregarPagina(page, "assistente", { api: (url) => (url.endsWith("/api/modelos") ? (online ? ["llama3"] : []) : undefined) });
  await expect(page.locator("#ollama-offline")).toBeVisible();
  online = true;
  await page.locator("#ollama-offline .tk-btn").click();
  await expect(page.locator("#ollama-offline")).toBeHidden();
  await expect(page.locator(".input-area")).toBeVisible();
  await expect(page.locator("#modelo")).toHaveValue("llama3");
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/api/modelos")).length).toBe(2);
});


test("erro de lista não vira item e o skeleton some após a carga", async ({ page }) => {
  let falhar = true;
  const ctx = await carregarPagina(page, "assistente", { api: (url) => (url.includes("/api/transcricoes") && falhar ? { status: 500, body: "{}" } : undefined) });
  await expect(page.locator("#transcricao")).toHaveClass(/is-error/);
  await expect(page.locator('#transcricao [role="option"]')).toHaveCount(0);
  await expect(page.locator("#transcricao .tk-listbox__estado .tk-btn")).toContainText("Tentar de novo");
  falhar = false;
  await page.locator("#transcricao .tk-listbox__estado .tk-btn").click();
  await expect(page.locator("#transcricao .tk-skeleton")).toHaveCount(0);
  await expect(page.locator('#transcricao [role="option"]')).toHaveCount(3);
  await expect(page.locator("#transcricao")).not.toHaveAttribute("aria-busy", "true");
  expect(ctx.violacoes).toEqual([]);
});


test("falha de rede na resposta vira cartão com Tentar de novo que reenvia", async ({ page }) => {
  let falhar = true;
  const ctx = await carregarPagina(page, "assistente", {
    api: (url) => (url.endsWith("/api/chat") && falhar ? { status: 503, body: JSON.stringify({ erro: "Ollama indisponível" }) } : undefined),
    chat: () => (falhar ? { status: 503, body: JSON.stringify({ erro: "Ollama indisponível" }) } : "resposta ok"),
  });
  await page.waitForFunction(() => document.getElementById("transcricao").options.length > 0 && document.getElementById("modelo").options.length > 0);
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await page.fill("#input", "oi");
  await page.click("#send");
  const cartao = page.locator("#chat .msg-erro");
  await expect(cartao).toBeVisible();
  await expect(cartao).toContainText("Ollama indisponível");
  await expect(cartao.locator(".tk-btn")).toContainText("Tentar de novo");
  falhar = false;
  await cartao.locator(".tk-btn").click();
  await expect(page.locator("#chat")).toContainText("resposta ok");
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/api/chat")).length).toBe(2);
});


test("transcrição longa mostra aviso inline com próximo passo, sem toast", async ({ page }) => {
  await carregarPagina(page, "assistente");
  await page.waitForFunction(() => document.getElementById("transcricao").options.length > 0);
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await expect(page.locator("#ctx-hint")).toContainText("Transcrição longa");
  await expect(page.locator("#ctx-hint")).toContainText("blocos");
  await expect(page.locator("#toast-region .tk-toast")).toHaveCount(0);
  await selecionarReuniao(page, "2026-09-18_15h30.txt");
  await expect(page.locator("#ctx-hint")).toBeHidden();
});
