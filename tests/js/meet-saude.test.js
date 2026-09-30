// T-15.B4 / NFR-15.B4 — saúde do canal de legendas e recuperação do silêncio.
import { describe, expect, it } from "vitest";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const rtc = require("../../extension/meet/rtc.js");
const fundo = require("../../extension/meet/background.js");

const MIN = 60000;


describe("rtc.js — vigia do canal", () => {
  it("silêncio com fala recente recria o canal", () => {
    const m = rtc.novoMonitorSaude(0);
    m.notarPacote("parsed", 0);
    m.notarFala(70000);
    expect(m.deveRecriar(75000)).toBe(true);
  });

  it("silêncio sem fala não recria", () => {
    const m = rtc.novoMonitorSaude(0);
    m.notarPacote("parsed", 0);
    m.notarFala(10000);
    expect(m.deveRecriar(75000)).toBe(false);
  });

  it("no máximo 3 tentativas", () => {
    const m = rtc.novoMonitorSaude(0);
    let recriadas = 0;
    for (let t = MIN + 5000; t < 20 * MIN; t += 10000) {
      m.notarFala(t);
      if (m.deveRecriar(t)) { m.notarRecriacao(); recriadas += 1; }
    }
    expect(recriadas).toBe(3);
    expect(m.resumo().recriacoes).toBe(3);
  });

  it("pacote novo zera o silêncio", () => {
    const m = rtc.novoMonitorSaude(0);
    m.notarFala(70000);
    m.notarPacote("parsed", 69000);
    expect(m.deveRecriar(75000)).toBe(false);
  });

  it("contadores e motivos sem conteúdo", () => {
    const m = rtc.novoMonitorSaude(0);
    m.notarPacote("parsed", 1);
    m.notarPacote("rejected", 2, "sem_dispositivo");
    m.notarPacote("rejected", 3, "sem_dispositivo");
    m.notarQueda();
    const r = m.resumo();
    expect(r.contadores.captions_v2).toEqual({ raw: 3, parsed: 1, rejected: 2 });
    expect(r.motivos).toEqual({ sem_dispositivo: 2 });
    expect(r.quedas).toBe(1);
  });

  it("esqueleto não contém texto nem bytes do texto", () => {
    const texto = [...Buffer.from("segredo da reunião", "utf8")];
    const interno = [8, 7, 18, texto.length, ...texto]; // {1: 7, 2: "segredo da reunião"}
    const pacote = new Uint8Array([10, interno.length, ...interno]);
    const esq = rtc.esqueleto(pacote);
    expect(esq).not.toMatch(/segredo|reuni/);
    expect(esq).toMatch(/^1:LEN\(\d+\)/);
    expect(rtc.esqueleto(new Uint8Array([255, 255]))).toMatch(/^nao-protobuf\(2\)$/);
  });
});


describe("background.js — envelope health", () => {
  it("só números, esqueleto curto e marcadores conhecidos", () => {
    const estado = fundo.estadoAba(801);
    fundo.aceitarSessao({ tipo: "sessao", connection_id: estado.connectionId, tab_id: "801", session_id: "s", meeting_key: "m" });
    const env = fundo.montarEnvelope({
      tipo: "saude", contadores: { captions_v2: { raw: 5, parsed: 4, rejected: 1 } }, motivos: { decode: 1, "<x>": 3 },
      recriacoes: 1, quedas: 0, esqueleto: "1:LEN(12){1:VARINT}", build_meet: "2026.09.21_00_RC00", tactiq: true, texto: "vazou",
    }, { frameId: 0, tab: { id: 801 }, url: "https://meet.google.com/abc-defg-hij" }, {});
    expect(env).toMatchObject({ kind: "health", raw: 5, parsed: 4, rejected: 1, recriacoes: 1, quedas: 0, tactiq: true });
    expect(env.motivos).toEqual({ decode: 1 });
    expect(JSON.stringify(env)).not.toContain("vazou");
  });
});
