/**
 * Página de pareamento local (T-13.D2). Troca o código de uso único pela
 * credencial da sessão, guardada em chrome.storage.session (nunca em
 * content script, nunca em arquivo versionado).
 */
"use strict";

function validarCodigo(codigo) {
  return typeof codigo === "string" && /^pair-[A-Za-z0-9_-]{16,}$/.test(codigo.trim());
}

function informar(texto) {
  const el = typeof document !== "undefined" ? document.getElementById("estado") : null;
  if (el) el.textContent = texto;
}

function aoParear() {
  const campo = document.getElementById("codigo");
  const codigo = (campo.value || "").trim();
  if (!validarCodigo(codigo)) {
    informar("Código inválido. Confira o código exibido no aplicativo.");
    return;
  }
  chrome.storage.session.set({ meetWsToken: codigo }, function () {
    chrome.runtime.sendMessage({ tipo: "parear" }, function (resposta) {
      if (chrome.runtime.lastError) {
        informar("Service worker indisponível. Recarregue a extensão.");
        return;
      }
      informar(resposta && resposta.pronto ? "Pareado e conectado." : "Código guardado. Conectando...");
    });
  });
}

if (typeof document !== "undefined") {
  const botao = document.getElementById("parear");
  if (botao) botao.addEventListener("click", aoParear);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { validarCodigo };
}
