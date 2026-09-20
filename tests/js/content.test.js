import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";


const contentScript = readFileSync(
  resolve(process.cwd(), "extension/meet/content.js"),
  "utf8"
);


const mensagens = [];

function carregarContentScriptReal() {
  vi.stubGlobal("chrome", {
    runtime: {
      sendMessage: (msg) => {
        mensagens.push(msg);
      }
    }
  });
  vi.spyOn(globalThis, "setInterval").mockImplementation(() => 0);
  mensagens.length = 0;
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
  it("entrega a legenda ao service worker sem segredo nem WebSocket direto", async () => {
    expect(contentScript).not.toMatch(/new\s+WebSocket/);
    expect(contentScript).not.toMatch(/MEET_WS_TOKEN/);
    carregarContentScriptReal();
    const legenda = document.createElement("section");
    legenda.setAttribute("data-caption-block", "");
    legenda.innerHTML =
      '<span data-speaker-name="Pessoa Sintética"></span>' +
      '<span data-caption-text>vamos revisar o cronograma</span>';
    document.body.append(legenda);

    await Promise.resolve();
    await Promise.resolve();

    expect(mensagens).toHaveLength(1);
    expect(mensagens[0]).toMatchObject({
      tipo: "meet-evento",
      evento: {
        nome: "Pessoa Sintética",
        tipo: "legenda",
        texto: "vamos revisar o cronograma"
      }
    });
  });
});
