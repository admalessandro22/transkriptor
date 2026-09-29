// T-15.A2 / FR-15.A2 — o background responde ao ping de relógio da ponte e o
// envelope leva a amostra página↔parede para converter o horário da fala.
import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const fundo = require("../../extension/meet/background.js");
const rtc = require("../../extension/meet/rtc.js");

const contentScript = readFileSync(resolve(process.cwd(), "extension/meet/content.js"), "utf8");
const parserScript = readFileSync(resolve(process.cwd(), "extension/meet/parser.js"), "utf8");


describe("background.js — pong do relógio", () => {
  it("responde na hora com o próprio relógio de parede", () => {
    const { connectionId } = fundo.estadoAba(401);
    const pong = fundo.responderRelogio({ tipo: "relogio_ping", n: 3, connection_id: connectionId }, 5000.5);
    expect(pong).toEqual({ tipo: "relogio_pong", n: 3, connection_id: connectionId, client_wall_ms: 5000.5 });
  });

  it("ignora ping de conexão desconhecida ou malformado", () => {
    const { connectionId } = fundo.estadoAba(402);
    expect(fundo.responderRelogio({ tipo: "relogio_ping", n: 1, connection_id: "outra" }, 1)).toBe(null);
    expect(fundo.responderRelogio({ tipo: "relogio_ping", n: "1", connection_id: connectionId }, 1)).toBe(null);
    expect(fundo.responderRelogio({ tipo: "sessao", n: 1, connection_id: connectionId }, 1)).toBe(null);
  });

  it("envelope v2 leva a amostra página↔parede quando válida", () => {
    const estado = fundo.estadoAba(403);
    fundo.aceitarSessao({ tipo: "sessao", connection_id: estado.connectionId, tab_id: "403",
      session_id: "s-403", meeting_key: "m-403" });
    const sender = { frameId: 0, tab: { id: 403 }, url: "https://meet.google.com/abc-defg-hij" };
    const base = { tipo: "legenda", nome: "Pessoa Sintética", texto: "oi", caption_id: "rtc-1/dev-1",
      caption_revision: 1, participant_id: "dev-1", confidence_source: "caption",
      caption_started_ms: 1000, caption_last_ms: 1200 };
    const com = fundo.montarEnvelope({ ...base, page_perf_ms: 1300.5, page_wall_ms: 1299 }, sender, {});
    expect(com).toMatchObject({ schema_version: 2, page_perf_ms: 1300.5, page_wall_ms: 1299 });
    const sem = fundo.montarEnvelope({ ...base, page_perf_ms: "x" }, sender, {});
    expect(sem).not.toHaveProperty("page_perf_ms");
    expect(sem).not.toHaveProperty("page_wall_ms");
  });
});


describe("content.js — amostra página↔parede no envio", () => {
  const mensagens = [];
  let tarefas = [];

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.replaceChildren();
  });

  it("cada legenda com horário leva page_perf_ms e page_wall_ms do mesmo instante", () => {
    vi.stubGlobal("chrome", { runtime: { sendMessage: (m) => mensagens.push(m) } });
    tarefas = [];
    vi.spyOn(globalThis, "setInterval").mockImplementation((fn) => {
      tarefas.push(fn);
      return 0;
    });
    mensagens.length = 0;
    Function(parserScript)();
    Function(contentScript)();
    const disparar = (m) => document.dispatchEvent(new CustomEvent(rtc.EVENTO, { detail: JSON.stringify(m) }));
    disparar({ tipo: "nomes", pares: [{ dispositivo: "dev-1", nome: "Pessoa Sintética" }] });
    disparar({ tipo: "legenda", canal: "captions_v2", dispositivo: "dev-1", utterance: 1, versao: 1,
      texto: "oi", t_inicio_ms: 1000, t_ultimo_ms: 1000 });
    vi.spyOn(performance, "now").mockReturnValue(777);
    vi.spyOn(Date, "now").mockReturnValue(1_789_848_060_000);
    tarefas.forEach((fn) => fn());
    const evento = mensagens.find((m) => m.evento && m.evento.tipo === "legenda").evento;
    expect(evento.page_perf_ms).toBeCloseTo(performance.timeOrigin + 777, 6);
    expect(evento.page_wall_ms).toBe(1_789_848_060_000);
  });
});
