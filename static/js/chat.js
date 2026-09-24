// Conversa do assistente (SDD v1.9, T-14.B3): lista de reuniões, contexto,
// mensagens em blocos com markdown incremental, chips de intenção e composer.
// Extraído de assistente.js (histórico isolado por reunião, UX-13.F1).
import { renderMarkdown, escapeHtml } from './markdown.js';
import { INTENCOES } from './intencoes.js';
import { criarListbox } from './reunioes.js';
import { toast, icone } from './ui.js';

const $ = (id) => document.getElementById(id);
const chat = $('chat');
const input = $('input');
const sendBtn = $('send');
const stopBtn = $('stop');
const limparBtn = $('limpar');
const selTrans = $('transcricao');
const selMod = $('modelo');
const ollamaDot = $('ollama-dot');
const statusMod = $('status-modelo');
const timerEl = $('timer');
const progressBar = $('progress-bar');
const tamanhoKbEl = $('tamanho-kb');
const ctxHintEl = $('ctx-hint');
const copiarBtn = $('copiar-resposta');
const menuToggle = $('menu-toggle');
const sidebarEl = $('sidebar');
const drawerOverlay = $('drawer-overlay');
const sidebarClose = $('sidebar-close');
const buscaInput = $('busca-transcricao');
const countEl = $('transcricao-count');
const contextFile = $('context-file');
const contextKb = $('context-kb');
const contextBadge = $('context-badge');
const headerMeta = $('header-meta');
const chipsEl = $('chips');
const chipsEditar = $('chips-editar');

export const listaReunioes = selTrans ? criarListbox(selTrans) : null;

let busy = false;
let abortController = null;
let timerInterval = null;
let timerStart = 0;
let historico = [];
let transcricoesLista = [];
let transcricoesFiltradas = [];
let ultimaRespostaIA = '';
let estadosReuniao = {};
let idGeracao = 0;
let idReuniaoAberta = '';
const detalhesPorArquivo = {};
const MAX_HISTORICO_ENVIO = 20;

const API_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
function apiHeaders(extra = {}) {
  const h = Object.assign({}, extra);
  if (API_TOKEN) h['X-Transkriptor-Token'] = API_TOKEN;
  return h;
}
const fetchOpts = { credentials: 'same-origin' };

export function showToast(msg, tone = 'info') {
  toast(tone === 'error' ? 'error' : 'info', msg);
}

// ---- Reunião e contexto -----------------------------------------------------

function reuniaoAtual() { return (selTrans && selTrans.value) || ''; }

function estadoReuniao(id) {
  if (!estadosReuniao[id]) estadosReuniao[id] = { historico: [], html: null };
  return estadosReuniao[id];
}

function revisaoDaReuniao(id) {
  const item = transcricoesLista.find((t) => t.arquivo === id);
  return item ? (item.data || '') + '|' + (item.tamanho_kb ?? '') : '';
}

function trocarReuniao(novaId) {
  if (!idReuniaoAberta) idReuniaoAberta = novaId || '';
  const anterior = idReuniaoAberta;
  if (anterior) estadosReuniao[anterior] = { historico, html: chat.innerHTML };
  if (abortController) abortController.abort();
  idGeracao += 1;
  const destino = estadoReuniao(novaId || '');
  historico = destino.historico;
  idReuniaoAberta = novaId || '';
  chat.innerHTML = destino.html != null ? destino.html : '';
  if (!chat.children.length) chat.appendChild(criarEmptyState());
  ligarAcoesDasMensagens();
  ultimaRespostaIA = '';
  if (copiarBtn) copiarBtn.disabled = true;
}

function atualizarContextBar() {
  const item = transcricoesLista.find((t) => t.arquivo === selTrans.value);
  if (!item) {
    contextFile.textContent = 'Nenhuma selecionada';
    contextKb.textContent = ''; contextBadge.textContent = ''; contextBadge.className = 'context-badge';
    if (headerMeta) headerMeta.textContent = '';
    return;
  }
  contextFile.textContent = item.arquivo; contextFile.title = item.arquivo;
  contextKb.textContent = `${item.tamanho_kb} KB`;
  const tipo = item.tipo === 'diarizado' ? 'separada por vozes' : 'transcrição';
  contextBadge.textContent = item.com_sua_voz ? `${tipo} · com sua voz` : tipo;
  contextBadge.className = 'context-badge ' + (item.tipo === 'diarizado' ? 'tipo-diarizado' : 'tipo-transcricao');
  if (headerMeta) headerMeta.textContent = `${item.data} · ${item.tamanho_kb} KB`;
}

