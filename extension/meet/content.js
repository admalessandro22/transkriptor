/**
 * Transkriptor Meet Bridge — falante ativo e legendas com nome+texto (FR-5.1).
 * Envia eventos para ws://127.0.0.1:5051
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
  const WS_URL =
    "ws://127.0.0.1:5051?token=" +
    encodeURIComponent(typeof MEET_WS_TOKEN !== "undefined" ? MEET_WS_TOKEN : "");
  const DEBOUNCE_MS = 400;
  const MAX_TEXTO = 500;

  const HEARTBEAT_MS = 5000;

  let ws = null;
  let ultimoNome = "";
  let ultimoTexto = "";
  let ultimoEnvio = 0;
  let timerReconectar = null;

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
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    try {
      ws.send(JSON.stringify({ tipo: "reuniao", ativa: emChamada(), ts_ms: Date.now(), titulo: (document.title || "").slice(0, 120) }));
    } catch (_e) {}
  }

  function conectar() {
    try {
      ws = new WebSocket(WS_URL);
      ws.onopen = function () {
        enviarEstado();
      };
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

  function textoLimpo(el) {
    return (el && el.textContent ? el.textContent : "").replace(/\s+/g, " ").trim();
  }

  function enviar(nome, tipo, texto) {
    if (!nome || !ws || ws.readyState !== WebSocket.OPEN) return;
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
    ws.send(JSON.stringify(payload));
  }

  /**
   * Extrai pares (nome, texto) das legendas do Meet em camadas (FR-5.1).
   * @returns {{nome: string, texto: string}[]}
   */
  function extrairLegendas() {
    const pares = [];

    // Camada 1: região de legendas + data-caption-block
    const blocos = document.querySelectorAll(
      '[role="region"] [data-caption-block], [data-caption-block]'
    );
    if (blocos.length) {
      blocos.forEach(function (bloco) {
        const nomeEl =
          bloco.querySelector("[data-speaker-name]") ||
          bloco.querySelector("[data-self-name]");
        const textoEl = bloco.querySelector("[data-caption-text]");
        const nome = nomeEl
          ? nomeEl.getAttribute("data-speaker-name") ||
            nomeEl.getAttribute("data-self-name") ||
            textoLimpo(nomeEl)
          : "";
        const texto = textoEl ? textoLimpo(textoEl) : "";
        if (nome && texto && nome.length < 80) {
          pares.push({ nome: nome.trim(), texto: texto.slice(0, MAX_TEXTO) });
        }
      });
      if (pares.length) return pares;
    }

    // Camada 2: data-* em contêiner de legendas (região ARIA)
    const regioes = document.querySelectorAll(
      '[role="region"][aria-label*="egenda" i], [role="region"][aria-label*="caption" i]'
    );
    regioes.forEach(function (regiao) {
      const nomes = regiao.querySelectorAll(
        "[data-speaker-name], [data-self-name]"
      );
      nomes.forEach(function (node) {
        const nome =
          node.getAttribute("data-speaker-name") ||
          node.getAttribute("data-self-name") ||
          textoLimpo(node);
        let texto = "";
        let sib = node.nextElementSibling;
        if (sib) texto = textoLimpo(sib);
        if (!texto && node.parentElement) {
          const filhos = node.parentElement.children;
          for (let i = 0; i < filhos.length; i++) {
            if (filhos[i] === node) continue;
            const t = textoLimpo(filhos[i]);
            if (t && t !== nome) {
              texto = t;
              break;
            }
          }
        }
        if (nome && texto && nome.length > 1 && nome.length < 80) {
          pares.push({ nome: nome.trim(), texto: texto.slice(0, MAX_TEXTO) });
        }
      });
    });
    if (pares.length) return pares;

    // Camada 3: classes ofuscadas atuais do Meet (último recurso)
    const containers = document.querySelectorAll(".nMcdL, .a4cQT .nMcdL, .iOzk7 .nMcdL");
    const alvos = containers.length
      ? containers
      : document.querySelectorAll(".NWpY1d, .zs7s8d");
    if (containers.length) {
      containers.forEach(function (c) {
        const nomeEl = c.querySelector(".NWpY1d, .zs7s8d, [jsname='V67aGc']");
        const textoEl = c.querySelector(".ygicle, .VbkSUe, .iTTPOb");
        const nome = nomeEl ? textoLimpo(nomeEl) : "";
        const texto = textoEl ? textoLimpo(textoEl) : "";
        if (nome && texto && nome.length > 1 && nome.length < 80) {
          pares.push({ nome: nome.trim(), texto: texto.slice(0, MAX_TEXTO) });
        }
      });
    } else {
      // fallback: pares sequenciais nome/texto no DOM
      const nomes = document.querySelectorAll(".NWpY1d, .zs7s8d, [jsname='V67aGc']");
      nomes.forEach(function (nomeEl) {
        const nome = textoLimpo(nomeEl);
        let texto = "";
        const parent = nomeEl.parentElement;
        if (parent) {
          const textoEl = parent.querySelector(".ygicle, .VbkSUe, .iTTPOb");
          if (textoEl) texto = textoLimpo(textoEl);
        }
        if (nome && texto && nome.length > 1 && nome.length < 80) {
          pares.push({ nome: nome.trim(), texto: texto.slice(0, MAX_TEXTO) });
        }
      });
    }
    return pares;
  }

  function nomeDoTileAtivo() {
    const ativos = document.querySelectorAll(
      "[data-self-name][data-is-muted], [data-requested-participant-id][data-self-name]"
    );
    for (const tile of ativos) {
      const nome = tile.getAttribute("data-self-name");
      if (!nome) continue;
      const estilo = window.getComputedStyle(
        tile.closest("[data-participant-id]") || tile
      );
      if (estilo && parseFloat(estilo.opacity || "1") > 0.5) {
        return nome;
      }
    }
    const falando = document.querySelector(
      "[data-self-name].kssMZb, [data-self-name].gjg47c"
    );
    if (falando) {
      return falando.getAttribute("data-self-name") || textoLimpo(falando);
    }
    return "";
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
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ tipo: "reuniao", ativa: false, ts_ms: Date.now() }));
      } catch (_e) {}
    }
  });

  conectar();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarObserver);
  } else {
    iniciarObserver();
  }
})();
