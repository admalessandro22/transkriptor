import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const parser = require("../../extension/meet/parser.js");


function fixture(nome) {
  return readFileSync(resolve(process.cwd(), "tests/js/fixtures", nome), "utf8");
}


function documento(html) {
  document.body.replaceChildren();
  const inv = document.createElement("div");
  inv.innerHTML = html;
  document.body.append(inv);
  return inv;
}


describe("parser.js real (D3)", () => {
  it("extrai legenda com id e revisao da fixture", () => {
    const raiz = documento(fixture("meet-legendas-v1.html"));
    const falas = parser.extrairLegendas(raiz);
    expect(falas).toHaveLength(1);
    expect(falas[0]).toMatchObject({
      id: "cap-001",
      nome: "Pessoa Sintética",
      texto: "vamos revisar o cronograma",
      revisao: 2,
      efemero: false
    });
  });

  it("tile visivel silencioso entra no roster, nao na fala", () => {
    const raiz = documento(fixture("meet-homonimos-v1.html"));
    const falas = parser.extrairLegendas(raiz);
    expect(falas.every((f) => f.nome !== "" && f.texto !== "")).toBe(true);
    const roster = parser.extrairRoster(raiz);
    expect(roster.length).toBeGreaterThanOrEqual(2);
    const atividade = parser.extrairAtividade(raiz);
    expect(Array.isArray(atividade)).toBe(true);
  });

  it("homonimos nao se fundem: ids locais distintos", () => {
    const raiz = documento(fixture("meet-homonimos-v1.html"));
    const roster = parser.extrairRoster(raiz);
    const anas = roster.filter((p) => p.nome === "Ana Sintética");
    expect(anas.length).toBe(2);
    expect(new Set(anas.map((p) => p.id)).size).toBe(2);
  });

  it("revisao maior substitui; bloco repetido nao duplica", () => {
    const raiz = documento(fixture("meet-homonimos-v1.html"));
    const falas = parser.extrairLegendas(raiz);
    const final = parser.consolidarRevisoes([...falas, ...falas]);
    const cap = final.filter((f) => f.id === "cap-010");
    expect(cap).toHaveLength(1);
    expect(cap[0]).toMatchObject({ revisao: 3, texto: "primeira fala revisada" });
  });

  it("DOM sem seletores emite capacidade indisponivel", () => {
    const raiz = documento(fixture("meet-sem-seletores-v1.html"));
    expect(parser.extrairLegendas(raiz)).toEqual([]);
    const cap = parser.avaliarCapacidades(raiz);
    expect(cap.legendas).toBe(false);
    expect(typeof cap.motivo).toBe("string");
  });

  it("legenda desligada nao fabrica fala", () => {
    const raiz = documento("<main></main>");
    expect(parser.extrairLegendas(raiz)).toEqual([]);
    expect(parser.avaliarCapacidades(raiz).legendas).toBe(false);
  });

  it("fala com camera desligada sai da legenda, nao do video", () => {
    const raiz = documento(fixture("meet-legendas-v1.html"));
    const falas = parser.extrairLegendas(raiz);
    expect(falas.length).toBe(1);
    expect(falas[0].texto).toContain("cronograma");
  });
});