function atualizarTamanhoKb() {
  const item = transcricoesLista.find((t) => t.arquivo === selTrans.value);
  if (!item) { tamanhoKbEl.textContent = ''; if (ctxHintEl) ctxHintEl.textContent = ''; atualizarContextBar(); return; }
  tamanhoKbEl.textContent = '';
  tamanhoKbEl.append(`${item.tamanho_kb} KB`);
  if (item.com_sua_voz) {
    tamanhoKbEl.append(' · ');
    const b = document.createElement('span'); b.className = 'badge-voce'; b.textContent = 'com sua voz';
    tamanhoKbEl.appendChild(b);
  }
  if (ctxHintEl) ctxHintEl.textContent = item.tamanho_kb > 78 ? 'Transcrição longa: a resposta será consolidada em blocos.' : '';
  atualizarContextBar();
}

async function carregarDetalhesSelecionado() {
  // UX-14.B2: preview/com_sua_voz exigem abrir o texto; só para a reunião ativa e uma vez.
  const id = selTrans.value;
  if (!id || detalhesPorArquivo[id]) return;
  detalhesPorArquivo[id] = { pendente: true };
  try {
    const r = await fetch('/api/transcricoes?detalhes=1&arquivo=' + encodeURIComponent(id), { ...fetchOpts, headers: apiHeaders() });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const lista = await r.json();
    const det = Array.isArray(lista) && lista[0] ? lista[0] : {};
    detalhesPorArquivo[id] = det;
    const alvo = transcricoesLista.find((t) => t.arquivo === id);
    if (alvo) Object.assign(alvo, { com_sua_voz: det.com_sua_voz === true, preview: det.preview || '' });
    if (selTrans.value === id) atualizarTamanhoKb();
  } catch (_) {
    delete detalhesPorArquivo[id];
  }
}

function buildModelOptions(modelos) {
  selMod.replaceChildren();
  if (!modelos.length) {
    const opt = document.createElement('option'); opt.value = ''; opt.textContent = 'Ollama offline';
    selMod.appendChild(opt);
    statusMod.textContent = 'Ollama offline';
    ollamaDot.classList.add('off');
    document.dispatchEvent(new CustomEvent('tk-ollama', { detail: { online: false } }));
    return;
  }
  for (const nome of modelos) { const opt = document.createElement('option'); opt.value = nome; opt.textContent = nome; selMod.appendChild(opt); }
  statusMod.textContent = modelos[0];
  ollamaDot.classList.remove('off');
  document.dispatchEvent(new CustomEvent('tk-ollama', { detail: { online: true } }));
}

function buildSelectOptions(items) {
  // com_sua_voz: preenchido sob demanda ao selecionar (detalhes=1)
  transcricoesLista = items;
  transcricoesFiltradas = items.slice();
  renderTranscricoesSelect(transcricoesFiltradas);
}

function renderTranscricoesSelect(items) {
  const prev = selTrans.value;
  if (!listaReunioes) return;
  if (!items.length) {
    listaReunioes.estado(transcricoesLista.length ? 'sem-resultado' : 'vazio');
    if (!transcricoesLista.length) tamanhoKbEl.textContent = '';
    if (countEl) countEl.textContent = transcricoesLista.length ? `0 de ${transcricoesLista.length}` : '';
    atualizarContextBar();
    return;
  }
  listaReunioes.render(items);
  if (prev && items.some(x => x.arquivo === prev)) selTrans.value = prev;
  if (countEl) countEl.textContent = items.length === transcricoesLista.length ? `${items.length}` : `${items.length} de ${transcricoesLista.length}`;
  atualizarTamanhoKb();
}

function filtrarTranscricoes() {
  const q = (buscaInput.value || '').trim().toLowerCase();
  transcricoesFiltradas = !q ? transcricoesLista.slice() : transcricoesLista.filter((t) => (t.arquivo + ' ' + t.data).toLowerCase().includes(q));
  renderTranscricoesSelect(transcricoesFiltradas);
}

