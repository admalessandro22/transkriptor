const { test, expect } = require("@playwright/test");
const { carregarPagina, fixtures } = require("./helpers");


function proxima(rev) { return "rev-" + (parseInt(String(rev).replace(/^rev-/, ""), 10) + 1); }

function servidorFalso(inicial) {
  const e = { dados: structuredClone(inicial) };
  return {
    e,
    api: (url, req) => {
      const p = new URL(url).pathname;
      const metodo = req.method();
      if (p === "/api/reunioes") return ["reuniao-2026-09-22"];
      if (p.endsWith("/resultado")) return e.dados;
      if (p.endsWith("/correcao") && metodo === "POST") {
        const corpo = JSON.parse(req.postData());
        if (corpo.expected_revision !== e.dados.revision) return { status: 409, body: JSON.stringify({ erro: "revisão esperada divergente; recarregue a reunião" }) };
        const anterior = e.dados.mapeamento[corpo.speaker_cluster_id] || null;
        const nova = proxima(e.dados.revision);
        e.dados.mapeamento[corpo.speaker_cluster_id] = { display_name: corpo.display_name, origem: "manual" };
        e.dados.historico.push({ revision: nova, acao: "corrigir", cluster: corpo.speaker_cluster_id, anterior });
        e.dados.revision = nova;
        return { revision: nova };
      }
      if (p.endsWith("/desfazer") && metodo === "POST") {
        const corpo = JSON.parse(req.postData());
        if (corpo.expected_revision !== e.dados.revision) return { status: 409, body: JSON.stringify({ erro: "revisão esperada divergente" }) };
        if (!e.dados.historico.length) return { status: 400, body: JSON.stringify({ erro: "nada a desfazer" }) };
        const ultimo = e.dados.historico[e.dados.historico.length - 1];
        if (ultimo.anterior) e.dados.mapeamento[ultimo.cluster] = ultimo.anterior; else delete e.dados.mapeamento[ultimo.cluster];
        const nova = proxima(e.dados.revision);
        e.dados.historico.push({ revision: nova, acao: "desfazer", cluster: ultimo.cluster });
        e.dados.revision = nova;
        return { revision: nova };
      }
      return undefined;
    },
  };
}


test("confirmar sugestão aplica o nome ao cluster inteiro", async ({ page }) => {
  const srv = servidorFalso(fixtures.resultado());
  await carregarPagina(page, "participantes", { api: srv.api });
  await expect(page.locator("#lista-participantes .fala")).toHaveCount(4);
  await expect(page.locator('#lista-participantes .fala[data-cluster="FALANTE_00"] .p-nome')).toHaveText(["Identificação pendente", "Identificação pendente"]);
  await page.getByRole("button", { name: "Confirmar Ana Souza" }).first().click();
  await expect(page.locator('#lista-participantes .fala[data-cluster="FALANTE_00"] .p-nome')).toHaveText(["Ana Souza", "Ana Souza"]);
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_00"] .falante__estado')).toContainText("Confirmado · manual");
  await expect(page.locator("#participantes-estado")).toHaveText("Correção salva. Revisão 4.");
  await expect(page.locator("#reuniao-revisao")).toHaveText("Revisão 4");
});


test("escolher outro nome foca o campo e mantém o falante escolhido", async ({ page }) => {
  const srv = servidorFalso(fixtures.resultado());
  await carregarPagina(page, "participantes", { api: srv.api });
  await page.getByRole("button", { name: "Escolher outro nome" }).first().click();
  await expect(page.locator("#correcao-nome")).toBeFocused();
  await expect(page.locator("#correcao-cluster")).toHaveValue("FALANTE_00");
  await page.fill("#correcao-nome", "Beatriz");
  await page.click("#salvar-correcao");
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_00"] .falante__nome')).toContainText("Beatriz");
  await expect(page.locator("#correcao-nome")).toHaveValue("");
});


test("undo diz o que vai desfazer e volta ao estado anterior", async ({ page }) => {
  const srv = servidorFalso(fixtures.resultado());
  await carregarPagina(page, "participantes", { api: srv.api });
  await expect(page.locator("#desfazer-descricao")).toContainText("Nada a desfazer");
  await expect(page.locator("#desfazer-correcao")).toBeDisabled();
  await page.selectOption("#correcao-cluster", "FALANTE_02");
  await page.fill("#correcao-nome", "Carla");
  await page.click("#salvar-correcao");
  await expect(page.locator("#desfazer-descricao")).toContainText("Desfazer: Carla volta a Identificação pendente (Falante 3)");
  await expect(page.locator("#desfazer-correcao")).toBeEnabled();
  await page.click("#desfazer-correcao");
  await expect(page.locator("#participantes-estado")).toHaveText("Desfeito. Revisão 5.");
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_02"] .falante__nome')).toContainText("Falante 3");
});


test("409 mantém o painel, recarrega a revisão e explica o próximo passo", async ({ page }) => {
  const srv = servidorFalso(fixtures.resultado());
  await carregarPagina(page, "assistente", { api: srv.api });
  await page.click("#abrir-participantes");
  await expect(page.locator("#reuniao-revisao")).toHaveText("Revisão 3");
  srv.e.dados.revision = "rev-9";
  await page.selectOption("#correcao-cluster", "FALANTE_02");
  await page.fill("#correcao-nome", "Dora");
  await page.click("#salvar-correcao");
  await expect(page.locator("#participantes-estado")).toContainText("Revisão divergente");
  await expect(page.locator("#participantes-estado")).toContainText("confirme novamente");
  await expect(page.locator("#participantes-drawer")).toHaveClass(/is-open/);
  await expect(page.locator("#correcao-revisao")).toHaveValue("rev-9");
  await expect(page.locator("#reuniao-revisao")).toHaveText("Revisão 9");
});


test("html em fala e em nome não executa", async ({ page }) => {
  const base = fixtures.resultado();
  base.segmentos[1].text = "<img src=x onerror=alert(1)> <b>negrito</b>";
  base.mapeamento.FALANTE_01.display_name = "<script>alert(2)</script>";
  const srv = servidorFalso(base);
  await carregarPagina(page, "participantes", { api: srv.api });
  await expect(page.locator("#lista-participantes img, #lista-participantes b, #lista-falantes script")).toHaveCount(0);
  await expect(page.locator('#lista-participantes .fala[data-cluster="FALANTE_01"] .fala__texto')).toContainText("<img src=x onerror=alert(1)>");
  await expect(page.locator('#lista-falantes .falante[data-cluster="FALANTE_01"] .falante__nome')).toContainText("<script>alert(2)</script>");
});
