import { describe, expect, it } from "vitest";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const fundo = require("../../extension/meet/background.js");
const pareamento = require("../../extension/meet/pairing.js");


describe("background.js (transporte D2)", () => {
  it("só aceita remetente do Meet em top-frame com aba numerada", () => {
    const bom = { frameId: 0, tab: { id: 7 }, url: "https://meet.google.com/abc-defg-hij" };
    expect(fundo.validarSender(bom)).toBe(true);
    expect(fundo.validarSender({ frameId: 1, tab: { id: 7 }, url: "https://meet.google.com/x" })).toBe(false);
    expect(fundo.validarSender({ frameId: 0, tab: {}, url: "https://meet.google.com/x" })).toBe(false);
    expect(fundo.validarSender({ frameId: 0, tab: { id: 7 }, url: "https://evil.example.test/" })).toBe(false);
    expect(fundo.validarSender(null)).toBe(false);
  });

  it("backoff cresce com teto e jitter limitado", () => {
    const semSorte = () => 0.5;
    expect(fundo.atrasoReconexao(0, semSorte)).toBe(1000);
    expect(fundo.atrasoReconexao(1, semSorte)).toBe(2000);
    expect(fundo.atrasoReconexao(99, semSorte)).toBe(30000);
    const piso = fundo.atrasoReconexao(2, () => 0);
    const teto = fundo.atrasoReconexao(2, () => 1);
    expect(piso).toBe(3000);
    expect(teto).toBe(5000);
  });

  it("envelope carrega o id da aba sem expor segredo", () => {
    const env = fundo.montarEnvelope({ nome: "Ana", tipo: "ativo" }, { tab: { id: 9 } });
    expect(env).toMatchObject({ nome: "Ana", tabId: 9 });
    expect(JSON.stringify(env)).not.toMatch(/token/i);
  });
});


describe("pairing.js (pareamento D2)", () => {
  it("aceita código de uso único e rejeita resto", () => {
    expect(pareamento.validarCodigo("pair-abcdefghijklmnop1234")).toBe(true);
    expect(pareamento.validarCodigo("35OlDxZsmQ2ex1Oa6PsUxqiS2mqVNIfY")).toBe(false);
    expect(pareamento.validarCodigo("")).toBe(false);
    expect(pareamento.validarCodigo(null)).toBe(false);
  });
});