export async function loadList() {
  if (listaReunioes) listaReunioes.estado('carregando');
  try {
    const r = await fetch('/api/transcricoes', { ...fetchOpts, headers: apiHeaders() });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    buildSelectOptions(d);
    const desejada = new URLSearchParams(window.location.search).get('reuniao');
    const alvo = desejada && d.find((t) => t.arquivo === desejada || t.arquivo.replace(/\.(txt|tkpt)$/, '') === desejada);
    if (alvo && listaReunioes) selTrans.value = alvo.arquivo;
  } catch (e) {
    if (listaReunioes) listaReunioes.estado('erro');
    if (countEl) countEl.textContent = '';
  }
  await carregarModelos();
}

export async function carregarModelos() {
  try {
    const r = await fetch('/api/modelos', { ...fetchOpts, headers: apiHeaders() });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    buildModelOptions(await r.json());
  } catch (e) { buildModelOptions([]); }
}

// ---- Mensagens --------------------------------------------------------------

function criarEmptyState() {
  const empty = document.createElement('div');
  empty.className = 'empty-state tk-empty'; empty.id = 'empty'; empty.setAttribute('role', 'status');
  empty.innerHTML =
    '<div class="empty-icon" aria-hidden="true"></div>' +
    '<h2 class="empty-title tk-empty__titulo">Pergunte sobre uma reunião</h2>' +
    '<ol class="empty-passos">' +
    '<li><span class="empty-num">1</span>Escolha uma reunião na lista ao lado.</li>' +
    '<li><span class="empty-num">2</span>Use uma ação rápida ou escreva sua pergunta.</li>' +
    '<li><span class="empty-num">3</span>A resposta é gerada localmente pelo Ollama. Nada sai da sua máquina.</li>' +
    '</ol>' +
    '<div class="empty-tips"><span class="tip"><kbd>Enter</kbd> enviar</span><span class="tip"><kbd>Shift</kbd>+<kbd>Enter</kbd> nova linha</span><span class="tip"><kbd>Esc</kbd> cancelar</span></div>';
  empty.querySelector('.empty-icon').appendChild(icone('sparkles', 'tk-icon tk-icon--lg'));
  return empty;
}

function ensureEmptyRemoved() { const el = $('empty'); if (el) el.remove(); }

function horaAgora() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function botaoAcao(rotulo, nomeIcone, classe) {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'msg-copy tk-btn tk-btn--quiet tk-btn--sm ' + (classe || '');
  b.appendChild(icone(nomeIcone, 'tk-icon tk-icon--sm'));
  b.appendChild(document.createTextNode(' ' + rotulo));
  return b;
}

async function copiarTexto(texto, botao) {
  try {
    await navigator.clipboard.writeText(texto);
    const anterior = botao.textContent; botao.textContent = 'Copiado!';
    setTimeout(() => { botao.textContent = ''; botao.appendChild(icone('copy', 'tk-icon tk-icon--sm')); botao.appendChild(document.createTextNode(' Copiar')); }, 1400);
    return true;
  } catch (_) {
    botao.textContent = 'Erro ao copiar';
    showToast('Não foi possível copiar. Selecione o texto e use Ctrl+C.', 'error');
    return false;
  }
}

function ligarAcoesDasMensagens() {
  chat.querySelectorAll('.msg-row').forEach((row) => {
    if (row._tkLigado) return;
    row._tkLigado = true;
    const texto = row.dataset.texto || '';
    const copiar = row.querySelector('[data-acao="copiar"]');
    if (copiar) copiar.addEventListener('click', () => copiarTexto(texto, copiar));
    const reenviar = row.querySelector('[data-acao="reenviar"]');
    if (reenviar) reenviar.addEventListener('click', () => pergunta(texto));
  });
}

