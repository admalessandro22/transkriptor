// T-15.E2 / FR-15.E2 — sem credencial, a extensão pareia sozinha pelo host nativo.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const fundo = require("../../extension/meet/background.js");
const manifest = JSON.parse(readFileSync(resolve(process.cwd(), "extension/meet/manifest.json"), "utf8"));


function deps(resposta) {
  const log = { pedidos: [], salvo: null, conectou: 0 };
  return {
    log,
    enviarNativo: (msg, cb) => { log.pedidos.push(msg); cb(resposta); },
    salvar: (valor, cb) => { log.salvo = valor; cb(); },
    conectar: () => { log.conectou += 1; },
  };
}


describe("background.js — pareamento nativo", () => {
  it("manifest pede nativeMessaging", () => {
    expect(manifest.permissions).toContain("nativeMessaging");
  });

  it("sem credencial usa nativo, guarda o código e conecta", async () => {
    const d = deps({ ok: true, codigo: "pair-abc_123", porta: 5051 });
    expect(await fundo.parearNativo(d)).toBe(true);
    expect(d.log.pedidos).toEqual([{ cmd: "obter_codigo_pareamento", v: 1 }]);
    expect(d.log.salvo).toEqual({ meetWsToken: "pair-abc_123" });
    expect(d.log.conectou).toBe(1);
    expect(fundo.estadoPareamento()).toBe("pendente");
  });

  it("nativo falha: nada é gravado e o pareamento manual continua disponível", async () => {
    for (const resposta of [{ ok: false, erro: "app_nao_iniciado" }, undefined, { ok: true, codigo: "sess-roubado" }]) {
      fundo.registrarPareamento("nenhum");
      const d = deps(resposta);
      expect(await fundo.parearNativo(d)).toBe(false);
      expect(d.log.salvo).toBe(null);
      expect(d.log.conectou).toBe(0);
      expect(fundo.estadoPareamento()).toBe("nenhum");
    }
  });

  it("host ausente (exceção do Chrome) não quebra", async () => {
    const d = deps(null);
    d.enviarNativo = () => { throw new Error("Specified native messaging host not found."); };
    expect(await fundo.parearNativo(d)).toBe(false);
  });
});
