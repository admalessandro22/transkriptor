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
const abas = new Map();

function novoId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function estadoAba(tabId) {
  if (!abas.has(tabId)) {
    abas.set(tabId, { connectionId: novoId(), session: null, seq: 0, helloSent: false, meetingHint: null });
  }
  return abas.get(tabId);
}

function hintDaSala(sender) {
  try {
    const url = new URL(sender.url || sender.tab.url || "");
    const codigo = url.pathname.slice(1).toLowerCase();
    return /^[a-z]{3,4}-[a-z]{3,4}-[a-z]{3,4}$/.test(codigo) ? codigo : null;
  } catch (_e) {
    return null;
  }
}

function montarHello(sender, agora = {}) {
  const estado = estadoAba(sender.tab.id);
  estado.meetingHint = hintDaSala(sender);
  return {
    tipo: "hello",
    connection_id: estado.connectionId,
    tab_id: String(sender.tab.id),
    meeting_hint: estado.meetingHint,
    client_wall_ms: agora.wallMs ?? Date.now(),
    client_monotonic_ms: agora.monotonicMs ?? performance.now(),
  };
}

function aceitarSessao(mensagem) {
  if (!mensagem || mensagem.tipo !== "sessao") return false;
  for (const [tabId, estado] of abas) {
    if (estado.connectionId !== mensagem.connection_id) continue;
    if (mensagem.tab_id !== String(tabId) || !mensagem.session_id || !mensagem.meeting_key) return false;
    if (estado.session && estado.session.session_id !== mensagem.session_id) estado.seq = 0;
    estado.session = { session_id: mensagem.session_id, meeting_key: mensagem.meeting_key };
    return true;
  }
  return false;
}

function validarSenderPareamento(sender, runtimeId) {
  if (!sender || !runtimeId || sender.id !== runtimeId || sender.frameId !== 0) return false;
  try {
    const url = new URL(sender.url || "");
    return url.protocol === "chrome-extension:" &&
      url.hostname === runtimeId && url.pathname === "/pairing.html";
  } catch (_e) {
    return false;
  }
}

function validarSenderMeet(sender) {
  if (!sender || sender.frameId !== 0) return false;
  const tab = sender.tab;
  if (!tab || typeof tab.id !== "number") return false;
  const url = sender.url || tab.url || "";
  return typeof url === "string" && /^https:\/\/meet\.google\.com\//.test(url);
}

const validarSender = validarSenderMeet;

function atrasoReconexao(tentativa, aleatorio) {
  const sorteio = typeof aleatorio === "function" ? aleatorio : Math.random;
  const base = Math.min(RECONECTAR_MAX_MS, RECONECTAR_BASE_MS * 2 ** tentativa);
  const jitter = base * 0.25 * (sorteio() * 2 - 1);
  return Math.max(0, Math.round(base + jitter));
}

function montarEnvelope(evento, remetente, agora = {}) {
  if (!evento || !remetente || !remetente.tab) return null;
  const estado = estadoAba(remetente.tab.id);
  if (!estado.session) return null;
  const kind = {
    reuniao: "heartbeat", legenda: "caption", ativo: "speaker_activity",
    atividade: "speaker_activity", capabilities: "capabilities",
  }[evento.tipo];
  if (!kind) return null;
  const envelope = {
    schema_version: 1,
    event_id: novoId(),
    session_id: estado.session.session_id,
    connection_id: estado.connectionId,
    seq: estado.seq++,
    tab_id: String(remetente.tab.id),
    meeting_key: estado.session.meeting_key,
    kind,
    client_wall_ms: agora.wallMs ?? Date.now(),
    client_monotonic_ms: agora.monotonicMs ?? performance.now(),
  };
  if (kind === "heartbeat") envelope.active = evento.ativa === true;
  if (kind === "caption" || kind === "speaker_activity") {
    if (typeof evento.participant_id === "string") envelope.participant_id = evento.participant_id;
    if (typeof evento.nome === "string") envelope.display_name = evento.nome;
    if (typeof evento.confidence_source === "string") envelope.confidence_source = evento.confidence_source;
  }
  if (kind === "caption") {
    if (typeof evento.caption_id === "string") envelope.caption_id = evento.caption_id;
    if (Number.isInteger(evento.caption_revision)) envelope.caption_revision = evento.caption_revision;
    if (typeof evento.texto === "string") envelope.text = evento.texto;
  }
  return envelope;
}

function enviarPonte(mensagem) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return false;
  try {
    ws.send(JSON.stringify(mensagem));
    return true;
  } catch (_e) {
    return false;
  }
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
      for (const estado of abas.values()) {
        estado.helloSent = false;
        estado.session = null;
      }
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
        if (msg && msg.tipo === "sessao") aceitarSessao(msg);
      } catch (_e) {}
    };
  });
}

function aoReceberMensagem(mensagem, remetente, responder, dependencias = {}) {
  if (!mensagem || typeof mensagem !== "object") return false;
  if (mensagem.tipo === "parear") {
    const runtimeId = dependencias.runtimeId || (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.id);
    if (!validarSenderPareamento(remetente, runtimeId)) return false;
    tentativas = 0;
    (dependencias.conectar || conectar)();
    if (typeof responder === "function") responder({ pronto });
    return true;
  }
  if (!validarSenderMeet(remetente)) return false;
  if (mensagem.tipo === "estadoPonte") {
    if (typeof responder === "function") responder({ pronto });
    return true;
  }
  if (mensagem.tipo === "meet-evento") {
    let estado = estadoAba(remetente.tab.id);
    const hint = hintDaSala(remetente);
    if (estado.meetingHint !== null && estado.meetingHint !== hint) {
      abas.delete(remetente.tab.id);
      estado = estadoAba(remetente.tab.id);
    }
    const enviar = dependencias.enviar || enviarPonte;
    if (!estado.session) {
      if (!estado.helloSent) estado.helloSent = enviar(montarHello(remetente)) !== false;
      if (!estado.helloSent) (dependencias.conectar || conectar)();
      return false;
    }
    const envelope = montarEnvelope(mensagem.evento, remetente);
    if (envelope) enviar(envelope);
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
    validarSenderMeet,
    validarSenderPareamento,
    aoReceberMensagem,
    estadoAba,
    montarHello,
    aceitarSessao,
    atrasoReconexao,
    montarEnvelope,
    PONTE_URL,
    RECONECTAR_BASE_MS,
    RECONECTAR_MAX_MS,
  };
}
