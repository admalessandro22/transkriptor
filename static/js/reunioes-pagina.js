// Página Reuniões (SDD v1.9, T-14.B2): índice paginado sem conteúdo de fala.
import { icone, toast } from './ui.js';
import { ligarAcoesReunioes } from './reunioes-acoes.js';

const LIMITE = 20;
const QUALIDADE = { pronto: ['Pronta', 'processando'], parcial: ['Parcial', 'separando_vozes'], falhou: ['Falhou', 'erro'], complete: ['Pronta', 'processando'], partial: ['Parcial', 'separando_vozes'], failed: ['Falhou', 'erro'] };

function formatarData(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const dd = String(d.getDate()).padStart(2, '0'), mm = String(d.getMonth() + 1).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0'), mi = String(d.getMinutes()).padStart(2, '0');
  return `${dd}/${mm}/${d.getFullYear()} · ${hh}:${mi}`;
}

function formatarDuracao(ms) {
  if (ms == null) return '—';
  const min = Math.round(ms / 60000);
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, '0')} min`;
}

function textoParticipantes(dados) {
  const nomes = (dados && dados.participantes) || [];
  const semNome = (dados && dados.sem_nome) || 0;
  if (!nomes.length && !semNome) return 'Participantes não identificados';
  if (!nomes.length) return semNome === 1 ? '1 participante sem nome' : `${semNome} participantes sem nome`;
  return nomes.join(', ') + (semNome ? ` + ${semNome} sem nome` : '');
}

const participantesCache = new Map();

/** Nomes lidos sob demanda (o índice não guarda nomes — SEC-13.E4). */
export async function preencherParticipantes(raiz, fetchFn = (u, o) => fetch(u, o)) {
  const alvos = [...raiz.querySelectorAll('.tk-row[data-id] .tk-row__participantes[data-pendente]')];
  const fila = alvos.slice();
  async function trabalhador() {
    while (fila.length) {
      const el = fila.shift();
      const id = el.closest('.tk-row').dataset.id;
      el.removeAttribute('data-pendente');
      try {
        if (!participantesCache.has(id)) {
          const r = await fetchFn('/api/reunioes/' + encodeURIComponent(id) + '/participantes', { credentials: 'same-origin' });
          participantesCache.set(id, r.ok ? await r.json() : null);
        }
        el.textContent = textoParticipantes(participantesCache.get(id));
        el.title = el.textContent;
      } catch (_) {
        el.textContent = 'Participantes não identificados';
      }
    }
  }
  await Promise.all([1, 2, 3].map(trabalhador));
}

const RESUMO_POLL_MS = 15000;
let seqResumo = 0;
let timerResumos = null;

function aplicarResumo(el, dados) {
  const estado = (dados && dados.estado) || 'indisponivel';
  el.dataset.estado = estado;
  if (estado === 'pronto') el.textContent = dados.resumo;
  else if (estado === 'gerando') el.textContent = 'Gerando resumo com a IA local…';
  else if (estado === 'sem_resumo') el.textContent = 'Sem resumo automático (reunião anterior). Use o botão de resumo para gerar.';
  else el.textContent = 'Resumo indisponível: ' + ((dados && dados.motivo) || 'IA local indisponível');
}

/** Resumo curto (≤ 500 caracteres) da IA local, pedido sob demanda; atualiza enquanto gera. */
export async function preencherResumos(raiz, fetchFn = (u, o) => fetch(u, o)) {
  const alvos = [...raiz.querySelectorAll('.tk-row[data-id] .tk-row__resumo:not([data-estado="pronto"]):not([data-estado="indisponivel"]):not([data-estado="sem_resumo"])')];
  for (const el of alvos) {
    const id = el.closest('.tk-row').dataset.id;
    try {
      const r = await fetchFn('/api/reunioes/' + encodeURIComponent(id) + '/resumo', { credentials: 'same-origin' });
      aplicarResumo(el, r.ok ? await r.json() : null);
    } catch (_) {
      aplicarResumo(el, null);
    }
  }
  const gerando = raiz.querySelector('.tk-row__resumo[data-estado="gerando"]');
  if (timerResumos) { clearTimeout(timerResumos); timerResumos = null; }
  if (gerando && raiz.isConnected) timerResumos = setTimeout(() => preencherResumos(raiz, fetchFn), RESUMO_POLL_MS);
}

function doisDigitos(n) { return String(n).padStart(2, '0'); }

/** { data: "24/09/2026", inicio: "16:05", fim: "17:01" } — fim só com duração conhecida. */
export function horarios(r) {
  const d = new Date(r.started_at);
  if (!r.started_at || Number.isNaN(d.getTime())) return { data: '—', inicio: '—', fim: '—' };
  const hora = (x) => `${doisDigitos(x.getHours())}:${doisDigitos(x.getMinutes())}`;
  const fim = r.duration_ms != null ? hora(new Date(d.getTime() + r.duration_ms)) : '—';
  return { data: `${doisDigitos(d.getDate())}/${doisDigitos(d.getMonth() + 1)}/${d.getFullYear()}`, inicio: hora(d), fim };
}

function celula(classe, rotulo, conteudo) {
  const c = document.createElement('div');
  c.className = 'tk-reuniao__cel tk-reuniao__' + classe;
  c.setAttribute('role', 'cell');
  c.dataset.rotulo = rotulo;
  if (typeof conteudo === 'string') c.textContent = conteudo; else if (conteudo) c.append(...[].concat(conteudo));
  return c;
}

function botaoAcao(acao, rotulo, nomeIcone, perigo = false) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'tk-btn tk-btn--sm tk-btn--quiet tk-btn--icon tk-reuniao__acao' + (perigo ? ' tk-reuniao__acao--perigo' : '');
  b.dataset.acao = acao;
  b.setAttribute('aria-label', rotulo);
  b.title = rotulo;
  b.appendChild(icone(nomeIcone, 'tk-icon tk-icon--sm'));
  return b;
}

/** Cabeçalho das colunas (só na página Reuniões). */
export function cabecalhoReunioes() {
  const cab = document.createElement('div');
  cab.className = 'tk-reuniao tk-reuniao--cabecalho';
  cab.setAttribute('role', 'row');
  for (const [classe, texto] of [['nome', 'Reunião'], ['data', 'Data'], ['inicio', 'Início'], ['fim', 'Fim'], ['duracao', 'Duração'], ['pessoas', 'Participantes'], ['estado', 'Status'], ['acoes', 'Ações']]) {
    const c = document.createElement('div');
    c.className = 'tk-reuniao__cel tk-reuniao__' + classe;
    c.setAttribute('role', 'columnheader');
    if (classe === 'acoes') { const t = document.createElement('span'); t.className = 'tk-visually-hidden'; t.textContent = texto; c.appendChild(t); } else c.textContent = texto;
    cab.appendChild(c);
  }
  return cab;
}

export function linhaReuniao(r, { acoes = false } = {}) {
  const div = document.createElement('div');
  div.className = 'tk-row tk-row--reuniao tk-reuniao';
  div.setAttribute('role', 'row');
  div.dataset.id = r.meeting_id;
  div.dataset.titulo = r.title || '';
  const abrir = document.createElement('a');
  abrir.className = 'tk-row__abrir';
  abrir.href = '/participantes?reuniao=' + encodeURIComponent(r.meeting_id);
  abrir.textContent = r.title || 'Reunião sem título';
  if (!r.title) abrir.classList.add('is-sem-titulo');
  const resumo = document.createElement('span');
  resumo.className = 'tk-row__resumo';
  resumo.id = 'resumo-reuniao-' + (++seqResumo);
  resumo.setAttribute('role', 'tooltip');
  resumo.textContent = 'Carregando resumo…';
  abrir.setAttribute('aria-describedby', resumo.id);
  const h = horarios(r);
  const pessoas = document.createElement('span');
  pessoas.className = 'tk-row__participantes';
  pessoas.dataset.pendente = '';
  pessoas.textContent = 'Carregando…';
  const [rotulo, estado] = QUALIDADE[r.quality_state] || ['Parcial', 'separando_vozes'];
  const badge = document.createElement('span');
  badge.className = 'tk-badge tk-badge-state';
  badge.dataset.estado = estado;
  badge.textContent = rotulo;
  badge.title = 'Revisão ' + (String(r.revision || '').replace(/^rev-/, '') || '—');
  const cels = [
    celula('nome', 'Reunião', [abrir, resumo]),
    celula('data', 'Data', h.data),
    celula('inicio', 'Início', h.inicio),
    celula('fim', 'Fim', h.fim),
    celula('duracao', 'Duração', formatarDuracao(r.duration_ms)),
    celula('pessoas', 'Participantes', pessoas),
    celula('estado', 'Status', badge),
  ];
  if (acoes) {
    const assistente = document.createElement('a');
    assistente.className = 'tk-btn tk-btn--sm tk-btn--quiet tk-btn--icon tk-reuniao__acao tk-row__assistente';
    assistente.href = '/?reuniao=' + encodeURIComponent(r.arquivo || r.meeting_id);
    assistente.setAttribute('aria-label', 'Abrir no Assistente');
    assistente.title = 'Abrir no Assistente';
    assistente.appendChild(icone('message', 'tk-icon tk-icon--sm'));
    cels.push(celula('acoes', 'Ações', [
      botaoAcao('resumo', 'Ver resumo da IA', 'sparkles'),
      botaoAcao('editar', 'Editar nome e participantes', 'edit'),
      assistente,
      botaoAcao('excluir', 'Excluir reunião', 'trash', true),
    ]));
  }
  div.append(...cels);
  return div;
}

export function criarPaginaReunioes({ raiz, fetchFn = (u, o) => fetch(u, o) }) {
  const lista = raiz.querySelector('#lista-reunioes');
  const estadoEl = raiz.querySelector('#lista-reunioes-estado');
  const maisBtn = raiz.querySelector('#carregar-mais');
  const busca = raiz.querySelector('#busca-reunioes');
  let cursor = null;
  let itens = [];
  let carregando = false;

  function mostrarEstado(tipo, texto) {
    estadoEl.className = 'tk-empty';
    estadoEl.hidden = false;
    estadoEl.innerHTML = '';
    const h = document.createElement('h3'); h.className = 'tk-empty__titulo';
    const p = document.createElement('p'); p.className = 'tk-empty__texto';
    if (tipo === 'vazio') { h.textContent = 'Nenhuma reunião ainda'; p.textContent = 'A primeira aparece aqui depois de gravada e processada.'; }
    else if (tipo === 'sem-resultado') { h.textContent = 'Nada combina com o filtro'; p.textContent = 'Tente outra data ou limpe a busca.'; }
    else { h.textContent = 'Não foi possível carregar'; p.textContent = texto || 'A Central não conseguiu ler o índice de reuniões.'; }
    estadoEl.append(h, p);
    if (tipo === 'erro') {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'tk-btn'; b.textContent = 'Tentar de novo';
      b.addEventListener('click', () => carregar(true));
      estadoEl.appendChild(b);
    }
  }

  function renderizar() {
    lista.innerHTML = '';
    const q = (busca && busca.value || '').trim().toLowerCase();
    const visiveis = q ? itens.filter((r) => (formatarData(r.started_at) + ' ' + (r.title || '') + ' ' + r.meeting_id + ' ' + textoParticipantes(participantesCache.get(r.meeting_id))).toLowerCase().includes(q)) : itens;
    if (!itens.length) { mostrarEstado('vazio'); lista.hidden = true; return; }
    if (!visiveis.length) { mostrarEstado('sem-resultado'); lista.hidden = true; return; }
    estadoEl.hidden = true; lista.hidden = false;
    lista.appendChild(cabecalhoReunioes());
    visiveis.forEach((r) => lista.appendChild(linhaReuniao(r, { acoes: true })));
    preencherParticipantes(lista, fetchFn);
    preencherResumos(lista, fetchFn);
  }

  async function carregar(reiniciar) {
    if (carregando) return;
    carregando = true;
    if (reiniciar) { cursor = null; itens = []; lista.innerHTML = ''; lista.hidden = true; estadoEl.hidden = true; }
    lista.setAttribute('aria-busy', 'true');
    maisBtn.classList.add('is-loading');
    try {
      const url = '/api/reunioes-indice?limit=' + LIMITE + (cursor ? '&cursor=' + encodeURIComponent(cursor) : '');
      const r = await fetchFn(url, { credentials: 'same-origin' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const dados = await r.json();
      const vistos = new Set(itens.map((i) => i.meeting_id));
      (dados.reunioes || []).forEach((i) => { if (!vistos.has(i.meeting_id)) { itens.push(i); vistos.add(i.meeting_id); } });
      cursor = dados.proximo || null;
      maisBtn.hidden = !cursor;
      renderizar();
    } catch (e) {
      mostrarEstado('erro');
      lista.hidden = true;
      maisBtn.hidden = true;
    } finally {
      carregando = false;
      lista.removeAttribute('aria-busy');
      maisBtn.classList.remove('is-loading');
    }
  }

  maisBtn.addEventListener('click', () => carregar(false));
  ligarAcoesReunioes(lista, {
    fetchFn,
    aoMudar: () => { participantesCache.clear(); carregar(true); },
    aoExcluir: (id) => { itens = itens.filter((r) => r.meeting_id !== id); renderizar(); },
  });
  document.addEventListener('tk-resumos-atualizar', () => preencherResumos(lista, fetchFn));
  if (busca) busca.addEventListener('input', renderizar);
  carregar(true);
  return { carregar, get itens() { return itens.slice(); } };
}

if (typeof document !== 'undefined' && document.getElementById('pagina-reunioes')) {
  criarPaginaReunioes({ raiz: document.getElementById('pagina-reunioes') });
  window.addEventListener('error', (e) => { if (e && e.message) toast('error', 'Erro na página', e.message); });
}
