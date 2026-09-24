// Listbox de reuniões (SDD v1.9, T-14.B2/B3). Módulo ES; sem fala na lista, só metadados.

function escapar(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function iconeSvg(nome) {
  return '<svg class="tk-icon" aria-hidden="true"><use href="/static/icones.svg#i-' + nome + '"/></svg>';
}

function badgesDe(item) {
  const b = [];
  if (/\.tkpt$/i.test(item.arquivo || '')) b.push('<span class="tk-badge tk-badge-protect tk-badge-protect--protegida">Protegida</span>');
  if (item.tipo === 'diarizado') b.push('<span class="tk-badge">Separada por vozes</span>');
  if (item.com_sua_voz === true) b.push('<span class="tk-badge tk-badge-protect tk-badge-protect--voce badge-voce">Com sua voz</span>');
  return b.join('');
}

function metaDe(item) {
  const partes = [];
  if (item.tamanho_kb != null) partes.push(item.tamanho_kb + ' KB');
  if (item.duracao_min != null) partes.push(item.duracao_min + ' min');
  if (item.estado) partes.push(escapar(item.estado));
  return partes.join(' · ');
}

const MENSAGENS = {
  vazio: 'Nenhuma reunião ainda. A primeira aparece aqui depois de gravada.',
  'sem-resultado': 'Nenhuma reunião combina com o filtro.',
  erro: 'Não foi possível carregar a lista.',
};

/**
 * Transforma `<ul role="listbox">` numa lista de reuniões com seleção única,
 * teclado completo e estados. Expõe `value`/`options` no próprio elemento
 * para compatibilidade com quem tratava o controle como <select>.
 */
export function criarListbox(ul, opcoes) {
  opcoes = opcoes || {};
  let itens = [];
  let selecionado = '';
  let ativo = -1;
  let buscaTexto = '';
  let buscaTimer = null;

  ul.setAttribute('role', 'listbox');
  ul.classList.add('tk-listbox');
  if (!ul.hasAttribute('tabindex')) ul.tabIndex = 0;

  function lis() { return Array.from(ul.querySelectorAll('[role="option"]')); }

  function atualizarAtivo(idx, focar) {
    const lista = lis();
    lista.forEach((li) => li.classList.remove('is-active'));
    if (idx < 0 || idx >= lista.length) { ativo = -1; ul.removeAttribute('aria-activedescendant'); return; }
    ativo = idx;
    lista[idx].classList.add('is-active');
    ul.setAttribute('aria-activedescendant', lista[idx].id);
    if (focar !== false && typeof lista[idx].scrollIntoView === 'function') lista[idx].scrollIntoView({ block: 'nearest' });
  }

  function selecionar(id, origem) {
    const anterior = selecionado;
    selecionado = id || '';
    lis().forEach((li, i) => {
      const marcado = li.dataset.id === selecionado;
      li.setAttribute('aria-selected', marcado ? 'true' : 'false');
      if (marcado) atualizarAtivo(i, origem === 'teclado');
    });
    if (anterior !== selecionado) ul.dispatchEvent(new Event('change', { bubbles: true }));
    if (opcoes.aoSelecionar) opcoes.aoSelecionar(selecionado, origem);
  }

  function render(novos) {
    ul.setAttribute('role', 'listbox');
    itens = Array.isArray(novos) ? novos.slice() : [];
    ul.innerHTML = '';
    ul.classList.remove('is-loading', 'is-empty', 'is-error');
    ul.removeAttribute('aria-busy');
    if (!itens.length) return;
    itens.forEach((item, i) => {
      const li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.id = ul.id + '-op-' + i;
      li.dataset.id = item.arquivo;
      li.setAttribute('aria-selected', item.arquivo === selecionado ? 'true' : 'false');
      li.innerHTML =
        '<span class="tk-listbox__titulo">' + escapar(item.data || item.arquivo) + '</span>' +
        '<span class="tk-listbox__meta"><span>' + metaDe(item) + '</span><span class="tk-listbox__badges">' + badgesDe(item) + '</span></span>';
      li.title = item.arquivo || '';
      li.addEventListener('click', () => { selecionar(item.arquivo, 'clique'); ul.focus(); });
      ul.appendChild(li);
    });
    const idx = itens.findIndex((t) => t.arquivo === selecionado);
    atualizarAtivo(idx >= 0 ? idx : 0, false);
  }

  function estado(nome, mensagem) {
    itens = [];
    ul.innerHTML = '';
    ul.classList.remove('is-loading', 'is-empty', 'is-error');
    ul.removeAttribute('aria-activedescendant');
    ul.setAttribute('role', 'listbox');
    if (nome === 'carregando') {
      ul.classList.add('is-loading');
      ul.setAttribute('aria-busy', 'true');
      for (let i = 0; i < 3; i++) { const li = document.createElement('li'); li.className = 'tk-skeleton tk-skeleton--card'; li.setAttribute('aria-hidden', 'true'); ul.appendChild(li); }
      return;
    }
    ul.removeAttribute('aria-busy');
    const li = document.createElement('li');
    li.className = 'tk-listbox__estado';
    // Sem opções não há listbox: vira lista simples com a mensagem (axe: aria-required-children).
    ul.setAttribute('role', 'list');
    li.textContent = mensagem || MENSAGENS[nome] || '';
    if (nome === 'erro') {
      ul.classList.add('is-error');
      const btn = document.createElement('button');
      btn.type = 'button'; btn.className = 'tk-btn tk-btn--sm'; btn.textContent = 'Tentar de novo';
      btn.addEventListener('click', () => ul.dispatchEvent(new Event('tk-recarregar')));
      li.appendChild(document.createTextNode(' '));
      li.appendChild(btn);
    } else {
      ul.classList.add('is-empty');
    }
    ul.appendChild(li);
  }

  ul.addEventListener('keydown', (e) => {
    const lista = lis();
    if (!lista.length) return;
    let alvo = ativo;
    if (e.key === 'ArrowDown') alvo = Math.min(lista.length - 1, ativo + 1);
    else if (e.key === 'ArrowUp') alvo = Math.max(0, ativo - 1);
    else if (e.key === 'Home') alvo = 0;
    else if (e.key === 'End') alvo = lista.length - 1;
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (ativo >= 0) selecionar(lista[ativo].dataset.id, 'teclado'); return; }
    else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      buscaTexto += e.key.toLowerCase();
      clearTimeout(buscaTimer); buscaTimer = setTimeout(() => { buscaTexto = ''; }, 600);
      const i = lista.findIndex((li) => li.textContent.trim().toLowerCase().startsWith(buscaTexto));
      if (i >= 0) { atualizarAtivo(i); }
      return;
    } else return;
    e.preventDefault();
    atualizarAtivo(alvo, true);
  });

  Object.defineProperty(ul, 'value', {
    configurable: true,
    get: () => selecionado,
    set: (v) => { selecionar(v || '', 'programa'); },
  });
  Object.defineProperty(ul, 'options', {
    configurable: true,
    get: () => lis().map((li) => Object.assign(li, { value: li.dataset.id })),
  });

  const api = { render, estado, selecionar: (id) => selecionar(id, 'programa'), get itens() { return itens.slice(); }, get value() { return selecionado; } };
  ul._tkLista = api;
  return api;
}

if (typeof window !== 'undefined') window.TkReunioes = { criarListbox, badgesDe, escapar };
