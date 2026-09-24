/**
 * Transkriptor Meet Bridge — falante ativo e legendas com nome+texto (FR-5.1).
 * Transporte T-13.D2: content script extrai e entrega ao service worker via
 * chrome.runtime; SÓ o background.js abre o WebSocket local. Nenhum segredo
 * neste arquivo (a credencial vive em chrome.storage.session, via pairing).
 *
 * Camadas de extração de legendas (extrairLegendas):
 *   1. região ARIA + data-caption-block / data-speaker-name / data-caption-text
 *   2. atributos data-* (data-self-name, data-speaker-name)
 *   3. classes ofuscadas do Meet (.NWpY1d, .zs7s8d, .ygicle) — último recurso
 *
 * O parser versionado fornece IDs e revisões preservados no transporte.
 *
 * Fonte principal (rtc.js, mundo da página): legendas do canal "captions_v2"
 * e nomes do canal "collections" — funcionam com o CC desligado na tela. O DOM
 * de legendas acima fica como reserva quando o canal não entrega nada.
 */
(function () {
  const DEBOUNCE_MS = 400;
  const MAX_TEXTO = 500;

  const HEARTBEAT_MS = 5000;
  const EVENTO_RTC = "transkriptor-meet-rtc";
  const RTC_FLUSH_MS = 1000;
  const RTC_VIVO_MS = 10000;
  const RTC_EXPIRA_MS = 60000;
  const MAX_NOMES = 500;

  /** dispositivo ("dev-127") -> nome exibido no Meet. */
  const nomesRtc = new Map();
  /** "utterance/dispositivo" -> última revisão ainda não entregue. */
  const falasRtc = new Map();
  let ultimaLegendaRtc = 0;

  let ultimoNome = "";
  let ultimoTexto = "";
  let ultimoEnvio = 0;

  /** Entrega ao service worker; ele detém o WebSocket e a credencial. */
  function canalEnviar(payload) {
    try {
      chrome.runtime.sendMessage({ tipo: "meet-evento", evento: payload });
    } catch (_e) {}
  }

  /**
   * Estamos dentro de uma chamada (e não na tela inicial / sala de espera)?
   * Sinais, em ordem de confiança: URL com código de sala + presença dos
   * controles da chamada (botão de sair / microfone).
   */
  function emChamada() {
    if (!/^\/[a-z]{3,4}-[a-z]{3,4}-[a-z]{3,4}/i.test(location.pathname)) return false;
    const seletores = [
      '[aria-label*="Sair da chamada" i]',
      '[aria-label*="Leave call" i]',
      '[data-tooltip*="Sair da chamada" i]',
      '[data-tooltip*="Leave call" i]',
      '[aria-label*="Desativar microfone" i]',
      '[aria-label*="Turn off microphone" i]',
      '[data-is-muted]',
    ];
    return seletores.some(function (s) {
      return document.querySelector(s) !== null;
    });
  }

  /** FR-9.3: heartbeat de estado — a fonte mais confiável de detecção. */
  function enviarEstado() {
    try {
      canalEnviar({ tipo: "reuniao", ativa: emChamada(), ts_ms: Date.now() });
    } catch (_e) {}
  }

  function enviar(nome, tipo, texto, metadados) {
    if (!nome) return;
    const agora = Date.now();
    const txt = (texto || "").trim().slice(0, MAX_TEXTO);
    if (
      nome === ultimoNome &&
      txt === ultimoTexto &&
      agora - ultimoEnvio < DEBOUNCE_MS
    ) {
      return;
    }
    ultimoNome = nome;
    ultimoTexto = txt;
    ultimoEnvio = agora;
    const payload = {
      nome: nome.trim(),
      ts_ms: agora,
      tipo: tipo || "ativo",
    };
    if (txt) {
      payload.texto = txt;
    }
    if (metadados) {
      if (metadados.id) payload.caption_id = metadados.id;
      if (Number.isInteger(metadados.revisao)) payload.caption_revision = metadados.revisao;
      if (metadados.participant_id) payload.participant_id = metadados.participant_id;
      payload.confidence_source = tipo === "legenda" ? "caption" : "speaker_activity";
    }
    canalEnviar(payload);
  }

  function biblioteca() {
    return typeof MeetParser !== "undefined" ? MeetParser : null;
  }

  /**
   * Legendas via parser versionado (parser.js, T-13.D3): última revisão
   * consolidada. Fallback vazio se a biblioteca ainda não carregou.
   * @returns {{nome: string, texto: string}[]}
   */
  function extrairLegendas() {
    const lib = biblioteca();
    if (!lib) return [];
    return lib.consolidarRevisoes(lib.extrairLegendas(document)).map(function (f) {
      return { nome: f.nome, texto: f.texto, id: f.id, revisao: f.revisao, participant_id: f.participant_id };
    });
  }

  function tileAtivo() {
    const lib = biblioteca();
    if (!lib) return null;
    const sinais = lib.extrairAtividade(document);
    return sinais.length ? sinais[0] : null;
  }

  /** Nome pelo tile do participante: data-participant-id termina em /devices/N. */
  function nomeNoTile(dispositivo) {
    const n = dispositivo.slice(4);
    if (!/^[A-Za-z0-9_-]+$/.test(n)) return "";
    const tile = document.querySelector('[data-participant-id$="/devices/' + n + '"]');
    const el = tile && tile.querySelector("span.notranslate");
    const nome = el ? (el.textContent || "").replace(/\s+/g, " ").trim() : "";
    return nome.length > 1 && nome.length < 80 ? nome : "";
  }

  function nomeDoDispositivo(dispositivo) {
    return nomesRtc.get(dispositivo) || nomeNoTile(dispositivo);
  }

  function receberRtc(ev) {
    let msg;
    try {
      msg = JSON.parse(ev.detail);
    } catch (_e) {
      return;
    }
    if (!msg || typeof msg !== "object") return;
    if (msg.tipo === "nomes" && Array.isArray(msg.pares)) {
      msg.pares.forEach(function (par) {
        if (!par || typeof par.dispositivo !== "string" || typeof par.nome !== "string") return;
        if (nomesRtc.size >= MAX_NOMES && !nomesRtc.has(par.dispositivo)) return;
        nomesRtc.set(par.dispositivo, par.nome);
      });
      return;
    }
    if (msg.tipo === "legenda" && typeof msg.dispositivo === "string" && typeof msg.texto === "string") {
      if (!Number.isInteger(msg.utterance) || !Number.isInteger(msg.versao)) return;
      ultimaLegendaRtc = Date.now();
      const id = msg.utterance + "/" + msg.dispositivo;
      const atual = falasRtc.get(id);
      if (atual && atual.versao > msg.versao) return;
      falasRtc.set(id, {
        dispositivo: msg.dispositivo,
        versao: msg.versao,
        texto: msg.texto,
        visto: Date.now(),
        pendente: true,
      });
    }
  }

  /** Entrega a revisão mais recente de cada fala; espera o nome se ainda não veio. */
  function descarregarRtc() {
    const agora = Date.now();
    falasRtc.forEach(function (fala, id) {
      if (agora - fala.visto > RTC_EXPIRA_MS) {
        falasRtc.delete(id);
        return;
      }
      if (!fala.pendente || !fala.texto) return;
      const nome = nomeDoDispositivo(fala.dispositivo);
      if (!nome) return;
      fala.pendente = false;
      enviar(nome, "legenda", fala.texto, {
        id: "rtc-" + id,
        revisao: fala.versao,
        participant_id: fala.dispositivo,
      });
    });
  }

  function detectar() {
    // Canal de legendas vivo: ele é a fonte; o DOM só duplicaria as falas.
    if (Date.now() - ultimaLegendaRtc < RTC_VIVO_MS) return;
    const legendas = extrairLegendas();
    if (legendas.length) {
      // envia a legenda mais recente (última do DOM)
      const ult = legendas[legendas.length - 1];
      enviar(ult.nome, "legenda", ult.texto, ult);
      return;
    }
    const ativo = tileAtivo();
    if (ativo) {
      enviar(ativo.nome, "ativo", "", { participant_id: ativo.id });
    }
  }

  function iniciarObserver() {
    const observer = new MutationObserver(function () {
      detectar();
    });
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    setInterval(detectar, 1500);
    setInterval(descarregarRtc, RTC_FLUSH_MS);
    setInterval(enviarEstado, HEARTBEAT_MS);
  }

  document.addEventListener(EVENTO_RTC, receberRtc);

  window.addEventListener("beforeunload", function () {
    try {
      canalEnviar({ tipo: "reuniao", ativa: false, ts_ms: Date.now() });
    } catch (_e) {}
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarObserver);
  } else {
    iniciarObserver();
  }
})();
