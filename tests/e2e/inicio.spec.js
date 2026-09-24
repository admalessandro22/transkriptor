const { test, expect } = require("@playwright/test");
const { carregarPagina, fixtures } = require("./helpers");


test("cartões refletem o estado, a última reunião e a proteção", async ({ page }) => {
  const ctx = await carregarPagina(page, "inicio", { api: (url) => (url.endsWith("/api/estado") ? fixtures.estado("gravando") : undefined) });
  await expect(page.locator("#inicio-estado")).toHaveAttribute("data-estado", "gravando");
  await expect(page.locator("#inicio-estado-valor")).toHaveText("Gravando");
  await expect(page.locator("#inicio-estado-detalhe")).toContainText("Sinal de: titulo, microfone");
  await expect(page.locator("#inicio-ultima-valor")).toHaveText("22/09 · 10:03");
  await expect(page.locator("#inicio-ultima-detalhe")).toContainText("Pronta");
  await expect(page.locator("#inicio-protecao-valor")).toHaveText("Protegida");
  await expect(page.locator("#inicio-recentes .tk-row")).toHaveCount(3);
  await expect(page.locator("#inicio-recentes")).not.toContainText("Bom dia");
  await expect(page.locator('.tk-nav__item[data-page="inicio"]')).toHaveAttribute("aria-current", "page");
  expect(ctx.violacoes).toEqual([]);
});


test("sem bandeja: cartão explica e nada quebra", async ({ page }) => {
  await carregarPagina(page, "inicio", { api: (url) => (url.endsWith("/api/estado") ? { status: 503, body: JSON.stringify({ erro: "estado indisponível" }) } : undefined) });
  await page.waitForTimeout(300);
  await expect(page.locator("#inicio-estado")).toHaveAttribute("data-estado", "indisponivel");
  await expect(page.locator("#inicio-estado-valor")).toHaveText("Central sem bandeja");
  await expect(page.locator("#inicio-estado-detalhe")).toContainText("bandeja");
  await expect(page.locator("#toast-region .tk-toast")).toHaveCount(0);
  await expect(page.locator("#inicio-recentes .tk-row")).toHaveCount(3);
});


test("polling para com a aba oculta e retoma ao voltar; cartão muda com o estado", async ({ page }) => {
  let estado = "aguardando";
  let chamadas = 0;
  await carregarPagina(page, "inicio", { api: (url) => { if (url.endsWith("/api/estado")) { chamadas++; return fixtures.estado(estado); } return undefined; } });
  await expect(page.locator("#inicio-estado")).toHaveAttribute("data-estado", "aguardando");
  estado = "pausado";
  await expect(page.locator("#inicio-estado")).toHaveAttribute("data-estado", "pausado", { timeout: 5000 });
  await expect(page.locator("#inicio-estado-detalhe")).toContainText("pausada");
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


test("índice vazio orienta o primeiro uso", async ({ page }) => {
  await carregarPagina(page, "inicio", { api: (url) => (url.includes("/api/reunioes-indice") ? { reunioes: [], proximo: null } : undefined) });
  await expect(page.locator("#inicio-recentes-estado")).toContainText("Nenhuma reunião ainda");
  await expect(page.locator("#inicio-recentes")).toBeHidden();
});
