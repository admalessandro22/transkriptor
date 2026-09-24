// Página Reuniões (SDD v1.9, T-14.B2): índice paginado sem conteúdo de fala.
import { toast } from './ui.js';

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

export function linhaReuniao(r) {
  const div = document.createElement('div');
  div.className = 'tk-row';
  div.dataset.id = r.meeting_id;
  const principal = document.createElement('span');
  principal.className = 'tk-row__principal';
  principal.textContent = `${formatarData(r.started_at)}${r.title ? ' · ' + r.title : ''}`;
  principal.title = r.meeting_id;
  const meta = document.createElement('span');
  meta.className = 'tk-row__meta';
  meta.textContent = `${formatarDuracao(r.duration_ms)} · Revisão ${String(r.revision || '').replace(/^rev-/, '') || '—'}`;
  const [rotulo, estado] = QUALIDADE[r.quality_state] || ['Parcial', 'separando_vozes'];
  const badge = document.createElement('span');
  badge.className = 'tk-badge tk-badge-state';
  badge.dataset.estado = estado;
  badge.textContent = rotulo;
  const abrir = document.createElement('a');
  abrir.className = 'tk-btn tk-btn--sm tk-btn--quiet';
  abrir.href = '/?reuniao=' + encodeURIComponent(r.meeting_id);
  abrir.textContent = 'Abrir no Assistente';
  div.append(principal, meta, badge, abrir);
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
    const visiveis = q ? itens.filter((r) => (formatarData(r.started_at) + ' ' + (r.title || '') + ' ' + r.meeting_id).toLowerCase().includes(q)) : itens;
    if (!itens.length) { mostrarEstado('vazio'); lista.hidden = true; return; }
    if (!visiveis.length) { mostrarEstado('sem-resultado'); lista.hidden = true; return; }
    estadoEl.hidden = true; lista.hidden = false;
    visiveis.forEach((r) => lista.appendChild(linhaReuniao(r)));
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
  if (busca) busca.addEventListener('input', renderizar);
  carregar(true);
  return { carregar, get itens() { return itens.slice(); } };
}

if (typeof document !== 'undefined' && document.getElementById('pagina-reunioes')) {
  criarPaginaReunioes({ raiz: document.getElementById('pagina-reunioes') });
  window.addEventListener('error', (e) => { if (e && e.message) toast('error', 'Erro na página', e.message); });
}
