const { test, expect } = require("@playwright/test");
const { carregarPagina, selecionarReuniao } = require("./helpers");


test("carregar o assistente sob a CSP normativa não gera violação", async ({ page }) => {
  const ctx = await carregarPagina(page, "assistente");
  await page.waitForFunction(() => document.getElementById("modelo").options.length > 0);
  await page.waitForTimeout(300);
  expect(ctx.violacoes).toEqual([]);
});


test("botão parar fica oculto ao carregar e visível só durante a geração", async ({ page }) => {
  const liberar = { fn: null };
  await carregarPagina(page, "assistente", {
    chat: () => new Promise((res) => { liberar.fn = () => res("resposta"); })
  });
  await page.waitForFunction(() => document.getElementById("transcricao").options.length > 0);
  await expect(page.locator("#stop")).toBeHidden();
  await expect(page.locator("#timer")).toBeHidden();
  await expect(page.locator("#send")).toBeVisible();
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await page.fill("#input", "resuma");
  await page.click("#send");
  await expect(page.locator("#stop")).toBeVisible();
  await expect(page.locator("#send")).toBeHidden();
  await page.click("#stop");
  await expect(page.locator("#stop")).toBeHidden();
  await expect(page.locator("#send")).toBeVisible();
});


test("nenhuma requisição sai de 127.0.0.1", async ({ page }) => {
  const externas = [];
  page.on("request", (r) => { if (!r.url().startsWith("http://127.0.0.1:5050")) externas.push(r.url()); });
  await carregarPagina(page, "assistente");
  await page.waitForFunction(() => document.getElementById("modelo").options.length > 0);
  expect(externas).toEqual([]);
});
