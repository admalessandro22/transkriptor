/**
 * Transkriptor Meet Bridge — lê falante ativo e legendas (FR-8.1 / FR-8.7).
 * Envia eventos para ws://127.0.0.1:5051
 */
(function () {
  const WS_URL =
    "ws://127.0.0.1:5051?token=" + encodeURIComponent(typeof MEET_WS_TOKEN !== "undefined" ? MEET_WS_TOKEN : "");
  const DEBOUNCE_MS = 400;

  let ws = null;
  let ultimoNome = "";
  let ultimoEnvio = 0;
  let timerReconectar = null;

  function conectar() {
    try {
      ws = new WebSocket(WS_URL);
      ws.onclose = function () {
        timerReconectar = setTimeout(conectar, 3000);
      };
      ws.onerror = function () {
        try {
          ws.close();
        } catch (_e) {}
      };
    } catch (_e) {
      timerReconectar = setTimeout(conectar, 3000);
    }
  }

  function enviar(nome, tipo) {
    if (!nome || !ws || ws.readyState !== WebSocket.OPEN) return;
    const agora = Date.now();
    if (nome === ultimoNome && agora - ultimoEnvio < DEBOUNCE_MS) return;
    ultimoNome = nome;
    ultimoEnvio = agora;
    ws.send(
      JSON.stringify({
        nome: nome.trim(),
        ts_ms: agora,
        tipo: tipo || "ativo",
      })
    );
  }

  function textoLimpo(el) {
    return (el && el.textContent ? el.textContent : "").replace(/\s+/g, " ").trim();
  }

  function nomeDaLegenda() {
    const seletores = [
      "[data-self-name]",
      ".NWpY1d",
      ".zs7s8d",
      "[jsname='V67aGc']",
      ".KV1GEc",
    ];
    for (const sel of seletores) {
      const nodes = document.querySelectorAll(sel);
      for (const node of nodes) {
        const nome =
          node.getAttribute("data-self-name") || textoLimpo(node);
        if (nome && nome.length > 1 && nome.length < 80) {
          return nome;
        }
      }
    }
    return "";
  }

  function nomeDoTileAtivo() {
    const ativos = document.querySelectorAll(
      '[data-self-name][data-is-muted], [data-requested-participant-id][data-self-name]'
    );
    for (const tile of ativos) {
      const nome = tile.getAttribute("data-self-name");
      if (!nome) continue;
      const estilo = window.getComputedStyle(tile.closest("[data-participant-id]") || tile);
      if (estilo && parseFloat(estilo.opacity || "1") > 0.5) {
        return nome;
      }
    }
    const falando = document.querySelector("[data-self-name].kssMZb, [data-self-name].gjg47c");
    if (falando) {
      return falando.getAttribute("data-self-name") || textoLimpo(falando);
    }
    return "";
  }

  function detectar() {
    const legenda = nomeDaLegenda();
    if (legenda) {
      enviar(legenda, "lista");
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
  }

  conectar();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarObserver);
  } else {
    iniciarObserver();
  }
})();