function addMsg(role, text, opts = {}) {
  ensureEmptyRemoved();
  const row = document.createElement('article');
  row.className = 'msg-row ' + role;
  row.dataset.texto = text;
  const cab = document.createElement('div');
  cab.className = 'msg-cab';
  const av = document.createElement('span'); av.className = 'avatar ' + role; av.setAttribute('aria-hidden', 'true');
  if (role === 'ai') av.appendChild(icone('sparkles', 'tk-icon tk-icon--sm')); else av.textContent = 'V';
  const autor = document.createElement('span'); autor.className = 'msg-autor'; autor.textContent = role === 'ai' ? 'Assistente' : 'Você';
  const hora = document.createElement('span'); hora.className = 'msg-hora tk-num'; hora.textContent = horaAgora();
  cab.append(av, autor, hora);
  const wrap = document.createElement('div'); wrap.className = 'msg-body';
  const bub = document.createElement('div'); bub.className = 'bubble';
  if (role === 'ai' && opts.renderMarkdown !== false) bub.innerHTML = renderMarkdown(text); else bub.textContent = text;
  wrap.appendChild(bub);
  const meta = document.createElement('div'); meta.className = 'msg-meta';
  if (role === 'ai' && text.trim()) { const c = botaoAcao('Copiar', 'copy'); c.dataset.acao = 'copiar'; meta.appendChild(c); }
  if (role === 'user') { const r = botaoAcao('Reenviar', 'refresh'); r.dataset.acao = 'reenviar'; meta.appendChild(r); }
  if (meta.children.length) wrap.appendChild(meta);
  row.append(cab, wrap);
  chat.appendChild(row);
  ligarAcoesDasMensagens();
  chat.scrollTop = chat.scrollHeight;
  return bub;
}

function addTyping() {
  ensureEmptyRemoved();
  const row = document.createElement('article');
  row.className = 'msg-row ai'; row.id = 'typing-row';
  const cab = document.createElement('div'); cab.className = 'msg-cab';
  const av = document.createElement('span'); av.className = 'avatar ai'; av.setAttribute('aria-hidden', 'true'); av.appendChild(icone('sparkles', 'tk-icon tk-icon--sm'));
  const autor = document.createElement('span'); autor.className = 'msg-autor'; autor.textContent = 'Assistente';
  cab.append(av, autor);
  const wrap = document.createElement('div'); wrap.className = 'msg-body';
  const bub = document.createElement('div'); bub.className = 'bubble';
  bub.innerHTML = '<div class="typing" aria-label="Gerando resposta"><span></span><span></span><span></span></div>';
  wrap.appendChild(bub);
  row.append(cab, wrap);
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
  return bub;
}

function iniciarTimer() {
  timerStart = Date.now();
  timerEl.classList.remove('is-hidden', 'longo');
  timerEl.textContent = 'Processando… 0s';
  timerInterval = setInterval(() => {
    const seg = Math.floor((Date.now() - timerStart) / 1000);
    if (seg >= 15) { timerEl.classList.add('longo'); timerEl.textContent = 'O modelo está pensando… (' + seg + 's)'; }
    else timerEl.textContent = `Processando… ${seg}s`;
  }, 1000);
}

function pararTimer() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  timerEl.classList.add('is-hidden'); timerEl.classList.remove('longo');
}

function mostrarBotoes(ocupado) {
  sendBtn.classList.toggle('is-hidden', ocupado);
  stopBtn.classList.toggle('is-hidden', !ocupado);
  progressBar.classList.toggle('visible', ocupado);
  progressBar.setAttribute('aria-hidden', ocupado ? 'false' : 'true');
  if (ocupado) input.setAttribute('disabled', ''); else input.removeAttribute('disabled');
  if (chipsEl) chipsEl.querySelectorAll('.tk-chip').forEach((c) => { c.disabled = ocupado; });
}

function mostrarToastInline(msg) {
  ensureEmptyRemoved();
  const row = document.createElement('article'); row.className = 'msg-row ai';
  const wrap = document.createElement('div'); wrap.className = 'msg-body';
  const el = document.createElement('div'); el.className = 'toast-inline'; el.setAttribute('role', 'status'); el.textContent = msg;
  wrap.appendChild(el); row.appendChild(wrap);
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
}

