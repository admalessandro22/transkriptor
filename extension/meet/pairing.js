/**
 * Página de pareamento local (T-13.D2, visual T-14.E5). Troca o código de uso
 * único pela credencial da sessão, guardada em chrome.storage.session (nunca em
 * content script, nunca em arquivo versionado).
 *
 * Estados de `#estado` (data-estado): carregando | sucesso | erro. Sucesso trava
 * o campo e o botão; erro diz o próximo passo. Nenhuma requisição além da
 * mensagem ao service worker (que fala só com o WebSocket local).
 */
"use strict";

var PREFIXO = "pair-";

function validarCodigo(codigo) {
  return typeof codigo === "string" && /^pair-[A-Za-z0-9_-]{16,}$/.test(codigo.trim());
}

function $(id) {
  return typeof document !== "undefined" ? document.getElementById(id) : null;
}

var ICONES = {
  carregando: "",
  sucesso: "✓",
  erro: "!",
};

/** Atualiza `#estado` e os controles. `proximoPasso` só aparece em erro. */
function definirEstado(estado, texto, proximoPasso) {
  var el = $("estado");
  if (!el) return;
  el.textContent = "";
  if (estado) {
    el.setAttribute("data-estado", estado);
    var icone = document.createElement("span");
    icone.className = "icone";
    icone.setAttribute("aria-hidden", "true");
    icone.textContent = ICONES[estado] || "";
    el.appendChild(icone);
    var corpo = document.createElement("span");
    corpo.textContent = texto;
    if (proximoPasso) {
      var proximo = document.createElement("span");
      proximo.className = "proximo";
      proximo.textContent = "Próximo passo: " + proximoPasso;
      corpo.appendChild(proximo);
    }
    el.appendChild(corpo);
  } else {
    el.removeAttribute("data-estado");
  }
  var campo = $("codigo");
  var botao = $("parear");
  var travar = estado === "sucesso";
  if (campo) campo.disabled = travar;
  if (botao) botao.disabled = travar || estado === "carregando";
}

function informar(texto) {
  definirEstado(null, texto);
  var el = $("estado");
  if (el) el.textContent = texto;
}

function aoParear() {
  var campo = $("codigo");
  var codigo = (campo && campo.value ? campo.value : "").trim();
  if (!validarCodigo(codigo)) {
    if (campo) campo.setAttribute("aria-invalid", "true");
    definirEstado(
      "erro",
      codigo.indexOf(PREFIXO) === 0
        ? "Código incompleto. Copie o código inteiro exibido no Diagnóstico."
        : "Código inválido: ele começa com " + PREFIXO + ".",
      "abra o Diagnóstico do Transkriptor e copie o código de pareamento."
    );
    return;
  }
  if (campo) campo.removeAttribute("aria-invalid");
  definirEstado("carregando", "Guardando o código e avisando a extensão…");
  chrome.storage.session.set({ meetWsToken: codigo }, function () {
    chrome.runtime.sendMessage({ tipo: "parear" }, function (resposta) {
      if (chrome.runtime.lastError) {
        definirEstado(
          "erro",
          "Service worker indisponível. Recarregue a extensão.",
          "em chrome://extensions, clique em Recarregar e abra esta página de novo."
        );
        return;
      }
      if (resposta && resposta.pronto) {
        definirEstado("sucesso", "Pareado e conectado. Pode fechar esta página.");
      } else {
        definirEstado("carregando", "Código guardado. Conectando ao Transkriptor…");
      }
    });
  });
}

function iniciar() {
  var botao = $("parear");
  if (botao) botao.addEventListener("click", aoParear);
  var campo = $("codigo");
  if (campo) {
    campo.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") aoParear();
    });
  }
}

if (typeof document !== "undefined") {
  iniciar();
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { validarCodigo, definirEstado, aoParear, iniciar, informar };
}
