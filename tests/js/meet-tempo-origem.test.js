// T-15.A1 / FR-15.A1 — o horário da fala nasce na chegada do primeiro pacote
// e atravessa content.js e background.js sem ser trocado pelo relógio do envio.
import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const rtc = require("../../extension/meet/rtc.js");
const fundo = require("../../extension/meet/background.js");

const contentScript = readFileSync(resolve(process.cwd(), "extension/meet/content.js"), "utf8");
const parserScript = readFileSync(resolve(process.cwd(), "extension/meet/parser.js"), "utf8");


// ---- protobuf sintético mínimo (mesmo formato de meet-rtc.test.js) ----

function varint(x) {
  const out = [];
  while (x >= 128) {
    out.push((x % 128) | 128);
    x = Math.floor(x / 128);
  }
  out.push(x);
  return out;
}

function msg(numero, conteudo) {
  const bytes = typeof conteudo === "string" ? [...Buffer.from(conteudo, "utf8")] : conteudo;
  return [...varint(numero * 8 + 2), ...varint(bytes.length), ...bytes];
}

function num(numero, valor) {
  return [...varint(numero * 8), ...varint(valor)];
}

function pacoteLegenda(utterance, versao, dispositivo, texto) {
  const legenda = [...msg(3, texto), ...msg(6, `spaces/SalaSintetica01/devices/${dispositivo}`)];
  const fala = [...num(1, utterance), ...num(2, versao), ...msg(3, legenda)];
  return new Uint8Array(msg(1, fala));
}


describe("rtc.js — horário carimbado na chegada do pacote", () => {
  it("relógio da página é timeOrigin + performance.now()", () => {
    vi.spyOn(performance, "now").mockReturnValue(250.5);
    expect(rtc.agoraPagina()).toBeCloseTo(performance.timeOrigin + 250.5, 6);
  });

  it("revisão não altera t_inicio; t_ultimo acompanha a última chegada", () => {
    const registro = rtc.novoRegistroTempos();
    const base = { dispositivo: "dev-1", utterance: 7, texto: "vamos" };
    const primeira = rtc.carimbarLegenda(registro, { ...base, versao: 0 }, 1000);
    const segunda = rtc.carimbarLegenda(registro, { ...base, versao: 1, texto: "vamos revisar" }, 2200);
    expect(primeira).toMatchObject({ t_inicio_ms: 1000, t_ultimo_ms: 1000 });
    expect(segunda).toMatchObject({ t_inicio_ms: 1000, t_ultimo_ms: 2200, texto: "vamos revisar" });
  });

  it("falas diferentes do mesmo dispositivo têm horários independentes", () => {
    const registro = rtc.novoRegistroTempos();
    rtc.carimbarLegenda(registro, { dispositivo: "dev-1", utterance: 7, versao: 0, texto: "a" }, 1000);
    const outra = rtc.carimbarLegenda(registro, { dispositivo: "dev-1", utterance: 8, versao: 0, texto: "b" }, 5000);
    expect(outra).toMatchObject({ t_inicio_ms: 5000, t_ultimo_ms: 5000 });
  });

  it("registro de horários é limitado", () => {
    const registro = rtc.novoRegistroTempos();
    for (let i = 1; i <= 600; i++) {
      rtc.carimbarLegenda(registro, { dispositivo: "dev-1", utterance: i, versao: 0, texto: "x" }, i);
    }
    expect(registro.size).toBeLessThanOrEqual(rtc.MAX_TEMPOS);
  });

  it("pacote do canal sai publicado com o horário da primeira chegada", async () => {
    const registro = rtc.novoRegistroTempos();
    const publicados = [];
    const acks = [];
    const deps = {
      registro,
      publicar: (m) => publicados.push(m),
      enviarAck: (b) => acks.push(b),
    };
    await rtc.tratarPacoteLegenda(pacoteLegenda(4411, 1, 127, "bom"), { ...deps, agora: () => 1000 });
    await rtc.tratarPacoteLegenda(pacoteLegenda(4411, 2, 127, "bom dia"), { ...deps, agora: () => 1800 });
    expect(acks).toHaveLength(2);
    expect(publicados[1]).toMatchObject({
      tipo: "legenda",
      canal: "captions_v2",
      dispositivo: "dev-127",
      utterance: 4411,
      versao: 2,
      texto: "bom dia",
      t_inicio_ms: 1000,
      t_ultimo_ms: 1800,
    });
  });
});


