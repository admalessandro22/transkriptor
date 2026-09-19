import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";


const contentScript = readFileSync(
  resolve(process.cwd(), "extension/meet/content.js"),
  "utf8"
);


class WebSocketFalsa {
  static OPEN = 1;
  static instancias = [];

  constructor(url) {
    this.url = url;
    this.readyState = WebSocketFalsa.OPEN;
    this.mensagens = [];
    WebSocketFalsa.instancias.push(this);
  }

  send(mensagem) {
    this.mensagens.push(mensagem);
  }

  close() {
    this.readyState = 3;
  }
}


function carregarContentScriptReal() {
  vi.stubGlobal("WebSocket", WebSocketFalsa);
  vi.spyOn(globalThis, "setInterval").mockImplementation(() => 0);
  WebSocketFalsa.instancias = [];
  document.body.replaceChildren();

  // Executa o arquivo de produção sem reimplementar o parser no teste.
  Function(contentScript)();
  if (document.readyState === "loading") {
    document.dispatchEvent(new Event("DOMContentLoaded"));
  }
}


afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.body.replaceChildren();
});


describe("content.js real", () => {
  it("envia a legenda extraída do DOM pelo parser de produção", async () => {
    carregarContentScriptReal();
    const legenda = document.createElement("section");
    legenda.setAttribute("data-caption-block", "");
    legenda.innerHTML =
      '<span data-speaker-name="Pessoa Sintética"></span>' +
      '<span data-caption-text>vamos revisar o cronograma</span>';
    document.body.append(legenda);

    await Promise.resolve();
    await Promise.resolve();

    const socket = WebSocketFalsa.instancias.at(-1);
    expect(socket).toBeDefined();
    expect(socket.mensagens).toHaveLength(1);
    expect(JSON.parse(socket.mensagens[0])).toMatchObject({
      nome: "Pessoa Sintética",
      tipo: "legenda",
      texto: "vamos revisar o cronograma"
    });
  });
});
