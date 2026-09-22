const { test, expect } = require("@playwright/test");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");


const raiz = resolve(__dirname, "../..");
const modelo = readFileSync(resolve(raiz, "templates/assistente.html"), "utf8")
  .replace(/\{\{[^}]*\}\}/g, "#");
const js = readFileSync(resolve(raiz, "static/assistente.js"), "utf8");


async function carregar(page, cenario) {
  await page.setContent(modelo);
  await page.evaluate((estado) => {
    window.__estado = estado;
    window.__chamadas = [];
    window.fetch = async (url, opc) => {
      window.__chamadas.push({ url, metodo: (opc && opc.method) || "GET", corpo: opc && opc.body });
      const corpo = await window.__rotear(url, opc);
      return { ok: corpo.status < 400, status: corpo.status, json: async () => corpo.json };
    };
    window.__rotear = async (url, opc) => {
      const metodo = (opc && opc.method) || "GET";
      const e = window.__estado;
      if (url === "/api/transcricoes" || url === "/api/modelos") {
        return { status: 200, json: [] };
      }
      if (url === "/api/reunioes" && metodo === "GET") return { status: 200, json: ["reuniao-x"] };
      if (url.endsWith("/resultado") && metodo === "GET") {
        return { status: 200, json: { ...e.base, revision: e.revisao, mapeamento: e.mapeamento } };
      }
      if (url.endsWith("/correcao") && metodo === "POST") {
        const corpo = JSON.parse(opc.body);
        if (corpo.expected_revision !== e.revisao) {
          return { status: 409, json: { erro: "revisão esperada divergente" } };
        }
        e.revisao = "rev-2";
        e.mapeamento = { [corpo.speaker_cluster_id]: { display_name: corpo.display_name, origem: "manual" } };
        return { status: 200, json: { revision: e.revisao } };
      }
      if (url.endsWith("/desfazer") && metodo === "POST") {
        e.revisao = "rev-3";
        e.mapeamento = {};
        return { status: 200, json: { revision: e.revisao } };
      }
      return { status: 404, json: { erro: "x" } };
    };
  }, cenario);
  await page.addScriptTag({ content: js });
}


const BASE = {
  schema_version: 1,
  revision: "rev-1",
  segmentos: [
    { segment_id: "s1", start_ms: 0, end_ms: 1000, audio_source: "loopback", text: "bom dia", speaker_cluster_id: "FALANTE_00", overlap: false }
  ],
  mapeamento: {},
  historico: []
};


test("drawer lista, corrige e desfaz com foco restaurado", async ({ page }) => {
  await carregar(page, { base: BASE, revisao: "rev-1", mapeamento: {} });

  await page.click("#abrir-participantes");
  await expect(page.locator("#participantes-drawer")).toBeVisible();
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");

  await page.selectOption("#correcao-cluster", "FALANTE_00");
  await page.fill("#correcao-nome", "Ana");
  await page.click("#salvar-correcao");
  await expect(page.locator("#lista-participantes")).toContainText("Ana");
  await expect(page.locator("#participantes-estado")).toContainText("rev-2");

  const chamadas = await page.evaluate(() => window.__chamadas.filter((c) => c.url.endsWith("/correcao")));
  expect(chamadas[0].corpo).toContain("FALANTE_00");

  await page.click("#desfazer-correcao");
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");

  await page.click("#fechar-participantes");
  await expect(page.locator("#abrir-participantes")).toBeFocused();
});


test("revisão divergente mostra erro sem perder o drawer", async ({ page }) => {
  await carregar(page, { base: BASE, revisao: "rev-9", mapeamento: {} });

  await page.click("#abrir-participantes");
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");
  await page.selectOption("#correcao-cluster", "FALANTE_00");
  await page.fill("#correcao-nome", "Bruno");
  // Revisão local defasada: força o 409 do servidor.
  await page.evaluate(() => {
    document.getElementById("correcao-revisao").value = "rev-1";
  });
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
  await carregar(page, { base, revisao: "rev-1", mapeamento: {} });
  await page.click("#abrir-participantes");
  await expect(page.locator("#lista-participantes")).toContainText("Identificação pendente");
  await expect(page.locator("#lista-participantes")).toContainText("Sugestão: Ana");
  await expect(page.locator("#lista-participantes")).toContainText("origem: legenda");
  await expect(page.locator("#lista-participantes img")).toHaveCount(0);
  await page.getByRole("button", { name: "Confirmar Ana" }).click();
  await expect(page.locator("#lista-participantes")).toContainText("Ana");
  const chamadas = await page.evaluate(() => window.__chamadas.filter((c) => c.url.endsWith("/correcao")));
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