export async function pergunta(prompt) {
  const transc = selTrans.value;
  const modelo = selMod.value;
  if (!transc) { mostrarToastInline('Selecione uma reunião primeiro.'); showToast('Selecione uma reunião na lista à esquerda.', 'error'); return; }
  if (!modelo || busy) return;
  if (!idReuniaoAberta && transc) idReuniaoAberta = transc;
  if (input && input.value === prompt) input.value = '';
  busy = true; mostrarBotoes(true);
  const minhaGeracao = ++idGeracao;
  const geracaoId = 'g' + Date.now().toString(36) + minhaGeracao.toString(36);
  const historicoEnvio = historico.slice(-MAX_HISTORICO_ENVIO);
  const revisao = revisaoDaReuniao(transc);
  addMsg('user', prompt, { renderMarkdown: false });
  const typingBubble = addTyping();
  iniciarTimer();
  let firstToken = true;
  let accumulated = '';
  let agendado = null;
  abortController = new AbortController();
  const desenhar = (alvo) => {
    if (agendado) return;
    agendado = requestAnimationFrame(() => { agendado = null; alvo.innerHTML = renderMarkdown(accumulated); chat.scrollTop = chat.scrollHeight; });
  };
  try {
    const res = await fetch('/api/chat', { ...fetchOpts, method: 'POST', headers: apiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ modelo, transcricao: transc, pergunta: prompt, historico: historicoEnvio, meeting_id: transc, transcript_revision: revisao, generation_id: geracaoId }),
      signal: abortController.signal });
    if (minhaGeracao !== idGeracao || selTrans.value !== transc) return;
    if (!res.ok) {
      let msg = `Erro ${res.status}`;
      try { const j = await res.json(); if (j.erro) msg = j.erro; } catch (_) { /* sem corpo JSON */ }
      throw new Error(msg);
    }
    const reader = res.body.getReader(); const dec = new TextDecoder(); let txt = '';
    let alvo = typingBubble;
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      if (minhaGeracao !== idGeracao || selTrans.value !== transc) return;
      txt += dec.decode(value, { stream: true });
      if (firstToken) { firstToken = false; pararTimer(); const row = $('typing-row'); if (row) alvo = row.querySelector('.bubble'); }
      accumulated = txt;
      desenhar(alvo);
    }
    if (agendado) { cancelAnimationFrame(agendado); agendado = null; }
    const row = $('typing-row');
    if (row) {
      const b = row.querySelector('.bubble');
      if (firstToken || !accumulated.trim()) { b.textContent = '(sem resposta)'; pararTimer(); }
      else {
        b.innerHTML = renderMarkdown(accumulated);
        row.dataset.texto = accumulated;
        const meta = document.createElement('div'); meta.className = 'msg-meta';
        const c = botaoAcao('Copiar', 'copy'); c.dataset.acao = 'copiar'; meta.appendChild(c);
        row.querySelector('.msg-body').appendChild(meta);
        row._tkLigado = false; ligarAcoesDasMensagens();
        ultimaRespostaIA = accumulated;
        copiarBtn.disabled = false;
      }
      row.id = '';
    } else if (accumulated.trim()) { ultimaRespostaIA = accumulated; copiarBtn.disabled = false; }
    if (minhaGeracao !== idGeracao || selTrans.value !== transc) return;
    if (accumulated.trim()) { historico.push({ role: 'user', content: prompt }); historico.push({ role: 'assistant', content: accumulated }); }
  } catch (e) {
    pararTimer();
    const row = $('typing-row');
    const target = (row && row.querySelector('.bubble')) || typingBubble;
    if (target) target.textContent = e.name === 'AbortError' ? '(cancelado)' : 'Não foi possível responder: ' + e.message + '. Tente de novo ou verifique o Ollama.';
    if (row) row.id = '';
  } finally {
    busy = false; mostrarBotoes(false); abortController = null; pararTimer();
  }
}

function abrirDrawer(aberto) {
  sidebarEl.classList.toggle('drawer-open', aberto);
  drawerOverlay.classList.toggle('open', aberto);
  menuToggle.setAttribute('aria-expanded', aberto ? 'true' : 'false');
  drawerOverlay.setAttribute('aria-hidden', aberto ? 'false' : 'true');
  if (aberto && buscaInput) buscaInput.focus();
}

function copiarUltimaResposta() {
  if (!ultimaRespostaIA) return;
  navigator.clipboard.writeText(ultimaRespostaIA).then(() => {
    const prev = copiarBtn.textContent; copiarBtn.textContent = 'Copiado!';
    setTimeout(() => { copiarBtn.textContent = prev; }, 1500);
  }).catch(() => {
    copiarBtn.textContent = 'Erro ao copiar';
    setTimeout(() => { copiarBtn.textContent = 'Copiar última'; }, 1500);
  });
}

