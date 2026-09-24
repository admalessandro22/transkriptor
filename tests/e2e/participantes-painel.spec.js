const { test, expect } = require("@playwright/test");
const { carregarPagina, fixtures } = require("./helpers");


test("falante sem nome aparece como Falante N e VOCÊ mantém o rótulo", async ({ page }) => {
  await carregarPagina(page, "assistente");
  await page.click("#abrir-participantes");
  await expect(page.locator("#participantes-drawer")).toHaveClass(/is-open/);
  await expect(page.locator("#lista-falantes .falante")).toHaveCount(3);
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_00"] .falante__nome')).toContainText("Falante 1");
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_01"] .falante__nome')).toContainText("VOCÊ");
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_02"] .falante__nome')).toContainText("Falante 3");
  await expect(page.locator("#lista-falantes")).not.toContainText("FALANTE_0");
  await expect(page.locator('#correcao-cluster option[value="FALANTE_02"]')).toHaveText("Falante 3");
  await expect(page.locator("#reuniao-revisao")).toHaveText("Revisão 3");
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_00"] .falante__estado')).toContainText("Sugerido");
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_01"] .falante__estado')).toContainText("Confirmado · voz");
});


test("carregando mostra skeleton e some após a carga", async ({ page }) => {
  let liberar = null;
  await carregarPagina(page, "assistente", {
    api: (url) => (url.endsWith("/resultado") ? new Promise((res) => { liberar = () => res(fixtures.resultado()); }) : undefined),
  });
  await page.click("#abrir-participantes");
  await expect(page.locator("#participantes-skeleton")).toBeVisible();
  await expect(page.locator("#participantes-drawer")).toHaveAttribute("aria-busy", "true");
  liberar();
  await expect(page.locator("#participantes-skeleton")).toBeHidden();
  await expect(page.locator("#participantes-drawer")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("#lista-falantes .falante")).toHaveCount(3);
  await expect(page.locator("#participantes-estado")).toHaveText("");
});


test("cores dos falantes são estáveis entre recargas", async ({ page }) => {
  await carregarPagina(page, "assistente");
  await page.click("#abrir-participantes");
  await expect(page.locator("#lista-falantes .falante")).toHaveCount(3);
  const antes = await page.$$eval("#lista-falantes .falante", (els) => els.map((e) => [e.dataset.cluster, e.querySelector(".falante__avatar").dataset.cor]));
  await page.selectOption("#reuniao-participantes", "reuniao-2026-09-22");
  await page.locator("#lista-falantes .falante").first().click();
  await page.selectOption("#reuniao-participantes", "reuniao-2026-09-22");
  await expect(page.locator("#lista-falantes .falante")).toHaveCount(3);
  const depois = await page.$$eval("#lista-falantes .falante", (els) => els.map((e) => [e.dataset.cluster, e.querySelector(".falante__avatar").dataset.cor]));
  expect(depois).toEqual(antes);
  expect(new Set(antes.map((a) => a[1])).size).toBe(3);
});


test("painel empurra o conteúdo em 1366 e sobrepõe em 900", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 800 });
  await carregarPagina(page, "assistente");
  const larguraAntes = await page.locator(".main").evaluate((el) => el.getBoundingClientRect().width);
  await page.click("#abrir-participantes");
  await expect(page.locator("#participantes-drawer")).toHaveClass(/is-open/);
  const larguraDepois = await page.locator(".main").evaluate((el) => el.getBoundingClientRect().width);
  expect(larguraDepois).toBeLessThan(larguraAntes - 300);
  await page.keyboard.press("Escape");
  await expect(page.locator("#abrir-participantes")).toBeFocused();

  await page.setViewportSize({ width: 900, height: 800 });
  const antes900 = await page.locator(".main").evaluate((el) => el.getBoundingClientRect().width);
  await page.click("#abrir-participantes");
  await expect(page.locator("#participantes-drawer")).toHaveClass(/is-open/);
  const depois900 = await page.locator(".main").evaluate((el) => el.getBoundingClientRect().width);
  expect(depois900).toBe(antes900);
  const estouro = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(estouro).toBeLessThanOrEqual(1);
});


test("página Participantes lista falantes e falas em duas colunas", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 800 });
  const ctx = await carregarPagina(page, "participantes");
  await expect(page.locator("#lista-falantes .falante")).toHaveCount(3);
  await expect(page.locator("#lista-participantes .fala")).toHaveCount(4);
  await expect(page.locator("#reuniao-revisao")).toHaveText("Revisão 3");
  const colunas = await page.locator("#participantes-drawer").evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length);
  expect(colunas).toBe(2);
  expect(ctx.violacoes).toEqual([]);
});
