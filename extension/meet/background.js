/**
 * Transkriptor Meet Bridge — service worker MV3 (T-13.D2).
 * Único dono do WebSocket local: content script nunca toca em token.
 *
 * Fluxo: content.js --(chrome.runtime)--> background.js --(WS)--> ponte local.
 * A credencial vem de chrome.storage.session, gravada pela pairing.html
 * com o código de uso único exibido pelo app (Pareador).
 */
"use strict";

const PONTE_URL = "ws://127.0.0.1:5051";
const RECONECTAR_BASE_MS = 1000;
const RECONECTAR_MAX_MS = 30000;
const CHAVE_CREDENCIAL = "meetWsToken";

let ws = null;
let pronto = false;
let tentativas = 0;
let timerReconectar = null;

function validarSender(sender) {
  if (!sender || sender.frameId !== 0) return false;
  const tab = sender.tab;
  if (!tab || typeof tab.id !== "number") return false;
  const url = sender.url || tab.url || "";
  return typeof url === "string" && url.indexOf("https://meet.google.com/") === 0;
}

function atrasoReconexao(tentativa, aleatorio) {
  const sorteio = typeof aleatorio === "function" ? aleatorio : Math.random;
  const base = Math.min(RECONECTAR_MAX_MS, RECONECTAR_BASE_MS * 2 ** tentativa);
  const jitter = base * 0.25 * (sorteio() * 2 - 1);
  return Math.max(0, Math.round(base + jitter));
}

function montarEnvelope(evento, remetente) {
  const copia = Object.assign({}, evento);
  copia.tabId = remetente && remetente.tab ? remetente.tab.id : null;
  return copia;
}

function agendarReconexao() {
  if (typeof chrome === "undefined" || !chrome.storage) return;
  if (timerReconectar !== null) return;
  const espera = atrasoReconexao(tentativas);
  tentativas += 1;
  timerReconectar = setTimeout(function () {
    timerReconectar = null;
    conectar();
  }, espera);
}

function conectar() {
  if (typeof chrome === "undefined" || !chrome.storage) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  chrome.storage.session.get(CHAVE_CREDENCIAL, function (dados) {
    const credencial = dados && dados[CHAVE_CREDENCIAL];
    if (!credencial) {
      pronto = false;
      return;
    }
    try {
      ws = new WebSocket(PONTE_URL + "?token=" + encodeURIComponent(credencial));
    } catch (_e) {
      agendarReconexao();
      return;
    }
    ws.onopen = function () {
      pronto = true;
      tentativas = 0;
    };
    ws.onclose = function () {
      pronto = false;
      ws = null;
      agendarReconexao();
    };
    ws.onerror = function () {
      try {
        ws.close();
      } catch (_e) {}
    };
    ws.onmessage = function (evento) {
      try {
        const msg = JSON.parse(evento.data);
        if (msg && msg.tipo === "pareado" && msg.token && chrome.storage) {
          chrome.storage.session.set({ [CHAVE_CREDENCIAL]: msg.token });
        }
      } catch (_e) {}
    };
  });
}

function aoReceberMensagem(mensagem, remetente, responder) {
  if (!validarSender(remetente)) return false;
  if (!mensagem || typeof mensagem !== "object") return false;
  if (mensagem.tipo === "parear") {
    tentativas = 0;
    conectar();
    if (typeof responder === "function") responder({ pronto });
    return true;
  }
  if (mensagem.tipo === "estadoPonte") {
    if (typeof responder === "function") responder({ pronto });
    return true;
  }
  if (mensagem.tipo === "meet-evento") {
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(montarEnvelope(mensagem.evento, remetente)));
      } catch (_e) {}
    }
    return false;
  }
  return false;
}

if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
  chrome.runtime.onMessage.addListener(aoReceberMensagem);
  conectar();
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    validarSender,
    atrasoReconexao,
    montarEnvelope,
    PONTE_URL,
    RECONECTAR_BASE_MS,
    RECONECTAR_MAX_MS,
  };
}
