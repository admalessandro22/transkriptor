// Participantes por reunião (SDD v1.9, T-14.C1): falantes com nome amigável, cor
// estável e estado; falas com sugestões; correção com undo. Contrato D7 preservado:
// resultado, correção (409 por revisão), desfazer, exportação explícita.
import { escapeHtml } from './markdown.js';
import { abrirPainel, fecharPainel, icone, confirmar, toast } from './ui.js';

const $ = (id) => document.getElementById(id);
const painel = $('participantes-drawer');
const selReuniao = $('reuniao-participantes');
const listaFalantes = $('lista-falantes');
const listaFalas = $('lista-participantes');
const filtroFalante = $('filtro-falante');
const skeleton = $('participantes-skeleton');
const selCluster = $('correcao-cluster');
const inputNome = $('correcao-nome');
const inputRevisao = $('correcao-revisao');
const estadoEl = $('participantes-estado');
const formCorrecao = $('form-correcao');
const btnDesfazer = $('desfazer-correcao');
const btnExportar = $('exportar-txt');
const btnFechar = $('fechar-participantes');
const btnAbrir = $('abrir-participantes');
const rotuloRevisao = $('reuniao-revisao');

const API_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
function apiHeaders(extra = {}) {
  const h = Object.assign({}, extra);
  if (API_TOKEN) h['X-Transkriptor-Token'] = API_TOKEN;
  return h;
}
const fetchOpts = { credentials: 'same-origin' };

const ORIGENS = { caption: 'legenda', google_entry: 'entrada do Meet', manual: 'manual', voz: 'voz', voice: 'voz', pendente: 'pendente' };
const NUM_CORES = 8;

let dados = null;
let mapaExib = {};
let clusters = [];
let filtroAtivo = '';

// ---- nomes, cores e tempos --------------------------------------------------

/**
 * Mapeamento usado para EXIBIR: nome confirmado pela legenda do Meet quando
 * todas as falas confirmadas do falante concordam; correção manual prevalece.
 * A correção/desfazer continua operando sobre `dados.mapeamento` original.
 */
export function mapeamentoExibicao(segmentos, mapeamento) {
  const porCluster = {};
  for (const s of segmentos || []) {
    const a = s && s.assignment;
    if (!a || a.status !== 'confirmed' || !a.display_name) continue;
    (porCluster[s.speaker_cluster_id] = porCluster[s.speaker_cluster_id] || []).push(a);
  }
  const mapa = {};
  for (const [cluster, lista] of Object.entries(porCluster)) {
    if (new Set(lista.map((a) => a.display_name)).size === 1) {
      mapa[cluster] = { display_name: lista[0].display_name, origem: lista[0].source || 'caption' };
    }
  }
  for (const [cluster, entrada] of Object.entries(mapeamento || {})) {
    if (entrada && entrada.display_name) mapa[cluster] = entrada;
  }
  return mapa;
}

/** "FALANTE_00" → "Falante 1" (pela ordem estável dos clusters); nomes mapeados prevalecem. */
export function nomeAmigavel(cluster, mapeamento, ordem) {
  const entrada = (mapeamento || {})[cluster];
  if (entrada && entrada.display_name) return entrada.display_name;
  const idx = (ordem || []).indexOf(cluster);
  const m = /^FALANTE_(\d+)$/.exec(cluster || '');
  if (idx >= 0) return `Falante ${idx + 1}`;
  if (m) return `Falante ${parseInt(m[1], 10) + 1}`;
  return cluster || 'Falante';
}

