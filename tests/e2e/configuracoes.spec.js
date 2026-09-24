const { test, expect } = require("@playwright/test");
const { carregarPagina, fixtures } = require("./helpers");


function servidorConfig(inicial) {
  const e = { cfg: { ...fixtures.config(), modelos_whisper: ["auto", "small", "medium"], ...inicial }, pedidos: [] };
  const CONSEQ = {
    pausar_gravacao: { titulo: "Pausar a gravação automática?", consequencia: "Enquanto pausado, o Transkriptor NÃO grava nenhuma reunião.", confirmar: "Pausar" },
    modo_protegido: { titulo: "Ativar o modo protegido para novas reuniões?", consequencia: "Novas reuniões terão resultado cifrado.", confirmar: "Ativar proteção" },
    apagar_perfil_voz: { titulo: "Apagar o seu perfil de voz?", consequencia: "Não pode ser desfeito.", confirmar: "Apagar perfil" },
  };
  return {
    e,
    api: (url, req) => {
      if (!url.endsWith("/api/config")) return undefined;
      if (req.method() === "GET") return e.cfg;
      const corpo = JSON.parse(req.postData());
      e.pedidos.push(corpo);
      const acao = corpo.chave === "deteccao_ativa" && corpo.valor === false ? "pausar_gravacao" : corpo.chave === "protection_mode" ? "modo_protegido" : corpo.chave === "apagar_perfil_voz" ? "apagar_perfil_voz" : null;
      if (acao && corpo.confirmado !== true) return { status: 409, body: JSON.stringify({ erro: "Confirmação necessária", acao, ...CONSEQ[acao] }) };
      if (corpo.chave === "protection_mode") e.cfg.protection_mode = "protected";
      else if (corpo.chave === "apagar_perfil_voz") { e.cfg.perfil_voz_existe = false; e.cfg.identificar_minha_voz = false; }
      else e.cfg[corpo.chave] = corpo.valor;
      return e.cfg;
    },
  };
}


test("formulário espelha a bandeja e um toggle simples salva sem confirmação", async ({ page }) => {
  const srv = servidorConfig({});
  const ctx = await carregarPagina(page, "configuracoes", { api: srv.api });
  await expect(page.locator("#config-form")).toBeVisible();
  await expect(page.locator("#cfg-deteccao_ativa")).toBeChecked();
  await expect(page.locator("#cfg-modelo_whisper")).toHaveValue("auto");
  await expect(page.locator("#cfg-protecao-badge")).toHaveText("Protegida");
  await expect(page.locator("#cfg-linha-protegido")).toBeHidden();
  await page.locator("#cfg-diarizacao_ativa").click();
  await expect(page.locator("#toast-region .tk-toast--success")).toContainText("Configuração salva");
  expect(srv.e.pedidos).toEqual([{ chave: "diarizacao_ativa", valor: false, confirmado: false }]);
  await expect(page.locator("#cfg-diarizacao_ativa")).not.toBeChecked();
  expect(ctx.violacoes).toEqual([]);
});


test("409 abre diálogo com a consequência e reenvia confirmado; cancelar restaura", async ({ page }) => {
  const srv = servidorConfig({});
  await carregarPagina(page, "configuracoes", { api: srv.api });
  await page.locator("#cfg-deteccao_ativa").click();
  const dlg = page.locator("#dialogo-confirmacao");
  await expect(dlg).toBeVisible();
  await expect(dlg).toContainText("NÃO grava");
  await expect(dlg.locator('[data-acao="confirmar"]')).toHaveText("Pausar");
  await page.keyboard.press("Escape");
  await expect(page.locator("#cfg-deteccao_ativa")).toBeChecked();
  expect(srv.e.pedidos.filter((p) => p.confirmado)).toHaveLength(0);

  await page.locator("#cfg-deteccao_ativa").click();
  await dlg.locator('[data-acao="confirmar"]').click();
  await expect(page.locator("#cfg-deteccao_ativa")).not.toBeChecked();
  expect(srv.e.pedidos.at(-1)).toEqual({ chave: "deteccao_ativa", valor: false, confirmado: true });
});


test("modo protegido e apagar perfil passam pelo diálogo; perfil ausente desabilita", async ({ page }) => {
  const srv = servidorConfig({ protection_mode: "compatible", perfil_voz_existe: true, identificar_minha_voz: true });
  await carregarPagina(page, "configuracoes", { api: srv.api });
  await expect(page.locator("#cfg-linha-protegido")).toBeVisible();
  await page.click("#cfg-ativar-protegido");
  await expect(page.locator("#dialogo-confirmacao")).toContainText("modo protegido");
  await page.locator('#dialogo-confirmacao [data-acao="confirmar"]').click();
  await expect(page.locator("#cfg-protecao-badge")).toHaveText("Protegida");
  await expect(page.locator("#cfg-linha-protegido")).toBeHidden();

  await page.click("#cfg-apagar-perfil");
  await expect(page.locator("#dialogo-confirmacao")).toContainText("Não pode ser desfeito");
  await expect(page.locator('#dialogo-confirmacao [data-acao="confirmar"]')).toHaveClass(/tk-btn--danger/);
  await page.locator('#dialogo-confirmacao [data-acao="confirmar"]').click();
  await expect(page.locator("#cfg-apagar-perfil")).toBeDisabled();
  await expect(page.locator("#cfg-identificar_minha_voz")).toBeDisabled();
});


test("sem bandeja a página explica e não deixa editar", async ({ page }) => {
  await carregarPagina(page, "configuracoes", { api: (url) => (url.endsWith("/api/config") ? { status: 503, body: JSON.stringify({ erro: "configurações indisponíveis" }) } : undefined) });
  await expect(page.locator("#config-indisponivel")).toBeVisible();
  await expect(page.locator("#config-form")).toBeHidden();
  await expect(page.locator("#config-estado")).toHaveText("Central sem bandeja");
});
