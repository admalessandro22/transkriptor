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

  it("envia hello por aba e espera a sessão consentida antes do conteúdo", () => {
    const enviados = [];
    const sender = { frameId: 0, tab: { id: 91 }, url: "https://meet.google.com/abc-defg-hij" };
    fundo.aoReceberMensagem(
      { tipo: "meet-evento", evento: { tipo: "legenda", nome: "Pessoa Sintética", texto: "fala" } },
      sender, null, { enviar: (mensagem) => enviados.push(mensagem) }
    );
    expect(enviados).toHaveLength(1);
    expect(enviados[0]).toMatchObject({ tipo: "hello", tab_id: "91", meeting_hint: "abc-defg-hij" });
    expect(JSON.stringify(enviados)).not.toMatch(/Pessoa Sintética|fala|token/);
  });

  it("gera envelope v1 isolado por aba, com relógio do cliente e sem campo do servidor", () => {
    const a = { frameId: 0, tab: { id: 92 }, url: "https://meet.google.com/abc-defg-hij" };
    const b = { frameId: 0, tab: { id: 93 }, url: "https://meet.google.com/xyz-abcd-efg" };
    const ca = fundo.estadoAba(92).connectionId;
    const cb = fundo.estadoAba(93).connectionId;
    expect(ca).not.toBe(cb);
    expect(fundo.aceitarSessao({ tipo: "sessao", connection_id: ca, tab_id: "92", session_id: "s-a", meeting_key: "m-a" })).toBe(true);
    expect(fundo.aceitarSessao({ tipo: "sessao", connection_id: cb, tab_id: "93", session_id: "s-b", meeting_key: "m-b" })).toBe(true);
    const evento = { tipo: "legenda", nome: "Pessoa Sintética", texto: "fala", caption_id: "cap-1", caption_revision: 2, token: "segredo" };
    const ea = fundo.montarEnvelope(evento, a, { wallMs: 123, monotonicMs: 456 });
    const eb = fundo.montarEnvelope(evento, b, { wallMs: 124, monotonicMs: 457 });
    expect(ea).toMatchObject({ schema_version: 1, session_id: "s-a", connection_id: ca, tab_id: "92", meeting_key: "m-a", seq: 0, kind: "caption", client_wall_ms: 123, client_monotonic_ms: 456, caption_id: "cap-1", caption_revision: 2, display_name: "Pessoa Sintética", text: "fala" });
    expect(eb).toMatchObject({ session_id: "s-b", connection_id: cb, tab_id: "93", meeting_key: "m-b", seq: 0 });
    expect(ea.event_id).not.toBe(eb.event_id);
    expect(JSON.stringify(ea)).not.toMatch(/token|received_monotonic_ns/);
  });

  it("não aceita sessão destinada a outra conexão ou aba", () => {
    const connectionId = fundo.estadoAba(94).connectionId;
    expect(fundo.aceitarSessao({ tipo: "sessao", connection_id: connectionId, tab_id: "95", session_id: "s", meeting_key: "m" })).toBe(false);
    expect(fundo.montarEnvelope({ tipo: "reuniao", ativa: true }, { tab: { id: 94 } })).toBe(null);
  });

  it("troca de reunião na mesma aba invalida a sessão anterior", () => {
    const enviados = [];
    const antigo = { frameId: 0, tab: { id: 96 }, url: "https://meet.google.com/abc-defg-hij" };
    const novo = { frameId: 0, tab: { id: 96 }, url: "https://meet.google.com/xyz-abcd-efg" };
    const enviar = (msg) => enviados.push(msg);
    fundo.aoReceberMensagem({ tipo: "meet-evento", evento: { tipo: "reuniao", ativa: true } }, antigo, null, { enviar });
    const primeiro = enviados[0].connection_id;
    fundo.aceitarSessao({ tipo: "sessao", connection_id: primeiro, tab_id: "96", session_id: "sessao-antiga", meeting_key: "antiga" });
    fundo.aoReceberMensagem({ tipo: "meet-evento", evento: { tipo: "legenda", nome: "Pessoa Sintética", texto: "fala" } }, novo, null, { enviar });
    expect(enviados[1]).toMatchObject({ tipo: "hello", meeting_hint: "xyz-abcd-efg" });
    expect(enviados[1].connection_id).not.toBe(primeiro);
    expect(JSON.stringify(enviados[1])).not.toContain("fala");
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