/** Índice de cor 1..8 estável por cluster (posição na ordem; cai num hash se fora dela). */
export function corDoFalante(cluster, ordem) {
  const idx = (ordem || []).indexOf(cluster);
  if (idx >= 0) return (idx % NUM_CORES) + 1;
  let h = 0;
  for (const ch of String(cluster)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return (h % NUM_CORES) + 1;
}

export function tempo(ms) {
  const s = Math.max(0, Math.floor((ms || 0) / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}

function numeroRevisao(rev) {
  const m = /(\d+)\s*$/.exec(String(rev || ''));
  return m ? m[1] : (rev || '—');
}

export function estadoDoFalante(cluster, mapeamento, segmentos) {
  const entrada = (mapeamento || {})[cluster];
  if (entrada && entrada.display_name) return { rotulo: 'Confirmado', estado: 'confirmado', origem: ORIGENS[entrada.origem] || entrada.origem || 'manual' };
  const segs = (segmentos || []).filter((s) => s.speaker_cluster_id === cluster);
  const sugestoes = segs.filter((s) => s.assignment && s.assignment.status === 'suggested' && s.assignment.display_name);
  if (sugestoes.length) {
    const nomes = new Set(sugestoes.map((s) => s.assignment.display_name));
    return nomes.size === 1
      ? { rotulo: 'Sugerido', estado: 'sugerido', origem: ORIGENS[sugestoes[0].assignment.source] || 'desconhecida', sugestao: sugestoes[0].assignment.display_name }
      : { rotulo: 'Sugestões divergentes', estado: 'divergente', origem: 'legenda' };
  }
  return { rotulo: 'Identificação pendente', estado: 'pendente', origem: 'pendente' };
}

// ---- carga ------------------------------------------------------------------

function dizer(texto, tipo = 'info') {
  if (!estadoEl) return;
  estadoEl.textContent = texto;
  estadoEl.dataset.tipo = tipo;
}

function carregando(sim) {
  if (skeleton) skeleton.hidden = !sim;
  if (painel) painel.setAttribute('aria-busy', sim ? 'true' : 'false');
  [listaFalantes, listaFalas, formCorrecao].forEach((el) => { if (el) el.classList.toggle('is-hidden', sim); });
}

/** "22/09/2026 · 10:03 · Título" por meeting_id, a partir do índice (sem fala). */
async function rotulosDoIndice() {
  const rotulos = {};
  try {
    const r = await fetch('/api/reunioes-indice?limit=100', { ...fetchOpts, headers: apiHeaders() });
    if (!r.ok) return rotulos;
    for (const item of (await r.json()).reunioes || []) {
      const d = new Date(item.started_at);
      const data = Number.isNaN(d.getTime()) ? '' : `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()} · ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
      rotulos[item.meeting_id] = [data, item.title].filter(Boolean).join(' · ') || item.meeting_id;
    }
  } catch (_) { /* rótulo cai no id */ }
  return rotulos;
}

export async function carregarReunioes() {
  if (!selReuniao) return;
  carregando(true);
  try {
    const r = await fetch('/api/reunioes', { ...fetchOpts, headers: apiHeaders() });
    const ids = await r.json();
    const rotulos = await rotulosDoIndice();
    selReuniao.innerHTML = '';
    (ids || []).forEach((id) => { const op = document.createElement('option'); op.value = id; op.textContent = rotulos[id] || id; op.title = id; selReuniao.appendChild(op); });
    const pedida = new URLSearchParams(window.location.search).get('reuniao');
    if (pedida && (ids || []).includes(pedida)) selReuniao.value = pedida;
    if (selReuniao.value) await carregarResultado();
    else { carregando(false); renderVazio(); }
  } catch (_) {
    carregando(false);
    dizer('Não foi possível listar as reuniões. Tente de novo.', 'erro');
  }
}

function renderVazio() {
  if (listaFalantes) listaFalantes.innerHTML = '';
  if (listaFalas) { listaFalas.innerHTML = ''; const p = document.createElement('p'); p.className = 'tk-subtle'; p.textContent = 'Nenhum resultado com participantes ainda. As reuniões processadas com separação de vozes aparecem aqui.'; listaFalas.appendChild(p); }
  if (rotuloRevisao) rotuloRevisao.textContent = 'Revisão —';
}

export async function carregarResultado() {
  if (!selReuniao || !selReuniao.value) return;
  carregando(true);
  dizer('');
  try {
    const r = await fetch('/api/reunioes/' + encodeURIComponent(selReuniao.value) + '/resultado', { ...fetchOpts, headers: apiHeaders() });
    if (!r.ok) { carregando(false); dizer('Reunião não encontrada.', 'erro'); return; }
    dados = await r.json();
  } catch (_) {
    carregando(false); dizer('Não foi possível carregar o resultado. Tente de novo.', 'erro'); return;
  }
  if (inputRevisao) inputRevisao.value = dados.revision || '';
  if (rotuloRevisao) rotuloRevisao.textContent = 'Revisão ' + numeroRevisao(dados.revision);
  clusters = [...new Set((dados.segmentos || []).map((s) => s.speaker_cluster_id))].sort();
  mapaExib = mapeamentoExibicao(dados.segmentos, dados.mapeamento);
  if (filtroAtivo && !clusters.includes(filtroAtivo)) filtroAtivo = '';
  carregando(false);
  render();
}

// ---- render -----------------------------------------------------------------

function avatarDe(cluster) {
  const av = document.createElement('span');
  av.className = 'falante__avatar';
  av.dataset.cor = String(corDoFalante(cluster, clusters));
  av.setAttribute('aria-hidden', 'true');
  const nome = nomeAmigavel(cluster, mapaExib, clusters);
  av.textContent = nome === 'VOCÊ' ? 'V' : nome.replace(/^Falante\s+/, '').slice(0, 1).toUpperCase();
  if (nome.startsWith('Falante ')) av.textContent = nome.replace('Falante ', '');
  return av;
}

function renderFalantes() {
  if (!listaFalantes) return;
  listaFalantes.innerHTML = '';
  const segs = dados.segmentos || [];
  for (const c of clusters) {
    const meus = segs.filter((s) => s.speaker_cluster_id === c);
    const total = meus.reduce((acc, s) => acc + Math.max(0, (s.end_ms || 0) - (s.start_ms || 0)), 0);
    const info = estadoDoFalante(c, mapaExib, segs);
    const nome = nomeAmigavel(c, mapaExib, clusters);
    const li = document.createElement('li');
    li.className = 'falante';
    li.dataset.cluster = c;
    li.dataset.estado = info.estado;
    li.title = c;
    const corpo = document.createElement('div'); corpo.className = 'falante__corpo';
    const n = document.createElement('span'); n.className = 'falante__nome'; n.textContent = nome;
    if (nome === 'VOCÊ') { const b = document.createElement('span'); b.className = 'tk-badge tk-badge-protect tk-badge-protect--voce'; b.textContent = 'Você'; n.appendChild(document.createTextNode(' ')); n.appendChild(b); }
    const meta = document.createElement('span'); meta.className = 'falante__meta tk-num';
    meta.textContent = `${meus.length} ${meus.length === 1 ? 'fala' : 'falas'} · ${Math.max(1, Math.round(total / 60000))} min`;
    const est = document.createElement('span'); est.className = 'tk-badge falante__estado'; est.dataset.estado = info.estado;
    est.textContent = info.rotulo + (info.estado === 'confirmado' ? ' · ' + info.origem : '');
    corpo.append(n, meta, est);
    li.append(avatarDe(c), corpo);
    if (/^FALANTE_\d{2}$/.test(c)) {
      const aprender = document.createElement('button');
      aprender.type = 'button'; aprender.className = 'tk-btn tk-btn--quiet tk-btn--sm falante__aprender'; aprender.dataset.acao = 'aprender-voz';
      aprender.title = 'Aprender esta voz para próximas reuniões';
      aprender.setAttribute('aria-label', 'Aprender a voz de ' + nome + ' para próximas reuniões');
      aprender.appendChild(icone('user', 'tk-icon tk-icon--sm'));
      aprender.appendChild(document.createTextNode(' Aprender voz'));
      aprender.addEventListener('click', (ev) => { ev.stopPropagation(); aprenderVoz(c); });
      li.appendChild(aprender);
    }
    li.addEventListener('click', () => { if (selCluster) selCluster.value = c; alternarFiltro(c); });
    listaFalantes.appendChild(li);
  }
}

function alternarFiltro(cluster) {
  filtroAtivo = filtroAtivo === cluster ? '' : cluster;
  renderFiltro();
  renderFalas();
}

function renderFiltro() {
  if (!filtroFalante) return;
  filtroFalante.innerHTML = '';
  const todos = document.createElement('button');
  todos.type = 'button'; todos.className = 'tk-chip' + (filtroAtivo ? '' : ' is-active'); todos.setAttribute('aria-pressed', filtroAtivo ? 'false' : 'true'); todos.textContent = 'Todos';
  todos.addEventListener('click', () => { filtroAtivo = ''; renderFiltro(); renderFalas(); });
  filtroFalante.appendChild(todos);
  for (const c of clusters) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'tk-chip' + (filtroAtivo === c ? ' is-active' : ''); b.dataset.cluster = c;
    b.setAttribute('aria-pressed', filtroAtivo === c ? 'true' : 'false');
    const ponto = document.createElement('span'); ponto.className = 'falante__ponto'; ponto.dataset.cor = String(corDoFalante(c, clusters)); ponto.setAttribute('aria-hidden', 'true');
    b.append(ponto, document.createTextNode(nomeAmigavel(c, mapaExib, clusters)));
    b.addEventListener('click', () => alternarFiltro(c));
    filtroFalante.appendChild(b);
  }
}

function porCluster(segs) {
  const m = new Map();
  segs.forEach((seg) => { const g = m.get(seg.speaker_cluster_id) || []; g.push(seg); m.set(seg.speaker_cluster_id, g); });
  return m;
}

function renderFalas() {
  if (!listaFalas) return;
  listaFalas.innerHTML = '';
  const mapa = mapaExib;
  const segs = dados.segmentos || [];
  const grupos = porCluster(segs);
  const visiveis = filtroAtivo ? segs.filter((s) => s.speaker_cluster_id === filtroAtivo) : segs;
  if (!visiveis.length) { const p = document.createElement('p'); p.className = 'tk-subtle'; p.textContent = 'Nenhuma fala para mostrar.'; listaFalas.appendChild(p); return; }
  for (const seg of visiveis) {
    const c = seg.speaker_cluster_id;
    const info = estadoDoFalante(c, mapa, segs);
    const nome = nomeAmigavel(c, mapa, clusters);
    const div = document.createElement('article');
    div.className = 'participante-seg fala';
    div.dataset.cluster = c;
    const cab = document.createElement('div'); cab.className = 'fala__cab';
    const t = document.createElement('span'); t.className = 'fala__tempo tk-num'; t.textContent = tempo(seg.start_ms);
    const chip = document.createElement('span'); chip.className = 'fala__falante'; chip.dataset.cor = String(corDoFalante(c, clusters));
    const pNome = document.createElement('span'); pNome.className = 'p-nome'; pNome.textContent = info.estado === 'confirmado' ? nome : 'Identificação pendente';
    const pOrigem = document.createElement('span'); pOrigem.className = 'p-origem';
    pOrigem.textContent = info.estado === 'confirmado' ? `(${info.origem})` : `(pendente, incerto · ${nome})`;
    chip.append(pNome, document.createTextNode(' '), pOrigem);
    const fonte = document.createElement('span'); fonte.className = 'fala__fonte'; fonte.title = seg.audio_source === 'microphone' || seg.audio_source === 'microfone' ? 'Microfone' : 'Áudio do sistema';
    fonte.appendChild(icone(seg.audio_source === 'microphone' || seg.audio_source === 'microfone' ? 'mic' : 'wave', 'tk-icon tk-icon--sm'));
    cab.append(t, chip, fonte);
    const texto = document.createElement('p'); texto.className = 'p-texto fala__texto'; texto.textContent = seg.text || '';
    div.append(cab, texto);
    const sugestao = seg.assignment;
    if (info.estado !== 'confirmado' && sugestao && sugestao.status === 'suggested' && sugestao.display_name) {
      div.appendChild(cartaoSugestao(seg, sugestao, grupos));
    }
    listaFalas.appendChild(div);
  }
}

function cartaoSugestao(seg, sugestao, grupos) {
  const origem = ORIGENS[sugestao.source] || 'desconhecida';
  const confianca = Number.isFinite(Number(sugestao.confidence)) ? Math.round(Number(sugestao.confidence) * 100) + '%' : 'indisponível';
  const box = document.createElement('div');
  box.className = 'p-sugestao fala__sugestao';
  const txt = document.createElement('div'); txt.className = 'fala__sugestao-texto';
  txt.textContent = 'Sugestão: ' + sugestao.display_name + ' · origem: ' + origem + ' · confiança: ' + confianca;
  box.appendChild(txt);
  const acoes = document.createElement('div'); acoes.className = 'fala__sugestao-acoes';
  const consenso = (grupos.get(seg.speaker_cluster_id) || []).every((o) => o.assignment && o.assignment.status === 'suggested' && o.assignment.display_name === sugestao.display_name && o.assignment.participant_id === sugestao.participant_id);
  if (consenso) {
    const confirmar = document.createElement('button');
    confirmar.type = 'button'; confirmar.className = 'tk-btn tk-btn--sm tk-btn--primary'; confirmar.textContent = 'Confirmar ' + sugestao.display_name;
    confirmar.addEventListener('click', () => { if (selCluster) selCluster.value = seg.speaker_cluster_id; if (inputNome) inputNome.value = sugestao.display_name; salvarCorrecao(); });
    acoes.appendChild(confirmar);
  } else {
    const aviso = document.createElement('span'); aviso.className = 'tk-subtle tk-type-xs'; aviso.textContent = 'Sugestões divergentes para este falante: escolha o nome manualmente.';
    acoes.appendChild(aviso);
  }
  const escolher = document.createElement('button');
  escolher.type = 'button'; escolher.className = 'tk-btn tk-btn--sm tk-btn--secondary'; escolher.textContent = 'Escolher outro nome';
  escolher.addEventListener('click', () => { if (selCluster) selCluster.value = seg.speaker_cluster_id; if (inputNome) { inputNome.value = ''; inputNome.focus(); } });
  acoes.appendChild(escolher);
  box.appendChild(acoes);
  return box;
}

function renderForm() {
  if (!selCluster) return;
  const atual = selCluster.value;
  selCluster.innerHTML = '';
  clusters.forEach((c) => {
    const op = document.createElement('option');
    op.value = c; op.textContent = nomeAmigavel(c, mapaExib, clusters); op.title = c;
    selCluster.appendChild(op);
  });
  if (atual && clusters.includes(atual)) selCluster.value = atual;
  renderUndo();
}

/** UX-14.C2: o botão Desfazer diz o que vai desfazer, a partir do último item do histórico. */
export function descricaoUndo(dados, ordem) {
  const historico = Array.isArray(dados && dados.historico) ? dados.historico : [];
  if (!historico.length) return '';
  const ultimo = historico[historico.length - 1];
  const cluster = String(ultimo.cluster || '');
  const amigavel = nomeAmigavel(cluster, {}, ordem);
  const atual = nomeAmigavel(cluster, dados.mapeamento, ordem);
  if (ultimo.acao === 'corrigir') {
    const anterior = ultimo.anterior && ultimo.anterior.display_name ? ultimo.anterior.display_name : 'Identificação pendente';
    return `Desfazer: ${atual} volta a ${anterior} (${amigavel})`;
  }
  return `Desfazer: última ação em ${amigavel} (revisão ${numeroRevisao(ultimo.revision)})`;
}

function renderUndo() {
  const descricao = descricaoUndo(dados, clusters);
  const el = $('desfazer-descricao');
  if (el) el.textContent = descricao || 'Nada a desfazer.';
  if (btnDesfazer) { btnDesfazer.disabled = !descricao; btnDesfazer.title = descricao || 'Nada a desfazer'; }
}

function render() {
  if (!dados) return;
  renderFalantes();
  renderFiltro();
  renderFalas();
  renderForm();
}

// ---- ações ------------------------------------------------------------------

export async function salvarCorrecao(ev) {
  if (ev) ev.preventDefault();
  if (!selReuniao || !selReuniao.value) return;
  const nome = inputNome ? inputNome.value.trim() : '';
  if (!nome) { dizer('Digite o nome corrigido antes de salvar.', 'erro'); if (inputNome) inputNome.focus(); return; }
  const r = await fetch('/api/reunioes/' + encodeURIComponent(selReuniao.value) + '/correcao', {
    ...fetchOpts, method: 'POST', headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ expected_revision: inputRevisao ? inputRevisao.value : '', speaker_cluster_id: selCluster ? selCluster.value : '', display_name: nome }),
  });
  const resp = await r.json();
  if (r.status === 409) { await carregarResultado(); dizer('Revisão divergente: o resultado foi atualizado por outra edição. Confira e confirme novamente.', 'aviso'); return; }
  if (!r.ok) { dizer(resp.erro || 'Não foi possível salvar a correção.', 'erro'); return; }
  await carregarResultado();
  if (inputNome) inputNome.value = '';
  dizer('Correção salva. Revisão ' + numeroRevisao(resp.revision) + '.', 'ok');
}

export async function desfazerCorrecao() {
  if (!selReuniao || !selReuniao.value) return;
  const r = await fetch('/api/reunioes/' + encodeURIComponent(selReuniao.value) + '/desfazer', {
    ...fetchOpts, method: 'POST', headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ expected_revision: inputRevisao ? inputRevisao.value : '' }),
  });
  const resp = await r.json();
  if (!r.ok) { dizer(resp.erro || 'Nada a desfazer.', 'aviso'); return; }
  await carregarResultado();
  dizer('Desfeito. Revisão ' + numeroRevisao(resp.revision) + '.', 'ok');
}

export async function exportarTxt() {
  if (!selReuniao || !selReuniao.value) return;
  // UX-14.C3: diálogo próprio com a consequência; nada é exportado sem confirmação.
  const ok = await confirmar({
    id: 'dialogo-exportar', confirmarId: 'confirmar-exportar',
    titulo: 'Exportar o texto legível desta reunião?',
    consequencia: 'O arquivo conterá o texto legível da reunião, com nomes e falas, fora da proteção do aplicativo. Guarde-o com cuidado.',
    confirmarRotulo: 'Exportar', perigo: true,
  });
  if (!ok) return;
  const id = selReuniao.value;
  const r = await fetch('/api/reunioes/' + encodeURIComponent(id) + '/exportar-txt', { ...fetchOpts, method: 'POST', headers: apiHeaders({ 'Content-Type': 'application/json' }), body: '{}' });
  if (!r.ok) { dizer('Não foi possível exportar o TXT.', 'erro'); return; }
  const url = URL.createObjectURL(await r.blob());
  try {
    const link = document.createElement('a'); link.href = url; link.download = 'reuniao-' + id + '.txt';
    document.body.appendChild(link); link.click(); link.remove();
    dizer('TXT exportado. Guarde o arquivo com cuidado.', 'ok');
  } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
}

/** UX-14.C3 (DU-07): ação separada da correção; cadastra a voz só com confirmação própria. */
export async function aprenderVoz(cluster) {
  if (!selReuniao?.value || !dados?.revision) return;
  const meetingId = selReuniao.value;
  const expectedRevision = dados.revision;
  const info = estadoDoFalante(cluster, mapaExib, dados.segmentos || []);
  const nome = info.estado === 'confirmado' ? nomeAmigavel(cluster, mapaExib, clusters) : (info.sugestao || '');
  if (!nome || /^Falante \d+$/.test(nome)) {
    toast('warning', 'Dê um nome ao falante antes', 'Corrija o nome nesta reunião (ou confirme a sugestão) e depois aprenda a voz.');
    return;
  }
  const ok = await confirmar({
    id: 'dialogo-aprender-voz', confirmarId: 'confirmar-aprender-voz',
    titulo: `Aprender a voz de ${nome}?`,
    consequencia: `A voz deste falante passa a ser reconhecida como "${nome}" nas próximas reuniões. É uma ação separada da correção desta reunião e pode ser revogada apagando as vozes conhecidas.`,
    confirmarRotulo: 'Aprender voz',
  });
  if (!ok) return;
  try {
    toast('info', 'Analisando a voz', 'Aguarde enquanto a amostra desta reunião é conferida.');
    const r = await fetch('/api/acoes/aprender-voz', { ...fetchOpts, method: 'POST', headers: apiHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ meeting_id: meetingId, expected_revision: expectedRevision, rotulo: cluster, nome }) });
    const resp = await r.json().catch(() => ({}));
    if (!r.ok) { toast('error', 'Não foi possível aprender a voz', resp.erro || 'Tente de novo.'); return; }
    toast('success', 'Voz aprendida', `${resp.salvo || nome} será reconhecido nas próximas reuniões.`);
  } catch (_) {
    toast('error', 'Não foi possível aprender a voz', 'Verifique se o aplicativo da bandeja está aberto.');
  }
}

function abrirParticipantes(aberto) {
  if (!painel) return;
  if (aberto) {
    abrirPainel('participantes-drawer');
    carregarReunioes();
    if (selReuniao) selReuniao.focus();
  } else {
    fecharPainel('participantes-drawer');
  }
}

export function iniciarParticipantes({ modo = 'painel' } = {}) {
  if (btnAbrir) btnAbrir.onclick = () => abrirParticipantes(true);
  if (btnFechar) btnFechar.onclick = () => abrirParticipantes(false);
  if (selReuniao) selReuniao.addEventListener('change', carregarResultado);
  if (formCorrecao) formCorrecao.addEventListener('submit', salvarCorrecao);
  if (btnDesfazer) btnDesfazer.onclick = desfazerCorrecao;
  if (btnExportar) btnExportar.onclick = exportarTxt;
  if (modo === 'pagina' && painel) painel.hidden = false;
}
