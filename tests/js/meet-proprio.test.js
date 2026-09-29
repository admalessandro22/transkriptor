// T-15.B2 / FR-15.B2 — qual dispositivo da sala é o do próprio usuário.
import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const rtc = require("../../extension/meet/rtc.js");
const fundo = require("../../extension/meet/background.js");

const contentScript = readFileSync(resolve(process.cwd(), "extension/meet/content.js"), "utf8");
const parserScript = readFileSync(resolve(process.cwd(), "extension/meet/parser.js"), "utf8");


describe("rtc.js — dispositivo próprio no corpo das chamadas do Meet", () => {
  const corpo = "\n\x12spaces/SalaSintetica01/devices/88\x1a\x02ok";

  it("extrai de texto, bytes e base64 sem vazar a sala", () => {
    expect(rtc.dispositivoProprioEm(corpo)).toBe("dev-88");
    expect(rtc.dispositivoProprioEm(new TextEncoder().encode(corpo))).toBe("dev-88");
    expect(rtc.dispositivoProprioEm(new TextEncoder().encode(corpo).buffer)).toBe("dev-88");
    expect(rtc.dispositivoProprioEm(Buffer.from(corpo, "latin1").toString("base64"))).toBe("dev-88");
  });

  it("sem dispositivo, nulo", () => {
    expect(rtc.dispositivoProprioEm("spaces/SalaSintetica01")).toBe(null);
    expect(rtc.dispositivoProprioEm(undefined)).toBe(null);
  });
});


describe("content.js — próprio dispositivo sobe uma vez", () => {
  const mensagens = [];

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("primeiro valor vale; repetição e segundo valor são ignorados", () => {
    vi.stubGlobal("chrome", { runtime: { sendMessage: (m) => mensagens.push(m) } });
    vi.spyOn(globalThis, "setInterval").mockImplementation(() => 0);
    mensagens.length = 0;
    Function(parserScript)();
    Function(contentScript)();
    const disparar = (m) => document.dispatchEvent(new CustomEvent(rtc.EVENTO, { detail: JSON.stringify(m) }));
    disparar({ tipo: "proprio", dispositivo: "dev-88" });
    disparar({ tipo: "proprio", dispositivo: "dev-88" });
    disparar({ tipo: "proprio", dispositivo: "dev-99" });
    disparar({ tipo: "proprio", dispositivo: "<x>" });
    const proprios = mensagens.filter((m) => m.evento && m.evento.tipo === "proprio").map((m) => m.evento);
    expect(proprios).toEqual([expect.objectContaining({ participant_id: "dev-88" })]);
  });
});


describe("background.js — envelope self_device", () => {
  function sender(tab) {
    const estado = fundo.estadoAba(tab);
    fundo.aceitarSessao({ tipo: "sessao", connection_id: estado.connectionId, tab_id: String(tab),
      session_id: `s-${tab}`, meeting_key: `m-${tab}` });
    return { frameId: 0, tab: { id: tab }, url: "https://meet.google.com/abc-defg-hij" };
  }

  it("vira kind self_device com o id do dispositivo", () => {
    const env = fundo.montarEnvelope({ tipo: "proprio", participant_id: "dev-88" }, sender(601), {});
    expect(env).toMatchObject({ kind: "self_device", participant_id: "dev-88" });
  });

  it("id inválido não sobe", () => {
    expect(fundo.montarEnvelope({ tipo: "proprio", participant_id: "Ana" }, sender(602), {})).toBe(null);
  });
});
