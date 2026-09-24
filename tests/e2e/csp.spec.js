const { test, expect } = require("@playwright/test");
const { carregarPagina, selecionarReuniao, ORIGEM } = require("./helpers");


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


// NFR-14.F2: todas as páginas da Central e a galeria, nos dois temas, sem
// nenhuma requisição fora de 127.0.0.1 e sem violação de CSP no console.
for (const pagina of ["inicio", "reunioes", "assistente", "participantes", "configuracoes", "diagnostico", "galeria"]) {
  test(`nenhuma requisicao externa em todas as paginas: ${pagina}`, async ({ page }) => {
    const externas = [];
    page.on("request", (r) => { if (!r.url().startsWith(ORIGEM)) externas.push(r.url()); });
    const ctx = await carregarPagina(page, pagina);
    await page.waitForTimeout(500);
    await page.emulateMedia({ colorScheme: "light" });
    await page.waitForTimeout(200);
    expect(externas).toEqual([]);
    expect(ctx.violacoes).toEqual([]);
    const falhas404 = ctx.console.filter((t) => /404|Failed to load resource/.test(t));
    expect(falhas404).toEqual([]);
  });
}


test("nenhuma requisição sai de 127.0.0.1", async ({ page }) => {
  const externas = [];
  page.on("request", (r) => { if (!r.url().startsWith("http://127.0.0.1:5050")) externas.push(r.url()); });
  await carregarPagina(page, "assistente");
  await page.waitForFunction(() => document.getElementById("modelo").options.length > 0);
  expect(externas).toEqual([]);
});
