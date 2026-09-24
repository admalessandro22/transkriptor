// Drawer de participantes por reunião (D7) — extraído de assistente.js sem
// mudança de comportamento (SDD v1.9, T-14.B3). O redesenho é C1–C3.
import { escapeHtml } from './markdown.js';

const $ = (id) => document.getElementById(id);
const btnParticipantes = $('abrir-participantes');
const drawerParticipantes = $('participantes-drawer');
const selReuniao = $('reuniao-participantes');
const listaParticipantes = $('lista-participantes');
const selCluster = $('correcao-cluster');
const inputNome = $('correcao-nome');
const inputRevisao = $('correcao-revisao');
const estadoParticipantes = $('participantes-estado');
const formCorrecao = $('form-correcao');
const btnDesfazer = $('desfazer-correcao');
const btnExportarTxt = $('exportar-txt');
const btnFecharPart = $('fechar-participantes');
let ultimoFocoParticipantes = null;

const API_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
function apiHeaders(extra = {}) {
  const h = Object.assign({}, extra);
  if (API_TOKEN) h['X-Transkriptor-Token'] = API_TOKEN;
  return h;
}
const fetchOpts = { credentials: 'same-origin' };

function dizerParticipantes(texto) { if (estadoParticipantes) estadoParticipantes.textContent = texto; }

async function carregarReunioes() {
  if (!selReuniao) return;
  const r = await fetch('/api/reunioes', { ...fetchOpts, headers: apiHeaders() });
  const ids = await r.json();
  selReuniao.innerHTML = '';
  (ids || []).forEach((id) => { const op = document.createElement('option'); op.value = id; op.textContent = id; selReuniao.appendChild(op); });
  if (selReuniao.value) await carregarResultado();
  else if (listaParticipantes) listaParticipantes.innerHTML = '';
}

async function carregarResultado() {
  if (!selReuniao || !selReuniao.value) return;
  dizerParticipantes('Carregando...');
  const r = await fetch('/api/reunioes/' + encodeURIComponent(selReuniao.value) + '/resultado', { ...fetchOpts, headers: apiHeaders() });
  if (!r.ok) { dizerParticipantes('Reunião não encontrada.'); return; }
  const dados = await r.json();
  if (inputRevisao) inputRevisao.value = dados.revision || '';
  const rotuloRevisao = $('reuniao-revisao');
  if (rotuloRevisao) rotuloRevisao.textContent = 'Versão: ' + (dados.revision || '—');
  renderParticipantes(dados);
  dizerParticipantes('');
}

function nomeExibido(cluster, mapeamento) {
  const entrada = (mapeamento || {})[cluster];
  if (entrada && entrada.display_name) return { nome: entrada.display_name, origem: entrada.origem || 'manual', incerto: false };
  return { nome: 'Identificação pendente', origem: 'pendente', incerto: true };
}

function renderParticipantes(dados) {
  if (!listaParticipantes) return;
  listaParticipantes.innerHTML = '';
  const mapa = dados.mapeamento || {};
  const porCluster = new Map();
  (dados.segmentos || []).forEach((seg) => { const g = porCluster.get(seg.speaker_cluster_id) || []; g.push(seg); porCluster.set(seg.speaker_cluster_id, g); });
  (dados.segmentos || []).forEach((seg) => {
    const info = nomeExibido(seg.speaker_cluster_id, mapa);
    const div = document.createElement('div');
    div.className = 'participante-seg';
    div.innerHTML = '<span class="p-nome">' + escapeHtml(info.nome) + '</span> ' +
      '<span class="p-origem">(' + escapeHtml(info.origem + (info.incerto ? ', incerto' : '')) + ')</span> ' +
      '<span class="p-texto">' + escapeHtml(seg.text || '') + '</span>';
    const sugestao = seg.assignment;
    if (info.incerto && sugestao && sugestao.status === 'suggested' && sugestao.display_name) {
      const origem = { caption: 'legenda', google_entry: 'entrada do Meet', manual: 'manual' }[sugestao.source] || 'desconhecida';
      const confianca = Number.isFinite(Number(sugestao.confidence)) ? Math.round(Number(sugestao.confidence) * 100) + '%' : 'indisponível';
      const detalhes = document.createElement('div');
      detalhes.className = 'p-sugestao';
      detalhes.textContent = 'Sugestão: ' + sugestao.display_name + ' · origem: ' + origem + ' · confiança: ' + confianca;
      div.appendChild(detalhes);
      const consenso = (porCluster.get(seg.speaker_cluster_id) || []).every((o) => o.assignment && o.assignment.status === 'suggested' && o.assignment.display_name === sugestao.display_name && o.assignment.participant_id === sugestao.participant_id);
      if (consenso) {
        const confirmar = document.createElement('button');
        confirmar.type = 'button'; confirmar.textContent = 'Confirmar ' + sugestao.display_name;
        confirmar.addEventListener('click', () => { if (selCluster) selCluster.value = seg.speaker_cluster_id; if (inputNome) inputNome.value = sugestao.display_name; salvarCorrecao(); });
        div.appendChild(confirmar);
      }
      const escolher = document.createElement('button');
      escolher.type = 'button'; escolher.textContent = 'Escolher outro nome';
      escolher.addEventListener('click', () => { if (selCluster) selCluster.value = seg.speaker_cluster_id; if (inputNome) { inputNome.value = ''; inputNome.focus(); } });
      div.appendChild(escolher);
    }
    listaParticipantes.appendChild(div);
  });
  if (selCluster) {
    selCluster.innerHTML = '';
    [...new Set((dados.segmentos || []).map((s) => s.speaker_cluster_id))].forEach((c) => { const op = document.createElement('option'); op.value = c; op.textContent = c; selCluster.appendChild(op); });
  }
}

