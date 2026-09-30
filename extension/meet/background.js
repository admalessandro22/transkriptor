/**
 * Transkriptor Meet Bridge — service worker MV3 (T-13.D2).
 * Único dono do WebSocket local: content script nunca toca em token.
 *
 * Fluxo: content.js --(chrome.runtime)--> background.js --(WS)--> ponte local.
 * A credencial vem de chrome.storage.local (persiste entre reinícios do
 * Chrome, decisão do usuário 24/09/2026), gravada pela pairing.html
 * com o código de uso único exibido pelo app (Pareador).
 */
"use strict";

const PONTE_URL = "ws://127.0.0.1:5051";
const RECONECTAR_BASE_MS = 1000;
const RECONECTAR_MAX_MS = 30000;
const CHAVE_CREDENCIAL = "meetWsToken";
// T-15.A3: eventos esperam a sessão (início da reunião, reconexão) em vez de sumir.
const FILA_MAX = 200;
const FILA_IDADE_MS = 120000;
const CANAIS_ORIGEM = new Set(["captions_v2", "captions", "meet", "dom"]);
const PADRAO_IDIOMA = /^[a-z]{2,3}-[A-Z]{2}$/;

const inteiro = (v) => Number.isInteger(v) && v >= 0 && v < 1e9;

/** T-15.B4: saúde do canal — só contagens, motivos conhecidos, esqueleto e versão do Meet. */
function copiarSaude(evento, envelope) {
  const c = (evento.contadores && evento.contadores.captions_v2) || {};
  for (const campo of ["raw", "parsed", "rejected"]) if (inteiro(c[campo])) envelope[campo] = c[campo];
  for (const campo of ["recriacoes", "quedas"]) if (inteiro(evento[campo])) envelope[campo] = evento[campo];
  envelope.motivos = {};
  for (const [motivo, n] of Object.entries(evento.motivos || {})) {
    if (/^[a-z_]{1,32}$/.test(motivo) && inteiro(n)) envelope.motivos[motivo] = n;
  }
  if (typeof evento.esqueleto === "string" && evento.esqueleto.length <= 240 &&
      /^[0-9A-Z:(){} …a-z-]*$/.test(evento.esqueleto)) envelope.esqueleto = evento.esqueleto;
  if (typeof evento.build_meet === "string" && /^[\w.-]{1,80}$/.test(evento.build_meet)) envelope.build_meet = evento.build_meet;
  envelope.tactiq = evento.tactiq === true;
}

/** Copia só códigos BCP-47 válidos (FR-15.B1). */
function copiarIdiomas(evento, envelope, campos) {
  for (const campo of campos) {
    if (typeof evento[campo] === "string" && PADRAO_IDIOMA.test(evento[campo])) envelope[campo] = evento[campo];
  }
}

let ws = null;
let pronto = false;
let tentativas = 0;
let timerReconectar = null;
/** "nenhum" | "pendente" | "confirmado" | "recusado" — lido pela pairing.html. */
let pareamento = "nenhum";
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
    abas.set(tabId, { connectionId: novoId(), session: null, seq: 0, helloSent: false, meetingHint: null, fila: [] });
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

function montarHello(sender, agora = {}, active = false) {
  const estado = estadoAba(sender.tab.id);
  estado.meetingHint = hintDaSala(sender);
  return {
    tipo: "hello",
    connection_id: estado.connectionId,
    tab_id: String(sender.tab.id),
    meeting_hint: estado.meetingHint,
    active: active === true,
    client_wall_ms: agora.wallMs ?? Date.now(),
    client_monotonic_ms: agora.monotonicMs ?? performance.now(),
  };
}

function aceitarSessao(mensagem, dependencias = {}) {
  if (!mensagem || mensagem.tipo !== "sessao") return false;
  for (const [tabId, estado] of abas) {
    if (estado.connectionId !== mensagem.connection_id) continue;
    if (mensagem.tab_id !== String(tabId) || !mensagem.session_id || !mensagem.meeting_key) return false;
    if (estado.session && estado.session.session_id !== mensagem.session_id) estado.seq = 0;
    estado.session = { session_id: mensagem.session_id, meeting_key: mensagem.meeting_key };
    drenarFila(estado, dependencias.enviar || enviarPonte);
    return true;
  }
  return false;
}

