const { test, expect } = require("@playwright/test");
const { carregarPagina, fixtures } = require("./helpers");

const AUDIOS = [
  { nome: "2026-09-22_10h03.wav", mtime: "2026-09-22T10:03", duracao_seg: 1830 },
  { nome: "2026-09-18_15h30.tks", mtime: "2026-09-18T15:30", duracao_seg: 42 },
];


function api(extra = {}) {
  return (url, req) => {
    const p = new URL(url).pathname;
    if (p === "/api/diagnostico" && req.method() === "POST") return extra.diagnostico || fixtures.diagnostico();
    if (p === "/api/diagnostico/exportar") return { status: 200, body: "Diagnóstico do Transkriptor 1.7.0\n[ERRO ] Microfone  <pasta-pessoal>\n", contentType: "text/plain; charset=utf-8" };
    if (p === "/api/audios-retidos") return extra.audios || AUDIOS;
    if (p === "/api/acoes/retranscrever" && req.method() === "POST") return extra.retranscrever || { status: 202, body: JSON.stringify({ aceito: true, nome: JSON.parse(req.postData()).nome }) };
    if (p === "/api/acoes/pareamento" && req.method() === "POST") return extra.pareamento || { codigo: "pair-sintetico-0001-0000000000", validade_seg: 300, ponte_ativa: true };
    return undefined;
  };
}


test("itens do diagnóstico têm estado, detalhe e ação sugerida", async ({ page }) => {
  const ctx = await carregarPagina(page, "diagnostico", { api: api() });
  await expect(page.locator("#diag-vazio")).toBeVisible();
  await expect(page.locator("#diag-exportar")).toBeDisabled();
  await page.click("#diag-rodar");
  await expect(page.locator("#diag-lista .diag__item")).toHaveCount(4);
  await expect(page.locator("#diag-resumo-badge")).toHaveText("1 erro");
  const micro = page.locator('#diag-lista .diag__item[data-estado="ERRO"]');
  await expect(micro).toContainText("Microfone");
  await expect(micro.locator(".diag__acao")).toContainText("microfone padrão do Windows");
  await expect(page.locator('#diag-lista .diag__item[data-estado="OK"] .diag__acao')).toHaveCount(0);
  await expect(page.locator("#diag-resumo-texto")).toContainText("diagnostico_2026-09-24_12h00.txt");
  await expect(page.locator("#diag-exportar")).toBeEnabled();
  expect(ctx.violacoes).toEqual([]);
});


test("exportar baixa o texto sem dados pessoais", async ({ page }) => {
  const ctx = await carregarPagina(page, "diagnostico", { api: api() });
  await page.click("#diag-rodar");
  await expect(page.locator("#diag-exportar")).toBeEnabled();
  await page.evaluate(() => { window.__download = null; HTMLAnchorElement.prototype.click = function () { window.__download = this.download; }; });
  await page.click("#diag-exportar");
  await expect(page.locator("#toast-region .tk-toast--success")).toContainText("Relatório exportado");
  expect(await page.evaluate(() => window.__download)).toBe("diagnostico-transkriptor.txt");
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/api/diagnostico/exportar"))).toHaveLength(1);
});


test("retranscrever lista os áudios retidos, confirma e mostra progresso", async ({ page }) => {
  const ctx = await carregarPagina(page, "diagnostico", { api: api() });
  await expect(page.locator("#retranscrever-lista .tk-row")).toHaveCount(2);
  await expect(page.locator("#retranscrever-lista")).toContainText("30 min 30 s");
  await page.locator('#retranscrever-lista .tk-row[data-nome="2026-09-22_10h03.wav"] [data-acao="retranscrever"]').click();
  await expect(page.locator("#dialogo-retranscrever")).toBeVisible();
  await page.keyboard.press("Escape");
  expect(ctx.pedidos.filter((p) => p.url.endsWith("/api/acoes/retranscrever"))).toHaveLength(0);
  await page.locator('#retranscrever-lista .tk-row[data-nome="2026-09-22_10h03.wav"] [data-acao="retranscrever"]').click();
  await page.click("#confirmar-retranscrever");
  await expect(page.locator("#retranscrever-estado")).toContainText("Retranscrevendo");
  await expect(page.locator("#toast-region .tk-toast--info")).toContainText("Retranscrição iniciada");
  const pedido = ctx.pedidos.find((p) => p.url.endsWith("/api/acoes/retranscrever"));
  expect(JSON.parse(pedido.corpo)).toEqual({ nome: "2026-09-22_10h03.wav" });
});


test("sem bandeja e sem áudios, a página explica", async ({ page }) => {
  await carregarPagina(page, "diagnostico", { api: (url, req) => {
    const p = new URL(url).pathname;
    if (p === "/api/diagnostico") return { status: 503, body: JSON.stringify({ erro: "indisponível" }) };
    if (p === "/api/audios-retidos") return [];
    return undefined;
  } });
  await expect(page.locator("#retranscrever-vazio")).toContainText("Nenhum áudio retido");
  await page.click("#diag-rodar");
  await expect(page.locator("#diag-indisponivel")).toBeVisible();
  await expect(page.locator("#toast-region .tk-toast")).toHaveCount(0);
});


test("gera o código de pareamento da extensão e permite copiar", async ({ page }) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const ctx = await carregarPagina(page, "diagnostico", { api: api() });
  await expect(page.locator("#pareamento-resultado")).toBeHidden();
  await page.click("#pareamento-gerar");
  await expect(page.locator("#pareamento-codigo")).toHaveText("pair-sintetico-0001-0000000000");
  await expect(page.locator("#pareamento-aviso")).toContainText("5 min");
  await page.click("#pareamento-copiar");
  await expect(page.locator("#toast-region")).toContainText("Código copiado");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("pair-sintetico-0001-0000000000");
  expect(ctx.violacoes).toEqual([]);
});


test("sem ponte do Meet, o pareamento explica o próximo passo", async ({ page }) => {
  await carregarPagina(page, "diagnostico", { api: api({ pareamento: { status: 503, body: JSON.stringify({ erro: "Ponte do Meet desligada: ative 'Identificar nomes do Meet' em Configurações e tente de novo." }) } }) });
  await page.click("#pareamento-gerar");
  await expect(page.locator("#pareamento-resultado")).toBeHidden();
  await expect(page.locator("#pareamento-aviso")).toContainText("Identificar nomes do Meet");
});
