/**
 * Parser versionado de roster e legendas do Meet (T-13.D3).
 * Separado do transporte (background.js) e da coleta (content.js).
 *
 * Regras: tile visível não prova fala (vai para roster/atividade, nunca
 * para fala); homônimos nunca se fundem (ids locais distintos, efêmeros);
 * legenda tem id/revisão (revisão maior vence; repetição colapsa);
 * opacidade não é consultada; sem seletores, capacidade indisponível.
 * Nomes sintéticos nas fixtures; nenhum dado real.
 */
"use strict";

const MAX_TEXTO = 500;
const MAX_NOME = 80;

function escopo(raiz) {
  if (raiz && typeof raiz.querySelectorAll === "function") return raiz;
  if (typeof document !== "undefined") return document;
  return null;
}

function textoLimpo(el) {
  return (el && el.textContent ? el.textContent : "").replace(/\s+/g, " ").trim();
}

function revisaoDe(bloco) {
  const cru = bloco && bloco.getAttribute ? bloco.getAttribute("data-caption-revision") : null;
  const n = parseInt(cru, 10);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

function idLocal(prefixo, indice) {
  return "local-" + prefixo + "-" + indice;
}

function montarFala(bloco, nome, texto, indice) {
  const idAttr = bloco.getAttribute && (bloco.getAttribute("data-caption-id") || bloco.getAttribute("data-caption-block-id"));
  return {
    id: idAttr || idLocal("cap", indice),
    nome: nome.trim(),
    texto: texto.slice(0, MAX_TEXTO),
    revisao: revisaoDe(bloco),
    efemero: !idAttr,
  };
}

function camadaAtributos(raiz) {
  const pares = [];
  const blocos = raiz.querySelectorAll('[role="region"] [data-caption-block], [data-caption-block]');
  blocos.forEach(function (bloco, i) {
    const nomeEl = bloco.querySelector("[data-speaker-name]") || bloco.querySelector("[data-self-name]");
    const textoEl = bloco.querySelector("[data-caption-text]");
    const nome = nomeEl
      ? nomeEl.getAttribute("data-speaker-name") || nomeEl.getAttribute("data-self-name") || textoLimpo(nomeEl)
      : "";
    const texto = textoEl ? textoLimpo(textoEl) : "";
    if (nome && texto && nome.length < MAX_NOME) {
      pares.push(montarFala(bloco, nome, texto, i));
    }
  });
  return pares;
}

function camadaRegiao(raiz) {
  const pares = [];
  let n = 0;
  const regioes = raiz.querySelectorAll('[role="region"][aria-label*="egenda" i], [role="region"][aria-label*="caption" i]');
  regioes.forEach(function (regiao) {
    const nomes = regiao.querySelectorAll("[data-speaker-name], [data-self-name]");
    nomes.forEach(function (node) {
      const nome = node.getAttribute("data-speaker-name") || node.getAttribute("data-self-name") || textoLimpo(node);
      let texto = "";
      const sib = node.nextElementSibling;
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
      if (nome && texto && nome.length > 1 && nome.length < MAX_NOME) {
        pares.push({ id: idLocal("cap", n), nome: nome.trim(), texto: texto.slice(0, MAX_TEXTO), revisao: revisaoDe(node), efemero: true });
        n += 1;
      }
    });
  });
  return pares;
}

function camadaClasses(raiz) {
  const pares = [];
  const containers = raiz.querySelectorAll(".nMcdL, .a4cQT .nMcdL, .iOzk7 .nMcdL");
  const alvos = containers.length ? containers : raiz.querySelectorAll(".NWpY1d, .zs7s8d");
  function coletar(nomeEl, textoEl, i) {
    const nome = nomeEl ? textoLimpo(nomeEl) : "";
    const texto = textoEl ? textoLimpo(textoEl) : "";
    if (nome && texto && nome.length > 1 && nome.length < MAX_NOME) {
      pares.push({ id: idLocal("cap", i), nome: nome.trim(), texto: texto.slice(0, MAX_TEXTO), revisao: 0, efemero: true });
    }
  }
  if (containers.length) {
    containers.forEach(function (c, i) {
      coletar(c.querySelector(".NWpY1d, .zs7s8d, [jsname='V67aGc']"), c.querySelector(".ygicle, .VbkSUe, .iTTPOb"), i);
    });
  } else {
    alvos.forEach(function (nomeEl, i) {
      const parent = nomeEl.parentElement;
      coletar(nomeEl, parent ? parent.querySelector(".ygicle, .VbkSUe, .iTTPOb") : null, i);
    });
  }
  return pares;
}

function extrairLegendas(raiz) {
  const ctx = escopo(raiz);
  if (!ctx) return [];
  const camadas = [camadaAtributos(ctx), camadaRegiao(ctx), camadaClasses(ctx)];
  for (let i = 0; i < camadas.length; i++) {
    if (camadas[i].length) return camadas[i];
  }
  return [];
}

function extrairRoster(raiz) {
  const ctx = escopo(raiz);
  if (!ctx) return [];
  const vistos = [];
  const tiles = ctx.querySelectorAll("[data-participant-id], [data-self-name]");
  tiles.forEach(function (tile, i) {
    const nome = tile.getAttribute("data-self-name") || textoLimpo(tile);
    if (!nome || nome.length < 2 || nome.length >= MAX_NOME) return;
    const idAttr =
      tile.getAttribute("data-participant-id") ||
      tile.getAttribute("data-requested-participant-id");
    vistos.push({ id: idAttr || idLocal("roster", i), nome: nome.trim(), efemero: !idAttr });
  });
  return vistos;
}

function extrairAtividade(raiz) {
  const ctx = escopo(raiz);
  if (!ctx) return [];
  const sinais = [];
  const ativos = ctx.querySelectorAll(
    "[data-self-name][data-is-muted], [data-requested-participant-id][data-self-name], " +
      "[data-self-name].kssMZb, [data-self-name].gjg47c"
  );
  ativos.forEach(function (tile, i) {
    const nome = tile.getAttribute("data-self-name") || textoLimpo(tile);
    if (!nome) return;
    const idAttr = tile.getAttribute("data-participant-id") || tile.getAttribute("data-requested-participant-id");
    sinais.push({ id: idAttr || idLocal("atividade", i), nome: nome.trim(), efemero: !idAttr });
  });
  return sinais;
}

function consolidarRevisoes(pares) {
  const porId = new Map();
  (pares || []).forEach(function (fala) {
    if (!fala || !fala.id) return;
    const atual = porId.get(fala.id);
    if (!atual || (fala.revisao || 0) > (atual.revisao || 0)) {
      porId.set(fala.id, fala);
    }
  });
  return Array.from(porId.values());
}

function temSeletor(ctx, seletor) {
  try {
    return ctx.querySelector(seletor) !== null;
  } catch (_e) {
    return false;
  }
}

function avaliarCapacidades(raiz) {
  const ctx = escopo(raiz);
  if (!ctx) return { legendas: false, roster: false, motivo: "sem documento" };
  const legendas =
    temSeletor(ctx, "[data-caption-block]") ||
    temSeletor(ctx, '[role="region"]') ||
    temSeletor(ctx, ".nMcdL, .NWpY1d, .zs7s8d");
  const roster =
    temSeletor(ctx, "[data-participant-id]") || temSeletor(ctx, "[data-self-name]");
  let motivo = "seletores disponíveis";
  if (!legendas && !roster) motivo = "seletor desconhecido: capacidade indisponível";
  else if (!legendas) motivo = "legendas desligadas ou seletor desconhecido";
  return { legendas, roster, motivo };
}

const MeetParser = {
  extrairLegendas,
  extrairRoster,
  extrairAtividade,
  consolidarRevisoes,
  avaliarCapacidades,
  VERSAO: 1,
};

if (typeof window !== "undefined") {
  window.MeetParser = MeetParser;
}
if (typeof globalThis !== "undefined") {
  globalThis.MeetParser = MeetParser;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = MeetParser;
}
