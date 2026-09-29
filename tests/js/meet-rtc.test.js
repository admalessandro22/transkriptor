import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";
import { gzipSync } from "node:zlib";


const require = createRequire(import.meta.url);
const rtc = require("../../extension/meet/rtc.js");

const manifest = JSON.parse(
  readFileSync(resolve(process.cwd(), "extension/meet/manifest.json"), "utf8")
);
const contentScript = readFileSync(resolve(process.cwd(), "extension/meet/content.js"), "utf8");
const parserScript = readFileSync(resolve(process.cwd(), "extension/meet/parser.js"), "utf8");


// ---- protobuf sintético no formato observado no Meet (set/2026) ----

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

const SALA = "spaces/SalaSintetica01";

function pacoteLegenda(utterance, versao, dispositivo, texto) {
  const legenda = [
    ...num(2, 1),
    ...msg(3, texto),
    ...msg(4, num(14, 116)),
    ...msg(6, `${SALA}/devices/${dispositivo}`),
    ...num(9, 1),
  ];
  const fala = [...num(1, utterance), ...num(2, versao), ...msg(3, legenda)];
  return new Uint8Array([...msg(1, fala), ...msg(6, num(1, 1790273670))]);
}

function parNome(dispositivo, nome) {
  return [...msg(1, `${SALA}/devices/${dispositivo}`), ...msg(2, nome)];
}


describe("rtc.js — legendas e nomes sem CC na tela", () => {
  it("roda no mundo da página desde o início, só no Meet", () => {
    const entrada = manifest.content_scripts.find((c) => c.js.includes("rtc.js"));
    expect(entrada).toMatchObject({ world: "MAIN", run_at: "document_start" });
    expect(entrada.matches).toEqual(["https://meet.google.com/*"]);
  });

  it("decodifica a legenda do captions_v2 sem vazar o id da sala", () => {
    const legenda = rtc.decodificarLegenda(pacoteLegenda(6, 9, 127, "vamos revisar o cronograma"));
    expect(legenda).toEqual({
      dispositivo: "dev-127",
      utterance: 6,
      versao: 9,
      texto: "vamos revisar o cronograma",
      idioma: null, // T-15.B1: a fixture não traz código de idioma em texto
    });
    expect(JSON.stringify(legenda)).not.toContain("SalaSintetica01");
  });

  it("recusa pacote sem dispositivo ou utterance", () => {
    const semFala = new Uint8Array(msg(6, num(1, 5)));
    expect(rtc.decodificarLegenda(semFala)).toBeNull();
    const semDisp = new Uint8Array(msg(1, [...num(1, 3), ...num(2, 1), ...msg(3, msg(3, "oi"))]));
    expect(rtc.decodificarLegenda(semDisp)).toBeNull();
  });

  it("descompacta gzip com prefixo, como o canal entrega", async () => {
    const cru = pacoteLegenda(7, 1, 42, "texto compactado");
    const embrulhado = new Uint8Array([18, 98, ...gzipSync(Buffer.from(cru))]);
    const u = await rtc.descompactar(embrulhado);
    expect(rtc.decodificarLegenda(u)).toMatchObject({ dispositivo: "dev-42", texto: "texto compactado" });
  });

  it("ack referencia utterance e versão", () => {
    const ack = rtc.lerProto(rtc.ackLegenda(300, 12));
    const ref = rtc.lerProto(rtc.lerProto(ack[1][0])[1][0]);
    expect(ref[1][0]).toBe(300);
    expect(ref[2][0]).toBe(12);
    expect(ref[3][0]).toBe(1);
  });

  it("lê nome do canal collections e da resposta SyncMeetingSpaceCollections", () => {
    const aninhado = msg(1, msg(2, msg(13, msg(1, msg(2, parNome(127, "Pessoa Sintética"))))));
    expect(rtc.decodificarDispositivo(new Uint8Array(aninhado))).toEqual([
      { dispositivo: "dev-127", nome: "Pessoa Sintética" },
    ]);
    const colecao = msg(2, msg(2, [...msg(2, parNome(1, "Ana Fictícia")), ...msg(2, parNome(2, "Bruno Fictício"))]));
    expect(rtc.decodificarColecao(new Uint8Array(colecao))).toEqual([
      { dispositivo: "dev-1", nome: "Ana Fictícia" },
      { dispositivo: "dev-2", nome: "Bruno Fictício" },
    ]);
  });

  it("não abre WebSocket nem fala com a rede", () => {
    const fonte = readFileSync(resolve(process.cwd(), "extension/meet/rtc.js"), "utf8");
    expect(fonte).not.toMatch(/new\s+WebSocket|chrome\.runtime|XMLHttpRequest\(/);
  });
});


describe("content.js — fala do canal RTC vira evento com nome", () => {
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

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.replaceChildren();
  });

  it("entrega só a última revisão, com nome vindo do canal collections", () => {
    carregar();
    rtcEvento({ tipo: "nomes", pares: [{ dispositivo: "dev-127", nome: "Pessoa Sintética" }] });
    rtcEvento({ tipo: "legenda", dispositivo: "dev-127", utterance: 6, versao: 1, texto: "vamos" });
    rtcEvento({ tipo: "legenda", dispositivo: "dev-127", utterance: 6, versao: 3, texto: "vamos revisar o cronograma" });
    rtcEvento({ tipo: "legenda", dispositivo: "dev-127", utterance: 6, versao: 2, texto: "vamos revisar" });
    rodarTarefas();

    const falas = mensagens.filter((m) => m.evento && m.evento.tipo === "legenda");
    expect(falas).toHaveLength(1);
    expect(falas[0].evento).toMatchObject({
      nome: "Pessoa Sintética",
      texto: "vamos revisar o cronograma",
      caption_id: "rtc-6/dev-127",
      caption_revision: 3,
      participant_id: "dev-127",
      confidence_source: "caption",
    });
  });

  it("sem nome no canal, usa o tile; sem nenhum, espera em vez de inventar", () => {
    carregar();
    rtcEvento({ tipo: "legenda", dispositivo: "dev-9", utterance: 1, versao: 1, texto: "bom dia" });
    rodarTarefas();
    expect(mensagens.filter((m) => m.evento && m.evento.tipo === "legenda")).toHaveLength(0);

    const tile = document.createElement("div");
    tile.setAttribute("data-participant-id", "spaces/SalaSintetica01/devices/9");
    tile.innerHTML = '<span class="notranslate">Ana Fictícia</span>';
    document.body.append(tile);
    rodarTarefas();

    const falas = mensagens.filter((m) => m.evento && m.evento.tipo === "legenda");
    expect(falas).toHaveLength(1);
    expect(falas[0].evento).toMatchObject({ nome: "Ana Fictícia", texto: "bom dia" });
  });

  it("ignora eventos malformados", () => {
    carregar();
    document.dispatchEvent(new CustomEvent(rtc.EVENTO, { detail: "{nao json" }));
    rtcEvento({ tipo: "legenda", dispositivo: 5, utterance: "x", texto: "oi" });
    rtcEvento({ tipo: "nomes", pares: [{ dispositivo: "dev-1" }] });
    rodarTarefas();
    expect(mensagens.filter((m) => m.evento && m.evento.tipo === "legenda")).toHaveLength(0);
  });
});
