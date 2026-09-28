const { test, expect } = require("@playwright/test");
const { carregarPagina } = require("./helpers");

const COMPONENTES = ["tk-btn", "tk-field", "tk-listbox", "tk-badge", "tk-statusbar", "tk-toast", "tk-dialog", "tk-panel", "tk-skeleton", "tk-empty", "tk-row", "tk-progress", "tk-chip", "tk-card"];


for (const tema of ["dark", "light"]) {
  test.describe(`tema ${tema}`, () => {
    test.use({ colorScheme: tema, viewport: { width: 1366, height: 900 } });

    test("todos os componentes presentes e sem violação de CSP", async ({ page }) => {
      const ctx = await carregarPagina(page, "galeria");
      for (const c of COMPONENTES) {
        await expect(page.locator(`section[data-componente="${c}"]`)).toHaveCount(1);
      }
      await expect(page.locator(".tk-badge-state")).toHaveCount(8);
      await expect(page.locator(".tk-statusbar")).toHaveCount(7);
      await page.waitForTimeout(300);
      expect(ctx.violacoes).toEqual([]);
      const efetivo = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      expect(efetivo).toBe(tema === "dark" ? "rgb(15, 17, 21)" : "rgb(245, 246, 248)");
    });

    test("snapshot visual por componente", async ({ page }) => {
      await carregarPagina(page, "galeria");
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.waitForTimeout(200);
      for (const c of COMPONENTES) {
        if (c === "tk-dialog" || c === "tk-panel" || c === "tk-skeleton" || c === "tk-progress") continue;
        // A barra clara concentra texto: o rasterizador do runner Windows varia nas bordas das letras.
        const maxDiffPixelRatio = tema === "light" && c === "tk-statusbar" ? 0.04 : 0.02;
        await expect(page.locator(`section[data-componente="${c}"]`)).toHaveScreenshot(`${c}-${tema}.png`, { maxDiffPixelRatio });
      }
    });
  });
}


test("diálogo foca o botão seguro, Esc cancela e confirmar resolve true", async ({ page }) => {
  await carregarPagina(page, "galeria");
  await page.click("#abrir-dialogo");
  const dlg = page.locator("#dialogo-confirmacao");
  await expect(dlg).toBeVisible();
  await expect(dlg.locator('[data-acao="cancelar"]')).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dlg).toBeHidden();
  await expect(page.locator("#dialogo-resultado")).toHaveText("Cancelado");
  await expect(page.locator("#abrir-dialogo")).toBeFocused();
  await page.click("#abrir-dialogo-perigo");
  await expect(dlg).toHaveClass(/tk-dialog--perigo/);
  await expect(dlg.locator('[data-acao="confirmar"]')).toHaveClass(/tk-btn--danger/);
  await dlg.locator('[data-acao="confirmar"]').click();
  await expect(page.locator("#dialogo-resultado")).toHaveText("Confirmado");
});


test("painel prende o Tab e restaura o foco ao fechar", async ({ page }) => {
  await carregarPagina(page, "galeria");
  await page.click("#abrir-painel");
  const painel = page.locator("#painel-demo");
  await expect(painel).toHaveClass(/is-open/);
  await expect(page.locator("#fechar-painel")).toBeFocused();
  for (let i = 0; i < 6; i++) await page.keyboard.press("Tab");
  const dentro = await page.evaluate(() => document.getElementById("painel-demo").contains(document.activeElement));
  expect(dentro).toBe(true);
  await page.keyboard.press("Escape");
  await expect(painel).toBeHidden();
  await expect(page.locator("#abrir-painel")).toBeFocused();
});


test("toast de erro persiste e info fecha sozinho", async ({ page }) => {
  await carregarPagina(page, "galeria");
  await page.click('[data-toast="error"]');
  await page.click('[data-toast="info"]');
  const regiao = page.locator("#toast-region");
  await expect(regiao.locator(".tk-toast--error")).toHaveCount(1);
  await expect(regiao.locator(".tk-toast--info")).toHaveCount(1);
  await expect(regiao.locator(".tk-toast--error")).toHaveAttribute("role", "alert");
  await page.waitForTimeout(4600);
  await expect(regiao.locator(".tk-toast--info")).toHaveCount(0);
  await expect(regiao.locator(".tk-toast--error")).toHaveCount(1);
  await regiao.locator(".tk-toast--error .tk-toast__fechar").click();
  await expect(regiao.locator(".tk-toast--error")).toHaveCount(0);
});


test("tema alternado persiste após recarregar", async ({ page }) => {
  await carregarPagina(page, "galeria");
  const antes = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  await page.click("#tema-toggle");
  const depois = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(depois).not.toBe(antes);
  await page.reload();
  await page.waitForSelector("#galeria");
  const recarregado = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(recarregado).toBe(depois);
});