function limparConversa() {
  idGeracao += 1;
  if (idReuniaoAberta) estadosReuniao[idReuniaoAberta] = { historico: [], html: null };
  historico = []; ultimaRespostaIA = ''; copiarBtn.disabled = true;
  chat.innerHTML = '';
  chat.appendChild(criarEmptyState());
  showToast('Conversa limpa.');
  input.focus();
}

// ---- Chips de intenção --------------------------------------------------------

function montarChips() {
  if (!chipsEl) return;
  chipsEl.innerHTML = '';
  for (const it of INTENCOES) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'tk-chip' + (it.primario ? ' is-primary' : ''); b.dataset.intent = it.id;
    b.appendChild(icone(it.icone, 'tk-icon'));
    b.appendChild(document.createTextNode(it.rotulo));
    b.title = it.rotulo;
    b.addEventListener('click', () => {
      if (chipsEditar && chipsEditar.getAttribute('aria-pressed') === 'true') {
        input.value = it.prompt; autoAltura(); input.focus();
        showToast('Prompt carregado. Edite se quiser e pressione Enter.');
        return;
      }
      pergunta(it.prompt);
    });
    chipsEl.appendChild(b);
  }
  if (chipsEditar) chipsEditar.addEventListener('click', () => {
    const ativo = chipsEditar.getAttribute('aria-pressed') === 'true';
    chipsEditar.setAttribute('aria-pressed', ativo ? 'false' : 'true');
    chipsEditar.classList.toggle('is-active', !ativo);
  });
}

function navegarChips(e) {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  const alvo = e.target;
  if (alvo && /^(TEXTAREA|INPUT|SELECT)$/i.test(alvo.tagName)) return;
  const cards = [...document.querySelectorAll('.tk-chip[data-intent]')];
  if (!cards.length) return;
  const idx = cards.indexOf(document.activeElement);
  if (idx === -1) return;
  const frente = e.key === 'ArrowDown' || e.key === 'ArrowRight';
  if (frente && idx < cards.length - 1) cards[idx + 1].focus();
  if (!frente && idx > 0) cards[idx - 1].focus();
  e.preventDefault();
}

function autoAltura() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 160) + 'px'; }

// ---- Ligações -------------------------------------------------------------------

export function iniciarChat() {
  sendBtn.onclick = () => { const t = input.value.trim(); if (!t) return; pergunta(t); };
  stopBtn.onclick = () => { if (abortController) abortController.abort(); };
  limparBtn.onclick = limparConversa;
  copiarBtn.onclick = copiarUltimaResposta;
  if (menuToggle) menuToggle.onclick = () => abrirDrawer(!sidebarEl.classList.contains('drawer-open'));
  if (sidebarClose) sidebarClose.onclick = () => abrirDrawer(false);
  if (drawerOverlay) drawerOverlay.onclick = () => abrirDrawer(false);
  selTrans.addEventListener('change', atualizarTamanhoKb);
  selTrans.addEventListener('change', () => trocarReuniao(selTrans.value));
  selTrans.addEventListener('change', carregarDetalhesSelecionado);
  selTrans.addEventListener('tk-recarregar', loadList);
  selMod.addEventListener('change', () => { statusMod.textContent = selMod.value || '—'; });
  if (buscaInput) buscaInput.addEventListener('input', filtrarTranscricoes);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendBtn.click(); }
    if (e.key === 'Escape' && busy && abortController) { e.preventDefault(); abortController.abort(); }
    if (e.key === 'Escape' && !busy && sidebarEl.classList.contains('drawer-open')) abrirDrawer(false);
  });
  input.addEventListener('input', autoAltura);
  document.addEventListener('keydown', (e) => {
    // Esc cancela a geração de qualquer lugar: o campo fica desabilitado enquanto gera.
    if (e.key === 'Escape' && busy && abortController) { e.preventDefault(); abortController.abort(); return; }
    if (e.key === 'Escape' && sidebarEl.classList.contains('drawer-open')) abrirDrawer(false);
    navegarChips(e);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); if (buscaInput) { abrirDrawer(true); buscaInput.focus(); buscaInput.select(); } }
  });
  montarChips();
  if (!chat.children.length) chat.appendChild(criarEmptyState());
  input.focus();
  loadList();
}
