// T-15.D3 / UX-15.D3 — seção "Inteligência artificial" nas Configurações.
const { test, expect } = require("@playwright/test");
const { carregarPagina, fixtures } = require("./helpers");

const CONSENTIMENTO = "Ao usar o OpenRouter, o texto da transcrição e as suas perguntas saem deste computador. Áudio e voz nunca saem.";


function servidorIa({ ollama = "online", consentido = false } = {}) {
  const e = {
    pedidos: [],
    estado: {
      transcricao: { dispositivo: "auto", precisao: "auto", idioma: "pt", hardware: { cuda: false, vram_gb: 0 }, recomendado: "small" },
      resumo: { provedor: "ollama", modelo: "" },
      chat: { provedor: "ollama", modelo: "gemma4:latest" },
      ollama_url: "http://127.0.0.1:11434",
      openrouter: { configurada: false, final: null, consentido_em: consentido ? "2026-09-29T20:00:00Z" : null },
    },
  };
  const modelosOllama = ollama === "online"
    ? { estado: { estado: "online", detalhe: "", versao: "0.34.4" }, modelos: [{ id: "granite4.1:3b", nome: "granite4.1:3b", local: true }, { id: "gemma4:latest", nome: "gemma4:latest", local: true }] }
    : { estado: { estado: "offline", detalhe: "O Ollama não respondeu neste computador." }, modelos: [] };
  return {
    e,
    api: (url, req) => {
      const u = new URL(url);
      if (u.pathname === "/api/config") return fixtures.config();
      if (u.pathname === "/api/ia/modelos") {
        return u.searchParams.get("provedor") === "openrouter"
          ? { estado: { estado: "online" }, modelos: [{ id: "org/resumidor", nome: "Resumidor", local: false }] }
          : modelosOllama;
      }
      if (u.pathname !== "/api/ia") return undefined;
      if (req.method() === "GET") return e.estado;
      const corpo = JSON.parse(req.postData());
      e.pedidos.push(corpo);
      if (corpo.chave.endsWith("_provedor") && corpo.valor === "openrouter" && !e.estado.openrouter.consentido_em && corpo.confirmado !== true) {
        return { status: 409, body: JSON.stringify({ erro: "Confirmação necessária", acao: "openrouter", titulo: "Usar o OpenRouter?", consequencia: CONSENTIMENTO, confirmar: "Usar o OpenRouter" }) };
      }
      if (corpo.chave === "openrouter_chave") e.estado.openrouter = { ...e.estado.openrouter, configurada: true, final: corpo.valor.slice(-4) };
      else if (corpo.chave === "ia_resumo_provedor") { e.estado.resumo.provedor = corpo.valor; e.estado.openrouter.consentido_em = "2026-09-29T20:00:00Z"; }
      else if (corpo.chave === "ia_resumo_modelo") e.estado.resumo.modelo = corpo.valor;
      else if (corpo.chave === "whisper_dispositivo") e.estado.transcricao.dispositivo = corpo.valor;
      return e.estado;
    },
  };
}


test("seletor lista modelos do ollama e salva o escolhido", async ({ page }) => {
  const srv = servidorIa();
  const ctx = await carregarPagina(page, "configuracoes", { api: srv.api });
  const sel = page.locator("#ia-resumo-modelo");
  await expect(sel.locator("option")).toHaveText(["Automático", "granite4.1:3b", "gemma4:latest"]);
  await expect(page.locator("#ia-chat-modelo")).toHaveValue("gemma4:latest");
  await sel.selectOption("granite4.1:3b");
  await expect.poll(() => srv.e.pedidos.at(-1)).toEqual({ chave: "ia_resumo_modelo", valor: "granite4.1:3b", confirmado: false });
  await expect(page.locator("#ia-transcricao-info")).toContainText("small");
  expect(ctx.violacoes).toEqual([]);
});


test("ollama offline mostra o motivo", async ({ page }) => {
  await carregarPagina(page, "configuracoes", { api: servidorIa({ ollama: "offline" }).api });
  await expect(page.locator("#ia-resumo-estado")).toContainText("não respondeu");
  await expect(page.locator("#ia-resumo-modelo option")).toHaveText(["Automático"]);
});


test("openrouter pede consentimento com o que sai do computador", async ({ page }) => {
  const srv = servidorIa();
  await carregarPagina(page, "configuracoes", { api: srv.api });
  await page.locator("#ia-resumo-provedor").selectOption("openrouter");
  await expect(page.locator("#dialogo-confirmacao")).toBeVisible();
  await expect(page.locator("#dialogo-confirmacao")).toContainText("Áudio e voz nunca saem");
  await page.getByRole("button", { name: "Usar o OpenRouter" }).click();
  await expect.poll(() => srv.e.pedidos.at(-1)).toEqual({ chave: "ia_resumo_provedor", valor: "openrouter", confirmado: true });
  await expect(page.locator("#ia-resumo-modelo option")).toContainText(["org/resumidor"]);
});


test("chave mascarada: o campo esvazia e só o final aparece", async ({ page }) => {
  const srv = servidorIa();
  await carregarPagina(page, "configuracoes", { api: srv.api });
  const campo = page.locator("#ia-openrouter-chave");
  await expect(campo).toHaveAttribute("type", "password");
  await campo.fill("sk-or-v1-segredo-sintetico-123456");
  await page.locator("#ia-openrouter-salvar").click();
  await expect(page.locator("#ia-openrouter-status")).toContainText("3456");
  await expect(campo).toHaveValue("");
  await expect(page.locator("body")).not.toContainText("segredo-sintetico");
});


test("rótulos acessíveis nos controles", async ({ page }) => {
  await carregarPagina(page, "configuracoes", { api: servidorIa().api });
  for (const rotulo of ["Dispositivo da transcrição", "Provedor dos resumos", "Modelo dos resumos", "Provedor do assistente", "Modelo do assistente", "Chave do OpenRouter"]) {
    await expect(page.getByLabel(rotulo)).toBeVisible();
  }
});
