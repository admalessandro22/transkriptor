import { describe, expect, it, vi } from "vitest";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const fundo = require("../../extension/meet/background.js");
const runtimeId = "abcdefghijklmnop";

describe("listener real do service worker", () => {
  it("aceita pareamento apenas da própria página da extensão", () => {
    const conectar = vi.fn();
    const sender = {
      id: runtimeId,
      frameId: 0,
      url: `chrome-extension://${runtimeId}/pairing.html`,
    };
    const resposta = vi.fn();
    expect(fundo.aoReceberMensagem({ tipo: "parear" }, sender, resposta, {
      runtimeId,
      conectar,
    })).toBe(true);
    expect(conectar).toHaveBeenCalledOnce();
    expect(resposta).toHaveBeenCalledOnce();
  });

  it.each([
    { id: "outraextensao", frameId: 0, url: `chrome-extension://${runtimeId}/pairing.html` },
    { id: runtimeId, frameId: 0, url: "http://localhost/pairing.html" },
    { id: runtimeId, frameId: 1, url: `chrome-extension://${runtimeId}/pairing.html` },
    { id: runtimeId, frameId: 0, url: `chrome-extension://${runtimeId}/outra.html` },
  ])("rejeita remetente de pareamento inválido: %j", (sender) => {
    const conectar = vi.fn();
    expect(fundo.aoReceberMensagem({ tipo: "parear" }, sender, vi.fn(), {
      runtimeId,
      conectar,
    })).toBe(false);
    expect(conectar).not.toHaveBeenCalled();
  });

  it("não aceita mensagem de conteúdo enviada pela página de pareamento", () => {
    const sender = { id: runtimeId, frameId: 0, url: `chrome-extension://${runtimeId}/pairing.html` };
    expect(fundo.aoReceberMensagem({ tipo: "meet-evento", evento: { tipo: "reuniao" } }, sender)).toBe(false);
  });
});

describe("estado do pareamento", () => {
  const sender = { id: runtimeId, frameId: 0, url: `chrome-extension://${runtimeId}/pairing.html` };

  it("só a página de pareamento consulta; responde o estado registrado", () => {
    fundo.registrarPareamento("pendente");
    const resposta = vi.fn();
    expect(fundo.aoReceberMensagem({ tipo: "estadoPareamento" }, sender, resposta, { runtimeId })).toBe(true);
    expect(resposta).toHaveBeenCalledWith({ pronto: false, pareamento: "pendente" });

    const meet = { frameId: 0, tab: { id: 3 }, url: "https://meet.google.com/abc-defg-hij" };
    expect(fundo.aoReceberMensagem({ tipo: "estadoPareamento" }, meet, vi.fn(), { runtimeId })).toBe(false);
  });

  it("mensagem 'pareado' do app confirma; fechamento 1008 recusa", () => {
    fundo.registrarPareamento("pendente");
    fundo.tratarFechamento({ code: 1008 });
    expect(fundo.estadoPareamento()).toBe("recusado");
    fundo.registrarPareamento("confirmado");
    fundo.tratarFechamento({ code: 1006 });
    expect(fundo.estadoPareamento()).toBe("confirmado");
  });
});

describe("persistência da credencial", () => {
  it("pairing e background usam chrome.storage.local, nunca session", async () => {
    const { readFileSync } = await import("node:fs");
    for (const arquivo of ["background.js", "pairing.js"]) {
      const fonte = readFileSync(`extension/meet/${arquivo}`, "utf8");
      expect(fonte).toMatch(/chrome\.storage\.local/);
      expect(fonte).not.toMatch(/chrome\.storage\.session/);
    }
  });
});
