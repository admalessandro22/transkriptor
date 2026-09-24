const { test, expect } = require("@playwright/test");
const { carregarPagina } = require("./helpers");


const BASE = {
  schema_version: 1,
  revision: "rev-1",
  segmentos: [
    { segment_id: "s1", start_ms: 0, end_ms: 1000, audio_source: "loopback", text: "bom dia", speaker_cluster_id: "FALANTE_00", overlap: false }
  ],
  mapeamento: {},
  historico: []
};


async function carregar(page, cenario) {
  const e = cenario;
  const ctx = await carregarPagina(page, "assistente", {
    api: (url, req) => {
      const metodo = req.method();
      const p = new URL(url).pathname;
      if (p === "/api/transcricoes" || p === "/api/modelos") return [];
      if (p === "/api/reunioes" && metodo === "GET") return ["reuniao-x"];
      if (p.endsWith("/resultado") && metodo === "GET") return { ...e.base, revision: e.revisao, mapeamento: e.mapeamento, historico: e.historico || [] };
      if (p.endsWith("/correcao") && metodo === "POST") {
        const corpo = JSON.parse(req.postData());
        if (corpo.expected_revision !== e.revisao) return { status: 409, body: JSON.stringify({ erro: "revisão esperada divergente" }) };
        e.revisao = "rev-2";
        e.mapeamento = { [corpo.speaker_cluster_id]: { display_name: corpo.display_name, origem: "manual" } };
        e.historico = [{ revision: e.revisao, acao: "corrigir", cluster: corpo.speaker_cluster_id, anterior: null }];
        return { revision: e.revisao };
      }
      if (p.endsWith("/desfazer") && metodo === "POST") { e.revisao = "rev-3"; e.mapeamento = {}; e.historico = [...(e.historico || []), { revision: "rev-3", acao: "desfazer", cluster: "FALANTE_00" }]; return { revision: e.revisao }; }
      if (p.endsWith("/exportar-txt") && metodo === "POST") return { status: 200, body: "fala exportada\n", contentType: "text/plain; charset=utf-8" };
      return { status: 404, body: JSON.stringify({ erro: "x" }) };
    }
  });
  ctx.chamadas = () => ctx.pedidos.map((p) => ({ url: p.url, corpo: p.corpo, metodo: p.metodo }));
  return ctx;
}


test("drawer lista, corrige e desfaz com foco restaurado", async ({ page }) => {
  const ctx = await carregar(page, { base: BASE, revisao: "rev-1", mapeamento: {} });

  await page.click("#abrir-participantes");
  await expect(page.locator("#participantes-drawer")).toBeVisible();
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");

  await page.selectOption("#correcao-cluster", "FALANTE_00");
  await page.fill("#correcao-nome", "Ana");
  await page.click("#salvar-correcao");
  await expect(page.locator("#lista-participantes")).toContainText("Ana");
  await expect(page.locator("#participantes-estado")).toContainText("Revisão 2");

  const chamadas = ctx.chamadas().filter((c) => c.url.endsWith("/correcao"));
  expect(chamadas[0].corpo).toContain("FALANTE_00");

  await page.click("#desfazer-correcao");
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");

  await page.click("#fechar-participantes");
  await expect(page.locator("#abrir-participantes")).toBeFocused();
});


test("exportação TXT exige confirmação e aciona download explícito", async ({ page }) => {
  const ctx = await carregar(page, { base: BASE, revisao: "rev-1", mapeamento: {} });
  await page.click("#abrir-participantes");
  await page.evaluate(() => {
    window.__download = null;
    HTMLAnchorElement.prototype.click = function () { window.__download = { nome: this.download, url: this.href }; };
  });
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.click("#exportar-txt");
  expect(ctx.chamadas().filter((c) => c.url.endsWith("/exportar-txt"))).toHaveLength(0);

  page.once("dialog", (dialog) => dialog.accept());
  await page.click("#exportar-txt");
  await expect(page.locator("#participantes-estado")).toContainText("TXT exportado");
  expect(await page.evaluate(() => window.__download.nome)).toBe("reuniao-reuniao-x.txt");
  expect(ctx.chamadas().filter((c) => c.url.endsWith("/exportar-txt"))).toHaveLength(1);
});


test("revisão divergente mostra erro sem perder o drawer", async ({ page }) => {
  await carregar(page, { base: BASE, revisao: "rev-9", mapeamento: {} });

  await page.click("#abrir-participantes");
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");
  await page.selectOption("#correcao-cluster", "FALANTE_00");
  await page.fill("#correcao-nome", "Bruno");
  // Revisão local defasada: força o 409 do servidor.
  await page.evaluate(() => { document.getElementById("correcao-revisao").value = "rev-1"; });
  await page.click("#salvar-correcao");
  await expect(page.locator("#participantes-estado")).toContainText("divergente");
  await expect(page.locator("#participantes-drawer")).toBeVisible();
  await expect(page.locator("#correcao-revisao")).toHaveValue("rev-9");
});


test("sugestão conserva pendência até confirmação e escapa conteúdo", async ({ page }) => {
  const base = structuredClone(BASE);
  base.segmentos[0].text = "<img src=x onerror=alert(1)>";
  base.segmentos[0].assignment = {
    status: "suggested", participant_id: "p1", display_name: "Ana",
    source: "caption", confidence: 1, evidence_event_ids: ["e1"],
    calibration_version: "corpus-v1",
  };
  const ctx = await carregar(page, { base, revisao: "rev-1", mapeamento: {} });
  await page.click("#abrir-participantes");
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");
  await expect(page.locator("#lista-participantes")).toContainText("Sugestão: Ana");
  await expect(page.locator("#lista-participantes")).toContainText("origem: legenda");
  await expect(page.locator("#lista-participantes img")).toHaveCount(0);
  await page.getByRole("button", { name: "Confirmar Ana" }).click();
  await expect(page.locator("#lista-participantes")).toContainText("Ana");
  const chamadas = ctx.chamadas().filter((c) => c.url.endsWith("/correcao"));
  expect(JSON.parse(chamadas[0].corpo).expected_revision).toBe("rev-1");
  await page.click("#desfazer-correcao");
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");
});


test("sugestões divergentes no mesmo falante exigem escolha manual", async ({ page }) => {
  const base = structuredClone(BASE);
  base.segmentos = [
    { ...base.segmentos[0], assignment: { status: "suggested", display_name: "Ana", participant_id: "p1", source: "caption", confidence: 1 } },
    { ...base.segmentos[0], segment_id: "s2", assignment: { status: "suggested", display_name: "Bruno", participant_id: "p2", source: "caption", confidence: 1 } },
  ];
  await carregar(page, { base, revisao: "rev-1", mapeamento: {} });
  await page.click("#abrir-participantes");
  await expect(page.getByRole("button", { name: "Confirmar Ana" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confirmar Bruno" })).toHaveCount(0);
  await expect(page.locator("#lista-participantes")).toContainText("Sugestão: Ana");
  await expect(page.locator("#lista-participantes")).toContainText("Sugestão: Bruno");
});
