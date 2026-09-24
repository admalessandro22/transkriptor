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
  await expect(page.locator("#reuniao-revisao")).toContainText("Revisão 1");
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


// NFR-14.F1 — percurso de teclado completo por página: Tab alcança todos os
// controles focáveis visíveis, nenhum fica sem indicação de foco e o foco
// nunca cai no body (sem armadilha nem buraco).
const PAGINAS_CENTRAL = ["inicio", "reunioes", "assistente", "participantes", "configuracoes", "diagnostico", "galeria"];

for (const pagina of PAGINAS_CENTRAL) {
  test(`foco visivel em todos os controles: ${pagina}`, async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 900 });
    await carregarPagina(page, pagina);
    await page.waitForTimeout(400);
    // Chave estável por posição no DOM (rótulos repetidos, como "Abrir no Assistente", não são ciclo).
    const focaveis = await page.evaluate(() => {
      const todos = [...document.querySelectorAll("*")];
      return [...document.querySelectorAll("a[href], button, input, select, textarea, [tabindex]")]
        .filter((el) => el.tabIndex >= 0 && !el.matches(":disabled") && !el.closest("[hidden], [inert]") && el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
        .map((el) => `${todos.indexOf(el)}:${el.id ? "#" + el.id : el.tagName + ":" + (el.textContent || "").trim().slice(0, 20)}`);
    });
    const total = focaveis.length;
    expect(total).toBeGreaterThan(3);
    const vistos = new Set();
    const semFoco = [];
    let saidas = 0; // Tab depois do último controle sai do documento (body) e o próximo volta ao primeiro
    for (let i = 0; i < total + 3; i++) {
      await page.keyboard.press("Tab");
      const info = await page.evaluate(() => {
        const el = document.activeElement;
        const cs = getComputedStyle(el);
        const anel = cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0;
        const sombra = cs.boxShadow && cs.boxShadow !== "none";
        const chave = `${[...document.querySelectorAll("*")].indexOf(el)}:${el.id ? "#" + el.id : el.tagName + ":" + (el.textContent || "").trim().slice(0, 20)}`;
        return { tag: el.tagName, chave, visivel: anel || sombra };
      });
      if (info.tag === "BODY") {
        saidas += 1;
        expect(saidas, `foco caiu no body duas vezes (buraco) depois de ${[...vistos].slice(-1)[0]}`).toBeLessThanOrEqual(1);
        continue;
      }
      if (vistos.has(info.chave)) break;
      vistos.add(info.chave);
      if (!info.visivel) semFoco.push(info.chave);
    }
    expect(semFoco, "controles sem anel de foco").toEqual([]);
    expect([...new Set(focaveis)].filter((f) => !vistos.has(f)), "controles focáveis não alcançados por Tab").toEqual([]);
  });
}
