const { test, expect } = require("@playwright/test");
const { carregarPagina, selecionarReuniao } = require("./helpers");


const REUNIOES = [
  { arquivo: "a.txt", data: "01/01/2026 10:00", tipo: "transcricao", tamanho_kb: 1, protegida: false, com_sua_voz: null },
  { arquivo: "b.txt", data: "02/01/2026 10:00", tipo: "transcricao", tamanho_kb: 2, protegida: false, com_sua_voz: null }
];

const RESULTADO = {
  schema_version: 1, revision: "rev-1",
  segmentos: [{ segment_id: "s1", start_ms: 0, end_ms: 1000, audio_source: "loopback", text: "bom dia", speaker_cluster_id: "FALANTE_00", overlap: false }],
  mapeamento: {}, historico: []
};


async function carregar(page, roteador) {
  if (roteador === "clipboard-negado") {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new DOMException("negado", "NotAllowedError")) }, configurable: true });
    });
  }
  const ctx = await carregarPagina(page, "assistente", {
    api: (url) => {
      if (url.includes("/api/transcricoes")) return REUNIOES;
      if (url.endsWith("/api/modelos")) return ["llama3"];
      if (url.endsWith("/api/reunioes")) return ["reuniao-x"];
      if (url.endsWith("/resultado")) return RESULTADO;
      return undefined;
    },
    chat: () => "resposta acessivel"
  });
  await page.waitForFunction(() => document.getElementById("transcricao").options.length === 2 && document.getElementById("modelo").options.length === 1);
  return ctx;
}


test("foco entra no drawer, circula dentro e volta ao fechar", async ({ page }) => {
  await carregar(page);
  await page.click("#abrir-participantes");
  await expect(page.locator("#reuniao-participantes")).toBeFocused();
  await expect(page.locator("#reuniao-revisao")).toContainText("rev-1");
  const ordem = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    ordem.push(await page.evaluate(() => document.activeElement.id || document.activeElement.tagName));
  }
  expect(ordem.every((id) => id !== "BODY")).toBe(true);
  await page.keyboard.press("Escape");
  await expect(page.locator("#abrir-participantes")).toBeFocused();
});


test("clipboard negado mostra erro visivel", async ({ page }) => {
  await carregar(page, "clipboard-negado");
  await selecionarReuniao(page, "a.txt");
  await page.fill("#input", "oi");
  await page.click("#send");
  await page.waitForFunction(() => !document.getElementById("copiar-resposta").disabled);
  await page.click("#copiar-resposta");
  await expect(page.locator("#copiar-resposta")).toContainText("Erro ao copiar");
});


test("filtro preserva selecao e telas nao estouram", async ({ page }) => {
  await carregar(page);
  await selecionarReuniao(page, "b.txt");
  await page.fill("#busca-transcricao", "02/01");
  expect(await page.evaluate(() => document.getElementById("transcricao").value)).toBe("b.txt");
  for (const largura of [375, 860, 1366]) {
    await page.setViewportSize({ width: largura, height: 800 });
    await page.click("#abrir-participantes");
    const estouro = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(estouro).toBeLessThanOrEqual(1);
    await page.click("#fechar-participantes");
  }
});
