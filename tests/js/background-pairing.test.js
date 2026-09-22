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
