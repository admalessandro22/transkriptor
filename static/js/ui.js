// Primitivas de interface da Central (SDD v1.9, T-14.A3): toast, diálogo,
// painel lateral e tema. Módulo ES sem dependências; só altera classes.
const ICONES = '/static/icones.svg';
const DURACAO_TOAST_MS = 4000;

export function icone(nome, classe = 'tk-icon') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', classe);
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `${ICONES}#i-${nome}`);
  svg.appendChild(use);
  return svg;
}

function regiaoToasts() {
  let regiao = document.getElementById('toast-region');
  if (!regiao) {
    regiao = document.createElement('div');
    regiao.id = 'toast-region';
    document.body.appendChild(regiao);
  }
  regiao.classList.add('tk-toast-region');
  if (!regiao.getAttribute('aria-live')) regiao.setAttribute('aria-live', 'polite');
  return regiao;
}

const ICONE_POR_TIPO = { info: 'info', success: 'check', warning: 'alert', error: 'alert' };

/** Toast tipado. `error` persiste até ser fechado; os demais somem em 4 s. */
export function toast(tipo, titulo, texto = '', opcoes = {}) {
  const regiao = regiaoToasts();
  const el = document.createElement('div');
  el.className = `tk-toast tk-toast--${tipo}`;
  el.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
  const ic = icone(ICONE_POR_TIPO[tipo] || 'info', 'tk-icon tk-toast__icone');
  const corpo = document.createElement('div');
  const t = document.createElement('div'); t.className = 'tk-toast__titulo'; t.textContent = titulo;
  corpo.appendChild(t);
  if (texto) { const x = document.createElement('div'); x.className = 'tk-toast__texto'; x.textContent = texto; corpo.appendChild(x); }
  const fechar = document.createElement('button');
  fechar.type = 'button'; fechar.className = 'tk-btn tk-btn--quiet tk-btn--sm tk-btn--icon tk-toast__fechar';
  fechar.setAttribute('aria-label', 'Fechar aviso');
  fechar.appendChild(icone('x', 'tk-icon tk-icon--sm'));
  el.append(ic, corpo, fechar);
  regiao.appendChild(el);
  let timer = null;
  const remover = () => { el.classList.add('is-leaving'); setTimeout(() => el.remove(), 220); };
  fechar.addEventListener('click', () => { if (timer) clearTimeout(timer); remover(); });
  if (tipo !== 'error' && !opcoes.persistente) timer = setTimeout(remover, opcoes.duracaoMs || DURACAO_TOAST_MS);
  return el;
}

function garantirDialogo() {
  let dlg = document.getElementById('dialogo-confirmacao');
  if (dlg) return dlg;
  dlg = document.createElement('dialog');
  dlg.id = 'dialogo-confirmacao';
  dlg.className = 'tk-dialog';
  dlg.setAttribute('aria-labelledby', 'dialogo-confirmacao-titulo');
  dlg.setAttribute('aria-describedby', 'dialogo-confirmacao-consequencia');
  const corpo = document.createElement('div'); corpo.className = 'tk-dialog__corpo';
  const titulo = document.createElement('h2'); titulo.className = 'tk-dialog__titulo'; titulo.id = 'dialogo-confirmacao-titulo';
  const cons = document.createElement('p'); cons.className = 'tk-dialog__consequencia'; cons.id = 'dialogo-confirmacao-consequencia';
  corpo.append(titulo, cons);
  const acoes = document.createElement('div'); acoes.className = 'tk-dialog__acoes';
  const cancelar = document.createElement('button'); cancelar.type = 'button'; cancelar.className = 'tk-btn tk-btn--secondary'; cancelar.dataset.acao = 'cancelar';
  const confirmar = document.createElement('button'); confirmar.type = 'button'; confirmar.className = 'tk-btn tk-btn--primary'; confirmar.dataset.acao = 'confirmar';
  acoes.append(cancelar, confirmar);
  dlg.append(corpo, acoes);
  document.body.appendChild(dlg);
  return dlg;
}

/**
 * Confirmação com texto de consequência. Resolve `true` só no botão confirmar.
 * Foco inicial fica no botão seguro (cancelar); Esc e clique fora cancelam.
 */
