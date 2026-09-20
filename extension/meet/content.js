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
 * Espelho Python dos fixtures: tests/test_extensao_parsing.py → extrair_legendas_html
 * (sem runner JS no projeto).
 */
(function () {
  const DEBOUNCE_MS = 400;
  const MAX_TEXTO = 500;

  const HEARTBEAT_MS = 5000;

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
      canalEnviar({ tipo: "reuniao", ativa: emChamada(), ts_ms: Date.now(), titulo: (document.title || "").slice(0, 120) });
    } catch (_e) {}
  }

  function enviar(nome, tipo, texto) {
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
      return { nome: f.nome, texto: f.texto };
    });
  }

  function nomeDoTileAtivo() {
    const lib = biblioteca();
    if (!lib) return "";
    const sinais = lib.extrairAtividade(document);
    return sinais.length ? sinais[0].nome : "";
  }

  function detectar() {
    const legendas = extrairLegendas();
    if (legendas.length) {
      // envia a legenda mais recente (última do DOM)
      const ult = legendas[legendas.length - 1];
      enviar(ult.nome, "legenda", ult.texto);
      return;
    }
    const ativo = nomeDoTileAtivo();
    if (ativo) {
      enviar(ativo, "ativo");
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
    setInterval(enviarEstado, HEARTBEAT_MS);
  }

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
