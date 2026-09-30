// T-15.C4 / FR-15.C4 — aba "Transcrição do Meet" na reunião: escapada, sob a CSP real,
// e exportação só com confirmação explícita.
const { test, expect } = require("@playwright/test");
const { carregarPagina } = require("./helpers");


const BLOCOS = [
  { inicio_ms: 3_723_000, fim_ms: 3_725_000, participant_id: "dev-9", nome: "<script>window.__xss=1</script>", texto: "bom dia" },
  { inicio_ms: 3_730_000, fim_ms: 3_731_000, participant_id: "dev-1", nome: "Ana Fictícia", texto: "<b>oi</b>" },
];


function base(transcricaoMeet) {
  const dados = {
    schema_version: 1, revision: "rev-1", mapeamento: {}, historico: [],
    segmentos: [{ segment_id: "s1", start_ms: 0, end_ms: 1000, audio_source: "loopback", text: "fala", speaker_cluster_id: "FALANTE_00", overlap: false }],
  };
  if (transcricaoMeet) dados.transcricao_meet = transcricaoMeet;
  return dados;
}


async function carregar(page, dados) {
  return carregarPagina(page, "assistente", {
    api: (url, req) => {
      const p = new URL(url).pathname;
      if (p === "/api/transcricoes" || p === "/api/modelos") return [];
      if (p === "/api/reunioes" && req.method() === "GET") return ["reuniao-x"];
      if (p.endsWith("/resultado") && req.method() === "GET") return dados;
      return { status: 404, body: JSON.stringify({ erro: "x" }) };
    },
  });
}


test("aba mostra horario e nome escapados", async ({ page }) => {
  await carregar(page, base(BLOCOS));
  await page.click("#abrir-participantes");
  const secao = page.locator("#secao-meet");
  await expect(secao).toBeVisible();
  await expect(page.locator("#lista-meet li")).toHaveCount(2);
  await expect(page.locator("#lista-meet")).toContainText("01:02:03");
  await expect(page.locator("#lista-meet")).toContainText("<script>window.__xss=1</script>");
  await expect(page.locator("#lista-meet")).toContainText("<b>oi</b>");
  expect(await page.locator("#lista-meet script, #lista-meet b").count()).toBe(0);
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
});


test("sem transcricao do Meet a aba fica oculta", async ({ page }) => {
  await carregar(page, base(null));
  await page.click("#abrir-participantes");
  await expect(page.locator("#lista-participantes")).toContainText("fala");
  await expect(page.locator("#secao-meet")).toBeHidden();
});


test("exportacao da transcricao do Meet exige confirmacao", async ({ page }) => {
  await carregar(page, base(BLOCOS));
  await page.click("#abrir-participantes");
  await page.evaluate(() => {
    window.__download = null;
    HTMLAnchorElement.prototype.click = function () { window.__download = { nome: this.download, url: this.href }; };
    // A URL blob: é revogada e a CSP não permite buscá-la: guarda o Blob gerado.
    const criar = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (blob) => { window.__blob = blob; return criar(blob); };
  });
  await page.click("#exportar-meet");
  await expect(page.locator("#dialogo-exportar-meet")).toBeVisible();
  await page.click("#confirmar-exportar-meet");
  await expect.poll(() => page.evaluate(() => window.__download && window.__download.nome)).toBe("reuniao-reuniao-x-meet.txt");
  const texto = await page.evaluate(() => window.__blob.text());
  expect(texto).toBe("[01:02:03] <script>window.__xss=1</script>: bom dia\n[01:02:10] Ana Fictícia: <b>oi</b>\n");
});