export function confirmar({ titulo, consequencia = '', confirmarRotulo = 'Confirmar', cancelarRotulo = 'Cancelar', perigo = false }) {
  const dlg = garantirDialogo();
  dlg.classList.toggle('tk-dialog--perigo', !!perigo);
  dlg.querySelector('.tk-dialog__titulo').textContent = titulo;
  dlg.querySelector('.tk-dialog__consequencia').textContent = consequencia;
  const bCancelar = dlg.querySelector('[data-acao="cancelar"]');
  const bConfirmar = dlg.querySelector('[data-acao="confirmar"]');
  bCancelar.textContent = cancelarRotulo;
  bConfirmar.textContent = confirmarRotulo;
  bConfirmar.className = 'tk-btn ' + (perigo ? 'tk-btn--danger' : 'tk-btn--primary');
  const anterior = document.activeElement;
  return new Promise((resolve) => {
    let resultado = false;
    const fim = () => {
      dlg.removeEventListener('close', fim);
      bConfirmar.removeEventListener('click', ok);
      bCancelar.removeEventListener('click', nao);
      dlg.removeEventListener('click', fora);
      if (anterior && anterior.focus) anterior.focus();
      resolve(resultado);
    };
    const ok = () => { resultado = true; dlg.close(); };
    const nao = () => { resultado = false; dlg.close(); };
    const fora = (e) => { if (e.target === dlg) nao(); };
    dlg.addEventListener('close', fim);
    bConfirmar.addEventListener('click', ok);
    bCancelar.addEventListener('click', nao);
    dlg.addEventListener('click', fora);
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
    bCancelar.focus();
  });
}

const focoAnteriorPorPainel = new Map();

function focaveis(raiz) {
  return [...raiz.querySelectorAll('button, select, input, textarea, a[href], [tabindex]:not([tabindex="-1"])')]
    .filter((el) => !el.disabled && el.offsetParent !== null);
}

/** Abre um `.tk-panel`; guarda o foco anterior e prende o Tab dentro dele. */
export function abrirPainel(id) {
  const painel = document.getElementById(id);
  if (!painel) return null;
  focoAnteriorPorPainel.set(id, document.activeElement);
  painel.hidden = false;
  painel.classList.add('is-open');
  painel.setAttribute('aria-hidden', 'false');
  document.body.classList.add('tk-layout--com-painel');
  const primeiro = focaveis(painel)[0];
  if (primeiro) primeiro.focus();
  if (!painel._tkArmadilha) {
    painel._tkArmadilha = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); fecharPainel(id); return; }
      if (e.key !== 'Tab') return;
      const lista = focaveis(painel);
      if (!lista.length) return;
      const a = lista[0], z = lista[lista.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    };
    painel.addEventListener('keydown', painel._tkArmadilha);
  }
  return painel;
}

/** Fecha o painel e devolve o foco a quem o abriu. */
export function fecharPainel(id) {
  const painel = document.getElementById(id);
  if (!painel) return;
  painel.classList.remove('is-open');
  painel.setAttribute('aria-hidden', 'true');
  painel.hidden = true;
  document.body.classList.remove('tk-layout--com-painel');
  const anterior = focoAnteriorPorPainel.get(id);
  focoAnteriorPorPainel.delete(id);
  if (anterior && anterior.focus) anterior.focus();
}

const CHAVE_TEMA = 'tk-tema';

function lerTema() {
  try { return localStorage.getItem(CHAVE_TEMA) || ''; } catch (_) { return ''; }
}

/** Aplica o tema salvo (`dark`/`light`) ou deixa o sistema decidir. */
export function aplicarTema(tema = lerTema()) {
  const raiz = document.documentElement;
  if (tema === 'dark' || tema === 'light') raiz.setAttribute('data-theme', tema);
  else raiz.removeAttribute('data-theme');
  document.querySelectorAll('[data-tema-toggle]').forEach((b) => {
    const efetivo = temaEfetivo();
    b.setAttribute('aria-pressed', efetivo === 'dark' ? 'true' : 'false');
    b.setAttribute('aria-label', efetivo === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro');
  });
  return tema;
}

export function temaEfetivo() {
  const forcado = document.documentElement.getAttribute('data-theme');
  if (forcado) return forcado;
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

/** Alterna e persiste o tema em localStorage (conveniência por visitante). */
export function alternarTema() {
  const novo = temaEfetivo() === 'dark' ? 'light' : 'dark';
  try { localStorage.setItem(CHAVE_TEMA, novo); } catch (_) { /* armazenamento indisponível */ }
  return aplicarTema(novo);
}

export function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Acesso global para scripts clássicos (assistente.js legado) até a migração para módulos.
if (typeof window !== 'undefined') {
  window.TkUI = { icone, toast, confirmar, abrirPainel, fecharPainel, aplicarTema, alternarTema, temaEfetivo, escapeHtml };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => aplicarTema());
  else aplicarTema();
}
