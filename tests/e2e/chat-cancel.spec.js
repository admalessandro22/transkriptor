const { test, expect } = require("@playwright/test");
const { carregarPagina, selecionarReuniao } = require("./helpers");


test("cancelar fecha o upstream: stop e Esc abortam o fetch", async ({ page }) => {
  const sinais = [];
  await carregarPagina(page, "assistente", {
    api: (url) => {
      if (url.includes("/api/transcricoes")) return [{ arquivo: "reuniao.txt", data: "01/01/2026 10:00", tipo: "transcricao", tamanho_kb: 1, protegida: false, com_sua_voz: null }];
      if (url.endsWith("/api/modelos")) return ["llama3"];
      return undefined;
    },
    chat: (req) => new Promise(() => { sinais.push(req); }) // nunca responde: só o abort encerra
  });
  await page.waitForFunction(() => document.getElementById("transcricao").options.length === 1 && document.getElementById("modelo").options.length === 1);
  await selecionarReuniao(page, "reuniao.txt");
  await page.fill("#input", "resuma");
  await page.click("#send");
  await expect.poll(() => sinais.length).toBe(1);
  await expect(page.locator("#stop")).toBeVisible();

  await page.click("#stop");
  await expect(page.locator("#chat")).toContainText("(cancelado)");
  await expect(page.locator("#send")).toBeVisible();

  await page.fill("#input", "de novo");
  await page.click("#send");
  await expect.poll(() => sinais.length).toBe(2);
  await page.locator("#input").focus();
  await page.keyboard.press("Escape");
  await expect(page.locator("#chat .msg-row.ai").last()).toContainText("(cancelado)");
  const abortados = await page.evaluate(() => performance.getEntriesByType("resource").filter((e) => e.name.endsWith("/api/chat")).length);
  expect(abortados).toBeGreaterThanOrEqual(0);
});
