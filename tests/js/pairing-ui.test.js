// UX-14.E5 — página de pareamento com passos, estados e a identidade da Central (T-14.E5).
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const raiz = resolve(__dirname, "../..");
const html = readFileSync(resolve(raiz, "extension/meet/pairing.html"), "utf8");

function montar(chrome) {
  document.documentElement.innerHTML = html.replace(/<script[^>]*><\/script>/g, "");
  globalThis.chrome = chrome;
  // pairing.js é CJS carregado pelo require do Node: limpar o cache faz o
  // script rodar de novo e ligar os listeners no DOM recém-montado.
  const caminho = require.resolve("../../extension/meet/pairing.js");
  delete require.cache[caminho];
  return require(caminho);
}

function chromeFalso({ pronto = true, pareamento = "confirmado", lastError = undefined, adiar = false } = {}) {
  return {
    storage: { local: { set: (obj, cb) => cb && cb() } },
    runtime: {
      lastError,
      sendMessage: (msg, cb) => { if (!adiar && cb) cb({ pronto, pareamento }); },
    },
  };
}

describe("pareamento (pairing.html + pairing.js)", () => {
  beforeEach(() => { delete globalThis.chrome; });

  it("mantém os IDs #codigo, #parear e #estado e os passos numerados", () => {
    montar(chromeFalso());
    expect(document.querySelector("#codigo")).not.toBeNull();
    expect(document.querySelector("#parear")).not.toBeNull();
    expect(document.querySelector("#estado[role=status]")).not.toBeNull();
    const passos = [...document.querySelectorAll("ol.passos li")].map((li) => li.textContent);
    expect(passos).toHaveLength(4);
    expect(passos[0]).toMatch(/Diagnóstico/);
    expect(passos[3]).toMatch(/Parear/);
    expect(document.querySelector('link[rel=stylesheet][href="pairing.css"]')).not.toBeNull();
    expect(document.querySelector("style")).toBeNull();
    expect(html).not.toMatch(/https?:\/\//);
  });

  it("sucesso (app confirmou o código) mostra estado e desabilita campo", () => {
    montar(chromeFalso({ pronto: true, pareamento: "confirmado" }));
    document.querySelector("#codigo").value = "pair-codigo-de-uso-unico-12345";
    document.querySelector("#parear").click();
    const estado = document.querySelector("#estado");
    expect(estado.dataset.estado).toBe("sucesso");
    expect(estado.textContent).toMatch(/Pareado/);
    expect(document.querySelector("#codigo").disabled).toBe(true);
    expect(document.querySelector("#parear").disabled).toBe(true);
  });

  it("erro mostra proximo passo", () => {
    montar(chromeFalso({ lastError: { message: "no worker" } }));
    document.querySelector("#codigo").value = "pair-codigo-de-uso-unico-12345";
    document.querySelector("#parear").click();
    const estado = document.querySelector("#estado");
    expect(estado.dataset.estado).toBe("erro");
    expect(estado.textContent).toMatch(/Recarregue a extensão/);
    expect(estado.textContent).toMatch(/Próximo passo/);
    expect(document.querySelector("#codigo").disabled).toBe(false);
    expect(document.querySelector("#parear").disabled).toBe(false);
  });

  it("código sem o prefixo pair- é recusado antes de qualquer mensagem", () => {
    const chrome = chromeFalso();
    chrome.runtime.sendMessage = vi.fn();
    montar(chrome);
    const campo = document.querySelector("#codigo");
    campo.value = "abc";
    document.querySelector("#parear").click();
    expect(chrome.runtime.sendMessage).not.toHaveBeenCalled();
    expect(document.querySelector("#estado").dataset.estado).toBe("erro");
    expect(document.querySelector("#estado").textContent).toMatch(/pair-/);
    expect(campo.getAttribute("aria-invalid")).toBe("true");
  });

  it("enquanto aguarda o service worker fica em carregando com o botão travado", () => {
    montar(chromeFalso({ adiar: true }));
    document.querySelector("#codigo").value = "pair-codigo-de-uso-unico-12345";
    document.querySelector("#parear").click();
    expect(document.querySelector("#estado").dataset.estado).toBe("carregando");
    expect(document.querySelector("#parear").disabled).toBe(true);
  });

  it("resposta sem pronto guarda o código e informa que está conectando", () => {
    montar(chromeFalso({ pronto: false, pareamento: "pendente" }));
    document.querySelector("#codigo").value = "pair-codigo-de-uso-unico-12345";
    document.querySelector("#parear").click();
    expect(document.querySelector("#estado").dataset.estado).toBe("carregando");
    expect(document.querySelector("#estado").textContent).toMatch(/Conectando/);
  });
});
