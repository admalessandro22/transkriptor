// T-15.A3 / FR-15.A3 — nada se perde antes da sessão nem durante reconexão,
// e cada fala fecha com uma revisão final.
import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const fundo = require("../../extension/meet/background.js");
const rtc = require("../../extension/meet/rtc.js");

const contentScript = readFileSync(resolve(process.cwd(), "extension/meet/content.js"), "utf8");
const parserScript = readFileSync(resolve(process.cwd(), "extension/meet/parser.js"), "utf8");


function remetente(tab) {
  return { frameId: 0, tab: { id: tab }, url: "https://meet.google.com/abc-defg-hij" };
}

function legenda(texto) {
  return { tipo: "meet-evento", evento: { tipo: "legenda", nome: "Pessoa Sintética", texto, caption_id: `rtc-1/${texto}`,
    caption_revision: 1, participant_id: "dev-1", confidence_source: "caption" } };
}

function sessao(tab, id = "s") {
  const { connectionId } = fundo.estadoAba(tab);
  return { tipo: "sessao", connection_id: connectionId, tab_id: String(tab), session_id: `${id}-${tab}`,
    meeting_key: `m-${tab}` };
}


describe("background.js — fila até a sessão", () => {
  afterEach(() => vi.restoreAllMocks());

  it("eventos antes da sessão são reenviados em ordem", () => {
    const enviados = [];
    const deps = { enviar: (m) => enviados.push(m) };
    fundo.aoReceberMensagem(legenda("um"), remetente(701), null, deps);
    fundo.aoReceberMensagem(legenda("dois"), remetente(701), null, deps);
    fundo.aoReceberMensagem({ tipo: "meet-evento", evento: { tipo: "reuniao", ativa: true } }, remetente(701), null, deps);
    expect(enviados.filter((m) => m.tipo === "hello").length).toBeGreaterThan(0);
    expect(enviados.some((m) => m.kind)).toBe(false);
    enviados.length = 0;
    expect(fundo.aceitarSessao(sessao(701), deps)).toBe(true);
    expect(enviados.map((m) => m.text)).toEqual(["um", "dois"]);
    expect(enviados.every((m) => m.queued === true)).toBe(true);
    expect(enviados.map((m) => m.seq)).toEqual([0, 1]);
  });

  it("reconexão não perde eventos", () => {
    const enviados = [];
    const deps = { enviar: (m) => enviados.push(m) };
    fundo.aceitarSessao(sessao(702), deps);
    fundo.reiniciarSessoes();
    fundo.aoReceberMensagem(legenda("durante a queda"), remetente(702), null, deps);
    enviados.length = 0;
    fundo.aceitarSessao(sessao(702, "s2"), deps);
    expect(enviados.map((m) => m.text)).toEqual(["durante a queda"]);
  });

  it("fila respeita limite e idade", () => {
    const enviados = [];
    const deps = { enviar: (m) => enviados.push(m) };
    const agora = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    for (let i = 0; i < fundo.FILA_MAX + 50; i++) fundo.aoReceberMensagem(legenda(`f${i}`), remetente(703), null, deps);
    enviados.length = 0;
    fundo.aceitarSessao(sessao(703), deps);
    expect(enviados.length).toBe(fundo.FILA_MAX);
    expect(enviados[0].text).toBe("f50");

    fundo.reiniciarSessoes();
    fundo.aoReceberMensagem(legenda("velha"), remetente(703), null, deps);
    agora.mockReturnValue(1_000_000 + fundo.FILA_IDADE_MS + 1);
    enviados.length = 0;
    fundo.aceitarSessao(sessao(703, "s3"), deps);
    expect(enviados).toEqual([]);
  });
});


describe("content.js — revisão final", () => {
  const mensagens = [];
  let tarefas = [];

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("depois de 3 s sem revisão a fala sai uma vez com caption_final", () => {
    vi.stubGlobal("chrome", { runtime: { sendMessage: (m) => mensagens.push(m) } });
    tarefas = [];
    vi.spyOn(globalThis, "setInterval").mockImplementation((fn) => {
      tarefas.push(fn);
      return 0;
    });
    const agora = vi.spyOn(Date, "now").mockReturnValue(5_000_000);
    mensagens.length = 0;
    Function(parserScript)();
    Function(contentScript)();
    const disparar = (m) => document.dispatchEvent(new CustomEvent(rtc.EVENTO, { detail: JSON.stringify(m) }));
    disparar({ tipo: "nomes", pares: [{ dispositivo: "dev-1", nome: "Pessoa Sintética" }] });
    disparar({ tipo: "legenda", canal: "captions_v2", dispositivo: "dev-1", utterance: 9, versao: 1,
      texto: "bom dia", t_inicio_ms: 1, t_ultimo_ms: 2 });
    const rodar = () => tarefas.forEach((fn) => fn());
    rodar();
    agora.mockReturnValue(5_001_000);
    rodar();
    agora.mockReturnValue(5_003_500);
    rodar();
    rodar();
    const falas = mensagens.filter((m) => m.evento && m.evento.tipo === "legenda").map((m) => m.evento);
    expect(falas.map((f) => f.caption_final === true)).toEqual([false, true]);
    expect(falas[1]).toMatchObject({ texto: "bom dia", caption_revision: 1, caption_started_ms: 1 });
  });
});