function abrirParticipantes(aberto) {
  if (!drawerParticipantes) return;
  if (aberto) { ultimoFocoParticipantes = document.activeElement; drawerParticipantes.hidden = false; carregarReunioes(); if (selReuniao) selReuniao.focus(); }
  else { drawerParticipantes.hidden = true; if (ultimoFocoParticipantes && ultimoFocoParticipantes.focus) ultimoFocoParticipantes.focus(); }
}

async function salvarCorrecao(ev) {
  if (ev) ev.preventDefault();
  if (!selReuniao || !selReuniao.value) return;
  const r = await fetch('/api/reunioes/' + encodeURIComponent(selReuniao.value) + '/correcao', {
    ...fetchOpts, method: 'POST', headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ expected_revision: inputRevisao ? inputRevisao.value : '', speaker_cluster_id: selCluster ? selCluster.value : '', display_name: inputNome ? inputNome.value : '' }),
  });
  const dados = await r.json();
  if (r.status === 409) { await carregarResultado(); dizerParticipantes('Revisão divergente; resultado atualizado. Confirme novamente.'); return; }
  if (!r.ok) { dizerParticipantes(dados.erro || 'Falha ao salvar.'); return; }
  await carregarResultado();
  dizerParticipantes('Correção salva (' + dados.revision + ').');
}

async function desfazerCorrecao() {
  if (!selReuniao || !selReuniao.value) return;
  const r = await fetch('/api/reunioes/' + encodeURIComponent(selReuniao.value) + '/desfazer', {
    ...fetchOpts, method: 'POST', headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ expected_revision: inputRevisao ? inputRevisao.value : '' }),
  });
  const dados = await r.json();
  if (!r.ok) { dizerParticipantes(dados.erro || 'Nada a desfazer.'); return; }
  await carregarResultado();
  dizerParticipantes('Desfeito (' + dados.revision + ').');
}

async function exportarTxt() {
  if (!selReuniao || !selReuniao.value) return;
  if (!window.confirm('Exportar TXT legível desta reunião? O arquivo contém dados sensíveis.')) return;
  const id = selReuniao.value;
  const r = await fetch('/api/reunioes/' + encodeURIComponent(id) + '/exportar-txt', { ...fetchOpts, method: 'POST', headers: apiHeaders({ 'Content-Type': 'application/json' }), body: '{}' });
  if (!r.ok) { dizerParticipantes('Falha ao exportar TXT.'); return; }
  const url = URL.createObjectURL(await r.blob());
  try {
    const link = document.createElement('a'); link.href = url; link.download = 'reuniao-' + id + '.txt';
    document.body.appendChild(link); link.click(); link.remove();
    dizerParticipantes('TXT exportado. Guarde o arquivo com cuidado.');
  } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
}

export function iniciarParticipantes() {
  if (btnParticipantes) btnParticipantes.onclick = () => abrirParticipantes(true);
  if (btnFecharPart) btnFecharPart.onclick = () => abrirParticipantes(false);
  if (selReuniao) selReuniao.addEventListener('change', carregarResultado);
  if (formCorrecao) formCorrecao.addEventListener('submit', salvarCorrecao);
  if (btnDesfazer) btnDesfazer.onclick = desfazerCorrecao;
  if (btnExportarTxt) btnExportarTxt.onclick = exportarTxt;
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawerParticipantes && !drawerParticipantes.hidden) abrirParticipantes(false);
    if (e.key !== 'Tab' || !drawerParticipantes || drawerParticipantes.hidden) return;
    const alvos = drawerParticipantes.querySelectorAll('button, select, input, textarea, a[href], [tabindex]:not([tabindex="-1"])');
    const visiveis = [...alvos].filter((el) => !el.disabled && el.offsetParent !== null);
    if (!visiveis.length) return;
    const primeiro = visiveis[0], ultimo = visiveis[visiveis.length - 1];
    if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus(); }
    else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus(); }
  });
}
