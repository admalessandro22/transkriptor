// T-15.B1 / FR-15.B1 (leitura) — idioma efetivo da legenda e o pedido pelo Meet.
// Só leitura: nenhum teste aqui envia nada ao Meet (a escrita é a T-15.B1W).
import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const rtc = require("../../extension/meet/rtc.js");
const fundo = require("../../extension/meet/background.js");

const contentScript = readFileSync(resolve(process.cwd(), "extension/meet/content.js"), "utf8");
const parserScript = readFileSync(resolve(process.cwd(), "extension/meet/parser.js"), "utf8");

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
function pacote(texto, idiomaAninhado) {
  const extra = idiomaAninhado ? msg(9, msg(2, idiomaAninhado)) : [];
  const legenda = [...msg(3, texto), ...msg(6, "spaces/SalaSintetica01/devices/127"), ...extra];
  return new Uint8Array(msg(1, [...num(1, 55), ...num(2, 1), ...msg(3, legenda)]));
}


describe("rtc.js — idioma da legenda", () => {
  it("lê o código de idioma aninhado na legenda", () => {
    expect(rtc.decodificarLegenda(pacote("bom dia", "pt-BR")).idioma).toBe("pt-BR");
  });

  it("texto da fala nunca vira idioma, mesmo parecendo código", () => {
    expect(rtc.decodificarLegenda(pacote("en-US")).idioma).toBe(null);
  });

  it("sem código, idioma nulo", () => {
    expect(rtc.decodificarLegenda(pacote("bom dia")).idioma).toBe(null);
  });

  it("extrai idioma pedido do corpo binário ou base64 do UpdateMediaSession", () => {
    const corpo = new Uint8Array(msg(1, msg(4, [...msg(1, "en-US"), ...num(2, 3)])));
    expect(rtc.idiomaDoCorpo(corpo)).toBe("en-US");
    expect(rtc.idiomaDoCorpo(Buffer.from(corpo).toString("base64"))).toBe("en-US");
    expect(rtc.idiomaDoCorpo(new Uint8Array(msg(1, "spaces/abc")))).toBe(null);
    expect(rtc.idiomaDoCorpo("não é protobuf")).toBe(null);
  });

  it("a extensão continua só lendo: nenhum send além do ack de legenda", () => {
    const fonte = readFileSync(resolve(process.cwd(), "extension/meet/rtc.js"), "utf8");
    const envios = fonte.match(/\.send\(/g) || [];
    expect(envios.length).toBe(1);
    expect(fonte).not.toMatch(/RTCDataChannel\.prototype\.send\s*=/);
  });
});


describe("content.js — idioma sobe como capacidade e na legenda", () => {
  const mensagens = [];
  let tarefas = [];

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.replaceChildren();
  });

  function carregar() {
    vi.stubGlobal("chrome", { runtime: { sendMessage: (m) => mensagens.push(m) } });
    tarefas = [];
    vi.spyOn(globalThis, "setInterval").mockImplementation((fn) => {
      tarefas.push(fn);
      return 0;
    });
    mensagens.length = 0;
    Function(parserScript)();
    Function(contentScript)();
  }

  const disparar = (m) => document.dispatchEvent(new CustomEvent(rtc.EVENTO, { detail: JSON.stringify(m) }));
  const capacidades = () => mensagens.filter((m) => m.evento && m.evento.tipo === "capabilities").map((m) => m.evento);

  it("legenda leva caption_lang e a mudança de idioma vira uma capacidade", () => {
    carregar();
    disparar({ tipo: "nomes", pares: [{ dispositivo: "dev-1", nome: "Pessoa Sintética" }] });
    const base = { tipo: "legenda", canal: "captions_v2", dispositivo: "dev-1", texto: "oi", versao: 1,
      t_inicio_ms: 1, t_ultimo_ms: 2 };
    disparar({ ...base, utterance: 1, texto: "um", idioma: "en-US" });
    disparar({ ...base, utterance: 2, texto: "dois", idioma: "en-US" });
    disparar({ tipo: "idioma", codigo: "en-US", origem: "meet", resultado: "lido" });
    disparar({ ...base, utterance: 3, texto: "três", idioma: "pt-BR" });
    tarefas.forEach((fn) => fn());
    const legendas = mensagens.filter((m) => m.evento && m.evento.tipo === "legenda").map((m) => m.evento);
    expect(legendas.map((e) => e.caption_lang)).toEqual(["en-US", "en-US", "pt-BR"]);
    expect(capacidades()).toEqual([
      expect.objectContaining({ caption_lang: "en-US" }),
      expect.objectContaining({ caption_lang: "en-US", lang_requested: "en-US" }),
      expect.objectContaining({ caption_lang: "pt-BR", lang_requested: "en-US" }),
    ]);
  });

  it("código inválido é ignorado", () => {
    carregar();
    disparar({ tipo: "idioma", codigo: "<script>", origem: "meet", resultado: "lido" });
    expect(capacidades()).toEqual([]);
  });
});


describe("background.js — idioma no envelope", () => {
  function sender(tab) {
    const estado = fundo.estadoAba(tab);
    fundo.aceitarSessao({ tipo: "sessao", connection_id: estado.connectionId, tab_id: String(tab),
      session_id: `s-${tab}`, meeting_key: `m-${tab}` });
    return { frameId: 0, tab: { id: tab }, url: "https://meet.google.com/abc-defg-hij" };
  }

  it("capacidade leva os idiomas válidos", () => {
    const env = fundo.montarEnvelope({ tipo: "capabilities", caption_lang: "pt-BR", lang_requested: "en-US" },
      sender(501), {});
    expect(env).toMatchObject({ kind: "capabilities", caption_lang: "pt-BR", lang_requested: "en-US" });
  });

  it("legenda v2 leva caption_lang; lixo não sobe", () => {
    const base = { tipo: "legenda", nome: "P", texto: "oi", caption_id: "rtc-1/dev-1", caption_revision: 1,
      participant_id: "dev-1", confidence_source: "caption", caption_started_ms: 1, caption_last_ms: 2 };
    expect(fundo.montarEnvelope({ ...base, caption_lang: "pt-BR" }, sender(502), {}).caption_lang).toBe("pt-BR");
    expect(fundo.montarEnvelope({ ...base, caption_lang: "x" }, sender(503), {})).not.toHaveProperty("caption_lang");
  });
});
