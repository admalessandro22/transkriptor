// T-15.E3 / FR-15.E3 — primeiros passos: Ollama no seletor, ações quando falta, concluir.
const { test, expect } = require("@playwright/test");
const { carregarPagina } = require("./helpers");


function estado(ollama) {
  return {
    hardware: { cuda: false, vram_gb: 0, ram_gb: 8 },
    whisper_recomendado: "small",
    ollama: { estado: "online", versao: "0.34.4", pagina_instalacao: "https://ollama.com/download", modelos: [], ...ollama },
    modelo_sugerido: { id: "granite4.1:3b", tamanho_gb: 2.0 },
    extensao: { pareada: false },
    concluido: false,
  };
}


function servidor(dados, extra = {}) {
  const pedidos = [];
  return {
    pedidos,
    api: (url, req) => {
      const p = new URL(url).pathname;
      if (req.method() === "POST") pedidos.push({ p, corpo: req.postData() });
      if (p === "/api/primeiro-uso") return dados;
      if (extra[p]) return extra[p](req);
      if (p === "/api/primeiro-uso/concluir") return { concluido: true };
      return undefined;
    },
  };
}


test("ollama online popula a lista e oferece o modelo sugerido", async ({ page }) => {
  const ctx = await carregarPagina(page, "primeiro-uso", { api: servidor(estado({ modelos: [{ id: "gemma4:latest" }] })).api });
  await expect(page.locator("#pu-modelos li")).toHaveText(["gemma4:latest"]);
  await expect(page.locator("#pu-baixar")).toBeVisible();
  await expect(page.locator("#pu-baixar")).toContainText("granite4.1:3b");
  await expect(page.locator("#pu-transcricao")).toContainText("small");
  expect(ctx.violacoes).toEqual([]);
});


test("modelo sugerido já instalado não pede download", async ({ page }) => {
  await carregarPagina(page, "primeiro-uso", { api: servidor(estado({ modelos: [{ id: "granite4.1:3b" }] })).api });
  await expect(page.locator("#pu-modelos li")).toHaveText(["granite4.1:3b"]);
  await expect(page.locator("#pu-baixar")).toBeHidden();
});


test("ollama ausente oferece a página oficial; parado oferece iniciar com confirmação", async ({ page }) => {
  await carregarPagina(page, "primeiro-uso", { api: servidor(estado({ estado: "nao_instalado", versao: null })).api });
  const instalar = page.locator("#pu-instalar");
  await expect(instalar).toBeVisible();
  await expect(instalar).toHaveAttribute("href", "https://ollama.com/download");
  await expect(instalar).toHaveAttribute("rel", /noopener/);

  const srv = servidor(estado({ estado: "parado", versao: null }), {
    "/api/primeiro-uso/ollama/iniciar": (req) => (JSON.parse(req.postData()).confirmado
      ? { iniciado: true }
      : { status: 409, body: JSON.stringify({ titulo: "Iniciar o Ollama?", consequencia: "Será aberto.", confirmar: "Iniciar" }) }),
  });
  await carregarPagina(page, "primeiro-uso", { api: srv.api });
  await page.locator("#pu-iniciar").click();
  await expect(page.locator("#dialogo-confirmacao")).toBeVisible();
  await page.getByRole("button", { name: "Iniciar", exact: true }).click();
  await expect.poll(() => srv.pedidos.map((x) => x.corpo)).toContain('{"confirmado":true}');
});


test("pular conclui e leva ao início", async ({ page }) => {
  const srv = servidor(estado({}));
  await carregarPagina(page, "primeiro-uso", { api: srv.api });
  await page.locator("#pu-pular").click();
  await expect.poll(() => srv.pedidos.map((x) => x.p)).toContain("/api/primeiro-uso/concluir");
  await expect(page).toHaveURL(/\/inicio/);
});
