import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const html = readFileSync(resolve(process.cwd(), "extension/meet/pairing.html"), "utf8");
const script = readFileSync(resolve(process.cwd(), "extension/meet/pairing.js"), "utf8");

function montar(respostas) {
  document.documentElement.innerHTML = html.replace(/<script[\s\S]*?<\/script>/g, "");
  const fila = [...respostas];
  vi.stubGlobal("chrome", {
    runtime: {
      lastError: undefined,
      sendMessage: (msg, cb) => cb(msg.tipo === "parear" ? { pronto: false, pareamento: "pendente" } : fila.shift()),
    },
    storage: { local: { set: (_v, cb) => cb() } },
  });
  Function(script)();
  document.getElementById("codigo").value = "pair-abcdefghijklmnop1234";
  document.getElementById("parear").click();
  return document.getElementById("estado");
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("pairing.js espera a confirmação do app", () => {
  it("sai de 'conectando' para sucesso quando o app confirma", () => {
    vi.useFakeTimers();
    const estado = montar([{ pareamento: "pendente" }, { pronto: true, pareamento: "confirmado" }]);
    expect(estado.getAttribute("data-estado")).toBe("carregando");
    vi.advanceTimersByTime(2500);
    expect(estado.getAttribute("data-estado")).toBe("sucesso");
  });

  it("código recusado vira erro com próximo passo", () => {
    vi.useFakeTimers();
    const estado = montar([{ pareamento: "recusado" }]);
    vi.advanceTimersByTime(1500);
    expect(estado.getAttribute("data-estado")).toBe("erro");
    expect(estado.textContent).toMatch(/novo código/i);
  });

  it("sem resposta, desiste com erro em vez de girar para sempre", () => {
    vi.useFakeTimers();
    const estado = montar(Array(100).fill({ pareamento: "pendente" }));
    vi.advanceTimersByTime(60000);
    expect(estado.getAttribute("data-estado")).toBe("erro");
    expect(estado.textContent).toMatch(/Identificar nomes do Meet/);
  });
});
