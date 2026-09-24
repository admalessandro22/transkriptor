const { test, expect } = require("@playwright/test");
const { carregarPagina, fixtures } = require("./helpers");


for (const largura of [375, 900, 1366, 1920]) {
  test(`marca aparece uma vez e nada estoura em ${largura} px`, async ({ page }) => {
    await page.setViewportSize({ width: largura, height: 800 });
    const ctx = await carregarPagina(page, "assistente");
    await page.waitForFunction(() => document.getElementById("modelo").options.length > 0);
    const marcas = await page.evaluate(() => [...document.querySelectorAll("*")].filter((el) => el.children.length === 0 && el.textContent.trim() === "Transkriptor").length);
    expect(marcas).toBe(1);
    const estouro = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(estouro).toBeLessThanOrEqual(1);
    expect(ctx.violacoes).toEqual([]);
  });
}


test("statusbar mostra o rótulo do glossário vindo de /api/estado", async ({ page }) => {
  await carregarPagina(page, "assistente", { api: (url) => (url.endsWith("/api/estado") ? fixtures.estado("gravando") : undefined) });
  await expect(page.locator("#statusbar")).toHaveAttribute("data-estado", "gravando");
  await expect(page.locator("#statusbar")).toContainText("Gravando");
  await expect(page.locator("#statusbar")).toContainText("titulo, microfone");
});


test("503 em /api/estado não gera toast e marca a barra como indisponível", async ({ page }) => {
  await carregarPagina(page, "assistente", { api: (url) => (url.endsWith("/api/estado") ? { status: 503, body: JSON.stringify({ erro: "estado indisponível" }) } : undefined) });
  await page.waitForTimeout(300);
  await expect(page.locator("#statusbar")).toHaveAttribute("data-estado", "indisponivel");
  await expect(page.locator("#statusbar")).toContainText("Central sem bandeja");
  await expect(page.locator("#toast-region .tk-toast, #toast-region .toast")).toHaveCount(0);
});


test("polling para com a aba oculta e retoma ao voltar", async ({ page }) => {
  let chamadas = 0;
  await carregarPagina(page, "assistente", { api: (url) => { if (url.endsWith("/api/estado")) { chamadas++; return fixtures.estado("aguardando"); } return undefined; } });
  await expect.poll(() => chamadas).toBeGreaterThanOrEqual(1);
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  const antes = chamadas;
  await page.waitForTimeout(2600);
  expect(chamadas).toBe(antes);
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => chamadas).toBeGreaterThan(antes);
});


test("tema persiste após recarregar e o item ativo da nav é o Assistente", async ({ page }) => {
  await carregarPagina(page, "assistente");
  await expect(page.locator('.tk-nav__item[data-page="assistente"]')).toHaveAttribute("aria-current", "page");
  const antes = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  await page.click("#tema-toggle");
  const depois = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(depois).not.toBe(antes);
  await page.reload();
  await page.waitForSelector("#statusbar");
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe(depois);
});


test("Tab percorre nav, conteúdo e composer; nav vira drawer em 900 px", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 800 });
  await carregarPagina(page, "assistente");
  await page.waitForFunction(() => document.getElementById("modelo").options.length > 0);
  // O assistente foca o campo ao carregar; a ordem é verificada a partir do link de salto.
  await page.locator(".tk-skip").focus();
  await page.keyboard.press("Tab");
  await expect(page.locator('.tk-nav__item[data-page="inicio"]')).toBeFocused();
  for (let i = 0; i < 5; i++) await page.keyboard.press("Tab");
  await expect(page.locator('.tk-nav__item[data-page="diagnostico"]')).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#tema-toggle")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#busca-transcricao")).toBeFocused();
  await page.locator("#input").focus();
  await expect(page.locator("#input")).toBeFocused();

  await page.setViewportSize({ width: 860, height: 800 });
  await expect(page.locator("#nav-toggle")).toBeVisible();
  await page.click("#nav-toggle");
  await expect(page.locator("#nav")).toHaveClass(/is-open/);
  await page.keyboard.press("Escape");
  await expect(page.locator("#nav")).not.toHaveClass(/is-open/);
  await expect(page.locator("#nav-toggle")).toBeFocused();
});


test("página inexistente responde com o shell e caminho de volta", async ({ page }) => {
  await carregarPagina(page, "indisponivel");
  await expect(page.locator(".tk-empty__titulo")).toContainText("ainda não existe");
  await expect(page.locator('a.tk-btn[href="/"]')).toBeVisible();
});
