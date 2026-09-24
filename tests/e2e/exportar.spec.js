const { test, expect } = require("@playwright/test");
const { carregarPagina } = require("./helpers");


async function abrirPainel(page, api) {
  const ctx = await carregarPagina(page, "assistente", { api });
  await page.click("#abrir-participantes");
  await expect(page.locator("#lista-falantes .falante")).toHaveCount(3);
  await page.evaluate(() => {
    window.__download = null;
    HTMLAnchorElement.prototype.click = function () { window.__download = { nome: this.download }; };
  });
  return ctx;
}


test("cancelar a exportação não chama a API e devolve o foco", async ({ page }) => {
  const ctx = await abrirPainel(page);
  await page.click("#exportar-txt");
  const dlg = page.locator("#dialogo-exportar");
  await expect(dlg).toBeVisible();
  await expect(dlg).toContainText("texto legível");
  await expect(dlg.locator('[data-acao="cancelar"]')).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dlg).toBeHidden();
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/exportar-txt"))).toHaveLength(0);
  await expect(page.locator("#exportar-txt")).toBeFocused();
});


test("confirmar a exportação baixa o arquivo com nome da reunião", async ({ page }) => {
  const ctx = await abrirPainel(page, (url, req) => (url.endsWith("/exportar-txt") && req.method() === "POST" ? { status: 200, body: "[00:00:00] Ana: bom dia\n", contentType: "text/plain; charset=utf-8" } : undefined));
  await page.click("#exportar-txt");
  await page.click("#confirmar-exportar");
  await expect(page.locator("#participantes-estado")).toContainText("TXT exportado");
  expect(await page.evaluate(() => window.__download && window.__download.nome)).toBe("reuniao-reuniao-2026-09-22.txt");
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/exportar-txt"))).toHaveLength(1);
});


test("aprender voz é ação separada, com confirmação própria, e 404 vira próximo passo", async ({ page }) => {
  let resposta = { status: 404, body: JSON.stringify({ erro: "Nenhuma separação de vozes recente para aprender. Processe uma reunião com separação de vozes e tente de novo." }) };
  const ctx = await abrirPainel(page, (url) => (url.endsWith("/api/acoes/aprender-voz") ? resposta : undefined));
  const botao = page.locator('#lista-falantes .falante[data-cluster="FALANTE_00"] [data-acao="aprender-voz"]');
  await expect(botao).toBeVisible();
  await botao.click();
  const dlg = page.locator("#dialogo-aprender-voz");
  await expect(dlg).toBeVisible();
  await expect(dlg).toContainText("próximas reuniões");
  await page.keyboard.press("Escape");
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/aprender-voz"))).toHaveLength(0);
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/correcao"))).toHaveLength(0);

  await botao.click();
  await page.click("#confirmar-aprender-voz");
  await expect(page.locator("#toast-region .tk-toast--error")).toContainText("separação de vozes");
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/aprender-voz"))).toHaveLength(1);
  const corpo = JSON.parse(ctx.pedidos.find((p) => p.url.endsWith("/aprender-voz")).corpo);
  expect(corpo).toEqual({ rotulo: "FALANTE_00", nome: "Ana Souza" });

  resposta = { status: 200, body: JSON.stringify({ salvo: "Ana Souza" }) };
  await botao.click();
  await page.click("#confirmar-aprender-voz");
  await expect(page.locator("#toast-region .tk-toast--success")).toContainText("Ana Souza");
});