/** Reenvia, em ordem, o que chegou antes da sessão; o que passou da idade cai. */
function drenarFila(estado, enviar) {
  const fila = estado.fila || [];
  estado.fila = [];
  const agora = Date.now();
  for (const item of fila) {
    if (agora - item.em > FILA_IDADE_MS) continue;
    const envelope = montarEnvelope(item.evento, item.remetente);
    if (!envelope) continue;
    envelope.queued = true;
    enviar(envelope);
  }
}

function enfileirar(estado, evento, remetente) {
  if (!evento || evento.tipo === "reuniao") return;
  estado.fila = estado.fila || [];
  estado.fila.push({ evento, remetente, em: Date.now() });
  if (estado.fila.length > FILA_MAX) estado.fila.splice(0, estado.fila.length - FILA_MAX);
}

/** Socket novo: a sessão precisa ser renegociada; os eventos voltam a esperar na fila. */
function reiniciarSessoes() {
  for (const estado of abas.values()) {
    estado.helloSent = false;
    estado.session = null;
  }
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
    atividade: "speaker_activity", capabilities: "capabilities", proprio: "self_device", saude: "health",
  }[evento.tipo];
  if (!kind) return null;
  if (kind === "self_device" && !/^dev-[A-Za-z0-9_-]+$/.test(evento.participant_id || "")) return null;
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
  if (kind === "capabilities") copiarIdiomas(evento, envelope, ["caption_lang", "lang_requested"]);
  if (kind === "self_device") envelope.participant_id = evento.participant_id;
  if (kind === "health") copiarSaude(evento, envelope);
  if (kind === "caption" || kind === "speaker_activity") {
    if (typeof evento.participant_id === "string") envelope.participant_id = evento.participant_id;
    if (typeof evento.nome === "string") envelope.display_name = evento.nome;
    if (typeof evento.confidence_source === "string") envelope.confidence_source = evento.confidence_source;
  }
  if (kind === "caption") {
    if (typeof evento.caption_id === "string") envelope.caption_id = evento.caption_id;
    if (Number.isInteger(evento.caption_revision)) envelope.caption_revision = evento.caption_revision;
    if (typeof evento.texto === "string") envelope.text = evento.texto;
    // FR-15.A1: o tempo da fala vem da página; client_wall_ms é só o do envio.
    const inicio = evento.caption_started_ms;
    const fim = evento.caption_last_ms;
    if (Number.isFinite(inicio) && Number.isFinite(fim) && fim >= inicio) {
      envelope.schema_version = 2;
      envelope.caption_started_ms = inicio;
      envelope.caption_last_ms = fim;
      if (CANAIS_ORIGEM.has(evento.origin_channel)) envelope.origin_channel = evento.origin_channel;
      copiarIdiomas(evento, envelope, ["caption_lang"]);
      if (evento.caption_final === true) envelope.caption_final = true;
      // FR-15.A2: amostra página↔parede do mesmo instante, para a ponte converter.
      if (Number.isFinite(evento.page_perf_ms) && Number.isFinite(evento.page_wall_ms)) {
        envelope.page_perf_ms = evento.page_perf_ms;
        envelope.page_wall_ms = evento.page_wall_ms;
      }
    }
  }
  return envelope;
}

