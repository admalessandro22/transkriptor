import { describe, expect, it } from "vitest";
import { mapeamentoExibicao, nomeAmigavel, estadoDoFalante } from "../../static/js/participantes.js";

const seg = (id, cluster, assignment) => ({ segment_id: id, speaker_cluster_id: cluster, start_ms: 0, end_ms: 1, text: "", assignment });

describe("nomes confirmados pela legenda do Meet aparecem na transcrição", () => {
  const segs = [
    seg("s1", "FALANTE_00", { status: "confirmed", display_name: "Ana Fictícia", source: "caption" }),
    seg("s2", "FALANTE_00", { status: "confirmed", display_name: "Ana Fictícia", source: "caption" }),
    seg("s3", "FALANTE_01", { status: "confirmed", display_name: "Bruno Fictício", source: "caption" }),
    seg("s4", "FALANTE_01", { status: "confirmed", display_name: "Outro Nome", source: "caption" }),
    seg("s5", "FALANTE_02", { status: "suggested", display_name: "Carla Fictícia", source: "caption" }),
  ];

  it("confirmado unânime vira nome exibido; divergente e sugestão não", () => {
    const mapa = mapeamentoExibicao(segs, {});
    expect(mapa.FALANTE_00).toMatchObject({ display_name: "Ana Fictícia", origem: "caption" });
    expect(mapa.FALANTE_01).toBeUndefined();
    expect(mapa.FALANTE_02).toBeUndefined();
    expect(nomeAmigavel("FALANTE_00", mapa, ["FALANTE_00"])).toBe("Ana Fictícia");
    expect(estadoDoFalante("FALANTE_00", mapa, segs).estado).toBe("confirmado");
  });

  it("correção manual prevalece sobre a legenda", () => {
    const mapa = mapeamentoExibicao(segs, { FALANTE_00: { display_name: "Ana Corrigida", origem: "manual" } });
    expect(mapa.FALANTE_00.display_name).toBe("Ana Corrigida");
  });
});


describe("T-15.C3 — origem e confiança dos nomes automáticos do Meet", () => {
  it("nome de cluster automático mostra a origem e a confiança", () => {
    const mapa = { FALANTE_00: { display_name: "Ana Fictícia", origem: "meet_auto", confianca: 0.857 } };
    expect(estadoDoFalante("FALANTE_00", mapa, []).origem).toBe("Meet (automático) · 86%");
  });

  it("confirmação por segmento vinda do alinhamento aparece como Meet", () => {
    const segs = [seg("s1", "FALANTE_03", { status: "confirmed", auto: true, display_name: "Davi Fictício",
      source: "meet_alinhamento", confidence: 0.9 })];
    const mapa = mapeamentoExibicao(segs, {});
    expect(estadoDoFalante("FALANTE_03", mapa, segs).origem).toBe("Meet");
  });

  it("você pelo dispositivo próprio", () => {
    const segs = [seg("m1", "VOCÊ", { status: "confirmed", auto: true, display_name: "Alessandro (você)",
      source: "meet_proprio", confidence: 1 })];
    expect(estadoDoFalante("VOCÊ", mapeamentoExibicao(segs, {}), segs).origem).toBe("Meet (você)");
  });
});