describe("content.js — preserva o início da fala entre revisões", () => {
  const mensagens = [];
  let tarefas = [];

  function carregar() {
    vi.stubGlobal("chrome", { runtime: { sendMessage: (m) => mensagens.push(m) } });
    tarefas = [];
    vi.spyOn(globalThis, "setInterval").mockImplementation((fn) => {
      tarefas.push(fn);
      return 0;
    });
    mensagens.length = 0;
    document.body.replaceChildren();
    Function(parserScript)();
    Function(contentScript)();
  }

  function rtcEvento(m) {
    document.dispatchEvent(new CustomEvent(rtc.EVENTO, { detail: JSON.stringify(m) }));
  }

  function rodarTarefas() {
    tarefas.forEach((fn) => fn());
  }

  function legendas() {
    return mensagens.filter((m) => m.evento && m.evento.tipo === "legenda").map((m) => m.evento);
  }

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.replaceChildren();
  });

  const fala = { tipo: "legenda", canal: "captions_v2", dispositivo: "dev-127", utterance: 6 };

  it("envio de cada revisão leva o início da primeira e o fim da última", () => {
    carregar();
    rtcEvento({ tipo: "nomes", pares: [{ dispositivo: "dev-127", nome: "Pessoa Sintética" }] });
    rtcEvento({ ...fala, versao: 1, texto: "vamos", t_inicio_ms: 1000, t_ultimo_ms: 1000 });
    rodarTarefas();
    rtcEvento({ ...fala, versao: 2, texto: "vamos revisar", t_inicio_ms: 1000, t_ultimo_ms: 2200 });
    rodarTarefas();

    const enviadas = legendas();
    expect(enviadas).toHaveLength(2);
    expect(enviadas[0]).toMatchObject({ caption_started_ms: 1000, caption_last_ms: 1000 });
    expect(enviadas[1]).toMatchObject({
      caption_started_ms: 1000,
      caption_last_ms: 2200,
      origin_channel: "captions_v2",
    });
  });

  it("revisão com início posterior não empurra o início da fala", () => {
    carregar();
    rtcEvento({ tipo: "nomes", pares: [{ dispositivo: "dev-127", nome: "Pessoa Sintética" }] });
    rtcEvento({ ...fala, versao: 1, texto: "vamos", t_inicio_ms: 1000, t_ultimo_ms: 1000 });
    rtcEvento({ ...fala, versao: 2, texto: "vamos revisar", t_inicio_ms: 1500, t_ultimo_ms: 2200 });
    rodarTarefas();
    expect(legendas()[0]).toMatchObject({ caption_started_ms: 1000, caption_last_ms: 2200 });
  });

  it("flush tardio não substitui o horário da fala", () => {
    carregar();
    rtcEvento({ tipo: "nomes", pares: [{ dispositivo: "dev-127", nome: "Pessoa Sintética" }] });
    rtcEvento({ ...fala, versao: 1, texto: "vamos", t_inicio_ms: 1000, t_ultimo_ms: 1300 });
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 5000);
    rodarTarefas();
    expect(legendas()[0]).toMatchObject({ caption_started_ms: 1000, caption_last_ms: 1300 });
  });

  it("legenda sem horário (rtc antigo) segue sem os campos novos", () => {
    carregar();
    rtcEvento({ tipo: "nomes", pares: [{ dispositivo: "dev-127", nome: "Pessoa Sintética" }] });
    rtcEvento({ ...fala, versao: 1, texto: "vamos" });
    rodarTarefas();
    expect(legendas()[0]).not.toHaveProperty("caption_started_ms");
  });
});


describe("background.js — envelope v2 com o tempo da fala", () => {
  function sessaoPara(tabId) {
    const estado = fundo.estadoAba(tabId);
    fundo.aceitarSessao({
      tipo: "sessao", connection_id: estado.connectionId, tab_id: String(tabId),
      session_id: `s-${tabId}`, meeting_key: `m-${tabId}`,
    });
    return { frameId: 0, tab: { id: tabId }, url: "https://meet.google.com/abc-defg-hij" };
  }

  const legenda = {
    tipo: "legenda", nome: "Pessoa Sintética", texto: "bom dia", caption_id: "rtc-1/dev-127",
    caption_revision: 2, participant_id: "dev-127", confidence_source: "caption",
  };

  it("legenda com horário vira schema 2 e mantém os tempos da fala", () => {
    const sender = sessaoPara(301);
    const env = fundo.montarEnvelope(
      { ...legenda, caption_started_ms: 1000.5, caption_last_ms: 2200.25, origin_channel: "captions_v2" },
      sender, { wallMs: 9_000_000, monotonicMs: 42 }
    );
    expect(env).toMatchObject({
      schema_version: 2,
      kind: "caption",
      caption_started_ms: 1000.5,
      caption_last_ms: 2200.25,
      origin_channel: "captions_v2",
      client_wall_ms: 9_000_000,
    });
  });

  it("legenda sem horário continua schema 1", () => {
    const env = fundo.montarEnvelope(legenda, sessaoPara(302), { wallMs: 1, monotonicMs: 1 });
    expect(env.schema_version).toBe(1);
    expect(env).not.toHaveProperty("caption_started_ms");
  });

  it("horários incoerentes não sobem", () => {
    const env = fundo.montarEnvelope(
      { ...legenda, caption_started_ms: 3000, caption_last_ms: 2000 },
      sessaoPara(303), { wallMs: 1, monotonicMs: 1 }
    );
    expect(env.schema_version).toBe(1);
    expect(env).not.toHaveProperty("caption_started_ms");
  });
});