/** FR-15.A2: a ponte mede ida-e-volta; o background só devolve o relógio de parede. */
function responderRelogio(msg, agoraWall) {
  if (!msg || msg.tipo !== "relogio_ping" || !Number.isInteger(msg.n)) return null;
  for (const estado of abas.values()) {
    if (estado.connectionId === msg.connection_id) {
      return { tipo: "relogio_pong", n: msg.n, connection_id: msg.connection_id, client_wall_ms: agoraWall };
    }
  }
  return null;
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

function registrarPareamento(estado) {
  pareamento = estado;
}

function estadoPareamento() {
  return pareamento;
}

/** 1008 = o app recusou a credencial (código expirado, usado ou errado). */
function tratarFechamento(evento) {
  if (evento && evento.code === 1008 && pareamento !== "confirmado") {
    pareamento = "recusado";
    // Credencial vencida ou de outro ID: tenta o pareamento nativo mais uma vez.
    if (!nativoTentado) {
      nativoTentado = true;
      parearNativo();
    }
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

/** Novo código de pareamento: descarta o socket da credencial antiga. */
function reconectarComNovaCredencial() {
  if (timerReconectar !== null) {
    clearTimeout(timerReconectar);
    timerReconectar = null;
  }
  if (ws) {
    const antigo = ws;
    ws = null;
    pronto = false;
    antigo.onclose = null;
    try {
      antigo.close();
    } catch (_e) {}
  }
  conectar();
}

// T-15.E2: sem credencial, pede um código de uso único ao app pelo host nativo.
const HOST_NATIVO = "com.transkriptor.ponte";
let nativoTentado = false;

function parearNativo(dependencias = {}) {
  const enviarNativo = dependencias.enviarNativo ||
    ((msg, cb) => chrome.runtime.sendNativeMessage(HOST_NATIVO, msg, cb));
  const salvar = dependencias.salvar || ((valor, cb) => chrome.storage.local.set(valor, cb));
  const conectarDepois = dependencias.conectar || reconectarComNovaCredencial;
  return new Promise((resolver) => {
    try {
      enviarNativo({ cmd: "obter_codigo_pareamento", v: 1 }, (resposta) => {
        const erro = typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.lastError;
        const codigo = resposta && resposta.ok === true ? resposta.codigo : null;
        if (erro || typeof codigo !== "string" || !/^pair-[A-Za-z0-9_-]+$/.test(codigo)) {
          resolver(false);
          return;
        }
        salvar({ [CHAVE_CREDENCIAL]: codigo }, () => {
          registrarPareamento("pendente");
          conectarDepois();
          resolver(true);
        });
      });
    } catch (_e) {
      resolver(false); // host não instalado: o pareamento manual continua valendo
    }
  });
}

function conectar() {
  if (typeof chrome === "undefined" || !chrome.storage) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  chrome.storage.local.get(CHAVE_CREDENCIAL, function (dados) {
    const credencial = dados && dados[CHAVE_CREDENCIAL];
    if (!credencial) {
      pronto = false;
      if (!nativoTentado) {
        nativoTentado = true;
        parearNativo();
      }
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
      reiniciarSessoes();
    };
    ws.onclose = function (evento) {
      tratarFechamento(evento);
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
          chrome.storage.local.set({ [CHAVE_CREDENCIAL]: msg.token });
          registrarPareamento("confirmado");
        }
        if (msg && msg.tipo === "sessao") aceitarSessao(msg);
        const pong = responderRelogio(msg, Date.now());
        if (pong) enviarPonte(pong);
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
    registrarPareamento("pendente");
    (dependencias.conectar || reconectarComNovaCredencial)();
    if (typeof responder === "function") responder({ pronto, pareamento });
    return true;
  }
  if (mensagem.tipo === "estadoPareamento") {
    const runtimeId = dependencias.runtimeId || (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.id);
    if (!validarSenderPareamento(remetente, runtimeId)) return false;
    if (typeof responder === "function") responder({ pronto, pareamento });
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
      enfileirar(estado, mensagem.evento, remetente);
      if (!estado.helloSent || (mensagem.evento && mensagem.evento.tipo === "reuniao")) {
        estado.helloSent = enviar(montarHello(remetente, {}, mensagem.evento && mensagem.evento.ativa)) !== false;
      }
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
    responderRelogio,
    reiniciarSessoes,
    parearNativo,
    FILA_MAX,
    FILA_IDADE_MS,
    registrarPareamento,
    estadoPareamento,
    tratarFechamento,
    PONTE_URL,
    RECONECTAR_BASE_MS,
    RECONECTAR_MAX_MS,
  };
}
