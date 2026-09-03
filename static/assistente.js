const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const stopBtn = document.getElementById('stop');
const limparBtn = document.getElementById('limpar');
const selTrans = document.getElementById('transcricao');
const selMod = document.getElementById('modelo');
const emptyEl = document.getElementById('empty');
const ollamaDot = document.getElementById('ollama-dot');
const statusMod = document.getElementById('status-modelo');
const timerEl = document.getElementById('timer');
const progressBar = document.getElementById('progress-bar');
const tamanhoKbEl = document.getElementById('tamanho-kb');
const ctxHintEl = document.getElementById('ctx-hint');
const copiarBtn = document.getElementById('copiar-resposta');
const menuToggle = document.getElementById('menu-toggle');
const sidebarEl = document.getElementById('sidebar');
const drawerOverlay = document.getElementById('drawer-overlay');
const sidebarClose = document.getElementById('sidebar-close');
const buscaInput = document.getElementById('busca-transcricao');
const countEl = document.getElementById('transcricao-count');
const contextBar = document.getElementById('context-bar');
const contextFile = document.getElementById('context-file');
const contextKb = document.getElementById('context-kb');
const contextBadge = document.getElementById('context-badge');
const headerMeta = document.getElementById('header-meta');
const toastRegion = document.getElementById('toast-region');
const inputWrap = document.getElementById('input-wrap');

let busy = false;
let abortController = null;
let timerInterval = null;
let timerStart = 0;
let historico = [];
let transcricoesLista = [];
let transcricoesFiltradas = [];
let ultimaRespostaIA = '';
let ultimaRespostaEl = null;

const API_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
function apiHeaders(extra = {}) {
  const h = Object.assign({}, extra);
  if (API_TOKEN) h['X-Transkriptor-Token'] = API_TOKEN;
  return h;
}
const fetchOpts = { credentials: 'same-origin' };

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function renderMarkdown(text) {
  // Safe minimal markdown: headings, bold, code, lists, links, paragraphs.
  let html = escapeHtml(text);
  // Code blocks ``` ... ```
  html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code}</code></pre>`);
  // Inline code `...`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold **...** and __...__
  html = html.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  // Autolink http(s)
  html = html.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  // Unordered lists: lines starting with - or * or •
  // Simple paragraph handling
  const lines = html.split('\n');
  let out = '';
  let inUl = false;
  let inOl = false;
  function closeLists() {
    if (inUl) { out += '</ul>'; inUl = false; }
    if (inOl) { out += '</ol>'; inOl = false; }
  }
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const t = raw.trim();
    if (!t) { closeLists(); out += ''; continue; }
    // Heading ## or ### or #
    const hm = t.match(/^(#{1,3})\s+(.*)$/);
    if (hm) {
      closeLists();
      const lvl = hm[1].length;
      out += `<h${lvl+2}>${hm[2]}</h${lvl+2}>`;
      continue;
    }
    // Ordered list 1. 2.
    if (/^\d+\.\s+/.test(t)) {
      if (inUl) { out += '</ul>'; inUl = false; }
      if (!inOl) { out += '<ol>'; inOl = true; }
      out += `<li>${t.replace(/^\d+\.\s+/, '')}</li>`;
      continue;
    }
    // Unordered
    if (/^[-*•]\s+/.test(t)) {
      if (inOl) { out += '</ol>'; inOl = false; }
      if (!inUl) { out += '<ul>'; inUl = true; }
      out += `<li>${t.replace(/^[-*•]\s+/, '')}</li>`;
      continue;
    }
    closeLists();
    // paragraphs already handled via pre-wrap but we wrap
    out += `<p>${raw}</p>`;
  }
  closeLists();
  // If no block tags were produced, fallback to paragraphs via double newline
  if (!/<(p|ul|ol|pre|h[3-5])>/.test(out)) {
    out = html.split(/\n{2,}/).map(p => `<p>${p.replace(/\n/g,'<br>')}</p>`).join('');
  }
  // Restore pre/code inner br
  out = out.replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/g, (m, c) => `<pre><code>${c.replace(/<br>/g,'\n')}</code></pre>`);
  return out;
}

function showToast(msg, tone = 'info') {
  if (!toastRegion) return;
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  if (tone === 'error') el.style.borderColor = 'rgba(239,68,68,0.32)';
  toastRegion.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateY(4px)'; el.style.transition = 'opacity 0.22s, transform 0.22s'; }, 2600);
  setTimeout(() => el.remove(), 3000);
}

function atualizarContextBar() {
  const item = transcricoesLista.find(t => t.arquivo === selTrans.value);
  if (!item) {
    contextFile.textContent = 'Nenhuma selecionada';
    contextKb.textContent = '';
    contextBadge.textContent = '';
    contextBadge.className = 'context-badge';
    if (headerMeta) headerMeta.textContent = '';
    return;
  }
  contextFile.textContent = item.arquivo;
  contextFile.title = item.arquivo;
  contextKb.textContent = `${item.tamanho_kb} KB`;
  const tipo = item.tipo === 'diarizado' ? 'diarizado' : 'transcrição';
  contextBadge.textContent = item.com_sua_voz ? `${tipo} · com sua voz` : tipo;
  contextBadge.className = 'context-badge ' + (item.tipo === 'diarizado' ? 'tipo-diarizado' : 'tipo-transcricao');
  if (headerMeta) headerMeta.textContent = `${item.data} · ${item.tamanho_kb} KB`;
}

function atualizarTamanhoKb() {
  const item = transcricoesLista.find(t => t.arquivo === selTrans.value);
  if (!item) {
    tamanhoKbEl.textContent = '';
    if (ctxHintEl) ctxHintEl.textContent = '';
    atualizarContextBar();
    return;
  }
  let meta = `${item.tamanho_kb} KB`;
  if (item.com_sua_voz) meta += ' · com sua voz';
  tamanhoKbEl.innerHTML = item.com_sua_voz
    ? `${item.tamanho_kb} KB · <span class="badge-voce">com sua voz</span>`
    : meta;
  // Context length hint
  if (ctxHintEl) {
    if (item.tamanho_kb > 78) {
      ctxHintEl.textContent = 'Transcrição longa: resposta será consolidada em blocos.';
    } else if (item.tamanho_kb > 45) {
      ctxHintEl.textContent = '';
    } else {
      ctxHintEl.textContent = '';
    }
  }
  atualizarContextBar();
}

function buildModelOptions(modelos) {
  selMod.replaceChildren();
  if (!modelos.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Ollama offline';
    selMod.appendChild(opt);
    statusMod.textContent = 'Ollama offline — instale um modelo';
    ollamaDot.classList.add('off');
    showToast('Ollama offline. Verifique se o Ollama está rodando.', 'error');
    return;
  }
  for (const nome of modelos) {
    const opt = document.createElement('option');
    opt.value = nome;
    opt.textContent = nome;
    selMod.appendChild(opt);
  }
  statusMod.textContent = modelos[0];
  ollamaDot.classList.remove('off');
}

function buildSelectOptions(items) {
  // com_sua_voz: usado em renderTranscricoesSelect para marcar "com sua voz" no sufixo
  transcricoesLista = items;
  transcricoesFiltradas = items.slice();
  renderTranscricoesSelect(transcricoesFiltradas);
}

function renderTranscricoesSelect(items) {
  const prev = selTrans.value;
  selTrans.replaceChildren();
  if (!items.length) {
    const opt = document.createElement('option');
    opt.value = '';
    const hasFilter = buscaInput && buscaInput.value.trim();
    opt.textContent = transcricoesLista.length ? '(nenhum resultado para o filtro)' : '(nenhuma transcrição)';
    selTrans.appendChild(opt);
    tamanhoKbEl.textContent = '';
    if (countEl) countEl.textContent = transcricoesLista.length ? `0 de ${transcricoesLista.length}` : '';
    atualizarContextBar();
    return;
  }
  for (const t of items) {
    const opt = document.createElement('option');
    opt.value = t.arquivo;
    let sufixo = t.tipo === 'diarizado' ? ' [vozes]' : ' [texto]';
    if (t.com_sua_voz) sufixo += ' · com sua voz';
    opt.textContent = `${t.data} — ${t.preview || '(vazio)'}${sufixo}`;
    selTrans.appendChild(opt);
  }
  // Restore selection if still present
  if (prev && items.some(x => x.arquivo === prev)) selTrans.value = prev;
  if (countEl) countEl.textContent = items.length === transcricoesLista.length ? `${items.length}` : `${items.length} de ${transcricoesLista.length}`;
  atualizarTamanhoKb();
}

function filtrarTranscricoes() {
  const q = (buscaInput.value || '').trim().toLowerCase();
  if (!q) {
    transcricoesFiltradas = transcricoesLista.slice();
  } else {
    transcricoesFiltradas = transcricoesLista.filter(t =>
      (t.arquivo + ' ' + (t.preview||'') + ' ' + t.data).toLowerCase().includes(q)
    );
  }
  renderTranscricoesSelect(transcricoesFiltradas);
}

async function loadList() {
  try {
    const r = await fetch('/api/transcricoes', {...fetchOpts, headers: apiHeaders()}); const d = await r.json();
    buildSelectOptions(d);
  } catch(e) {
    selTrans.replaceChildren();
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'erro ao carregar';
    selTrans.appendChild(opt);
    if (countEl) countEl.textContent = '';
    showToast('Erro ao carregar transcrições.', 'error');
  }
  try {
    const r = await fetch('/api/modelos', {...fetchOpts, headers: apiHeaders()}); const d = await r.json();
    buildModelOptions(d);
  } catch(e) { buildModelOptions([]); }
}
selMod.addEventListener('change', ()=>{ statusMod.textContent = selMod.value || '—'; });

function ensureEmptyRemoved() {
  const el = document.getElementById('empty');
  if (el) el.remove();
}

function addMsg(role, text, opts = {}) {
  ensureEmptyRemoved();
  const row = document.createElement('div');
  row.className = 'msg-row '+role;
  const av = document.createElement('div');
  av.className = 'avatar '+role;
  av.setAttribute('aria-hidden', 'true');
  av.innerHTML = role==='ai'
    ? '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>'
    : 'Você';
  const bub = document.createElement('div');
  bub.className = 'bubble';
  if (role === 'ai' && opts.renderMarkdown !== false) {
    bub.innerHTML = renderMarkdown(text);
  } else {
    bub.textContent = text;
  }
  row.appendChild(av); row.appendChild(bub);
  // Per-message copy for AI
  if (role === 'ai' && text.trim()) {
    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'msg-copy';
    copy.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="10" height="10" rx="2"/><path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/></svg> Copiar';
    copy.addEventListener('click', () => {
      navigator.clipboard.writeText(text).then(() => {
        copy.textContent = 'Copiado!';
        setTimeout(() => copy.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="10" height="10" rx="2"/><path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/></svg> Copiar', 1400);
      });
    });
    meta.appendChild(copy);
    const wrap = document.createElement('div');
    wrap.style.display = 'flex';
    wrap.style.flexDirection = 'column';
    wrap.style.gap = '6px';
    wrap.style.minWidth = '0';
    wrap.style.flex = '1';
    wrap.appendChild(bub);
    wrap.appendChild(meta);
    row.appendChild(wrap);
    // remove bub already appended: need correct structure - rebuild
    row.replaceChildren(av, wrap);
    chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
    return bub;
  }
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
  return bub;
}

function addTyping() {
  ensureEmptyRemoved();
  const row = document.createElement('div');
  row.className = 'msg-row ai'; row.id = 'typing-row';
  const av = document.createElement('div'); av.className = 'avatar ai';
  av.setAttribute('aria-hidden', 'true');
  av.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="1.7"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>';
  const bub = document.createElement('div'); bub.className = 'bubble';
  bub.innerHTML = '<div class="typing" aria-label="Gerando resposta"><span></span><span></span><span></span></div>';
  const wrap = document.createElement('div');
  wrap.style.display = 'flex';
  wrap.style.flexDirection = 'column';
  wrap.style.gap = '4px';
  wrap.style.flex = '1';
  wrap.appendChild(bub);
  row.appendChild(av); row.appendChild(wrap);
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
  return bub;
}

function iniciarTimer() {
  timerStart = Date.now();
  timerEl.style.display = 'block';
  timerEl.classList.remove('longo');
  timerEl.textContent = 'Processando… 0s';
  timerInterval = setInterval(() => {
    const seg = Math.floor((Date.now() - timerStart) / 1000);
    if (seg >= 15) {
      timerEl.classList.add('longo');
      timerEl.textContent = 'O modelo está pensando… (' + seg + 's)';
    } else {
      timerEl.textContent = `Processando… ${seg}s`;
    }
  }, 1000);
}

function pararTimer() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  timerEl.style.display = 'none';
  timerEl.classList.remove('longo');
}

function mostrarBotoes(ocupado) {
  sendBtn.style.display = ocupado ? 'none' : 'flex';
  stopBtn.style.display = ocupado ? 'flex' : 'none';
  progressBar.classList.toggle('visible', ocupado);
  progressBar.setAttribute('aria-hidden', ocupado ? 'false' : 'true');
  if (ocupado) input.setAttribute('disabled','');
  else input.removeAttribute('disabled');
}

async function pergunta(prompt) {
  const transc = selTrans.value;
  const modelo = selMod.value;
  if (!transc) { mostrarToastInline('Selecione uma transcrição primeiro.'); showToast('Selecione uma transcrição na lista à esquerda.', 'error'); return; }
  if (!modelo || busy) return;
  busy = true; mostrarBotoes(true);
  addMsg('user', prompt, { renderMarkdown: false });
  const typingBubble = addTyping();
  iniciarTimer();
  let firstToken = true;
  let accumulated = '';
  abortController = new AbortController();
  try {
    const res = await fetch('/api/chat', {...fetchOpts, method:'POST', headers:apiHeaders({'Content-Type':'application/json'}),
      body: JSON.stringify({modelo, transcricao:transc, pergunta:prompt, historico}),
      signal: abortController.signal});
    if (!res.ok) {
      let msg = `Erro ${res.status}`;
      try { const j = await res.json(); if (j.erro) msg = j.erro; } catch(_){}
      throw new Error(msg);
    }
    const reader = res.body.getReader(); const dec = new TextDecoder(); let txt='';
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      txt += dec.decode(value, {stream:true});
      if (firstToken) {
        // Replace typing bubble with real bubble content
        const row = document.getElementById('typing-row');
        if (row) {
          const b = row.querySelector('.bubble');
          b.innerHTML = '';
          // keep reference
          firstToken = false;
          pararTimer();
          // swap to render accumulating
          typingBubble._real = b;
        } else {
          firstToken = false;
          pararTimer();
        }
        accumulated = txt;
      } else {
        accumulated = txt;
      }
      const target = typingBubble._real || typingBubble;
      // Stream update: show as plain text until complete, then markdown
      target.textContent = accumulated;
      chat.scrollTop = chat.scrollHeight;
    }
    const row = document.getElementById('typing-row');
    if (row) {
      const b = typingBubble._real || typingBubble;
      if (firstToken) {
        b.textContent = '(sem resposta)';
        pararTimer();
      } else if (!accumulated.trim()) {
        b.textContent = '(sem resposta)';
      } else {
        b.innerHTML = renderMarkdown(accumulated);
        // Add copy button to this AI message
        const wrap = b.parentElement;
        if (wrap) {
          const meta = document.createElement('div');
          meta.className = 'msg-meta';
          const copy = document.createElement('button');
          copy.type = 'button';
          copy.className = 'msg-copy';
          copy.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="10" height="10" rx="2"/><path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/></svg> Copiar';
          const fullText = accumulated;
          copy.addEventListener('click', () => {
            navigator.clipboard.writeText(fullText).then(() => {
              copy.textContent = 'Copiado!';
              setTimeout(() => copy.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="10" height="10" rx="2"/><path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/></svg> Copiar', 1400);
            });
          });
          meta.appendChild(copy);
          wrap.appendChild(meta);
        }
        ultimaRespostaIA = accumulated;
        ultimaRespostaEl = b;
        copiarBtn.disabled = false;
      }
      row.id = '';
    } else if (accumulated.trim()) {
      ultimaRespostaIA = accumulated;
      copiarBtn.disabled = false;
    }
    if (accumulated.trim()) {
      historico.push({role:'user', content:prompt});
      historico.push({role:'assistant', content:accumulated});
    }
  } catch(e) {
    pararTimer();
    const row = document.getElementById('typing-row');
    const target = (row && row.querySelector('.bubble')) || typingBubble;
    if (target) {
      if (e.name === 'AbortError') { target.textContent = '(cancelado)'; }
      else { target.textContent = 'Erro: '+e.message; }
    }
    if (row) row.id = '';
  } finally {
    busy = false; mostrarBotoes(false); abortController = null; pararTimer();
  }
}

function mostrarToastInline(msg) {
  ensureEmptyRemoved();
  const el = document.createElement('div');
  el.className = 'toast-inline';
  el.setAttribute('role','status');
  el.textContent = msg;
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  const av = document.createElement('div'); av.className = 'avatar ai'; av.setAttribute('aria-hidden','true');
  av.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="1.7"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/></svg>';
  const wrap = document.createElement('div'); wrap.style.flex = '1'; wrap.appendChild(el);
  row.appendChild(av); row.appendChild(wrap);
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
}

function abrirDrawer(aberto) {
  sidebarEl.classList.toggle('drawer-open', aberto);
  drawerOverlay.classList.toggle('open', aberto);
  menuToggle.setAttribute('aria-expanded', aberto ? 'true' : 'false');
  drawerOverlay.setAttribute('aria-hidden', aberto ? 'false' : 'true');
  if (aberto) buscaInput && buscaInput.focus();
}

function copiarUltimaResposta() {
  if (!ultimaRespostaIA) return;
  navigator.clipboard.writeText(ultimaRespostaIA).then(() => {
    const prev = copiarBtn.textContent;
    copiarBtn.textContent = 'Copiado!';
    setTimeout(() => { copiarBtn.textContent = prev; }, 1500);
  }).catch(() => {
    copiarBtn.textContent = 'Erro ao copiar';
    setTimeout(() => { copiarBtn.textContent = 'Copiar resposta'; }, 1500);
  });
}

function navegarActionCards(e) {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
  const alvo = e.target;
  if (alvo && /^(TEXTAREA|INPUT|SELECT)$/i.test(alvo.tagName)) return;
  const cards = [...document.querySelectorAll('.action-card')];
  if (!cards.length) return;
  const idx = cards.indexOf(document.activeElement);
  if (idx === -1) return;
  if (e.key === 'ArrowDown' && idx < cards.length - 1) cards[idx + 1].focus();
  if (e.key === 'ArrowUp' && idx > 0) cards[idx - 1].focus();
  e.preventDefault();
}

function limparConversa() {
  historico = [];
  ultimaRespostaIA = '';
  ultimaRespostaEl = null;
  copiarBtn.disabled = true;
  chat.innerHTML = '';
  const empty = document.createElement('div');
  empty.className = 'empty-state'; empty.id = 'empty'; empty.setAttribute('role', 'status');
  empty.innerHTML = '<div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="#fff" stroke-width="1.6"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></div><div class="empty-title">Como posso ajudar?</div><div class="empty-desc">Selecione uma transcrição na barra lateral e faça uma pergunta sobre a reunião — ou use uma das <em>ações rápidas</em>.</div><div class="empty-tips"><span class="tip"><kbd>↵</kbd> enviar</span><span class="tip"><kbd>⇧</kbd>+<kbd>↵</kbd> nova linha</span><span class="tip"><kbd>Esc</kbd> cancelar</span></div>';
  chat.appendChild(empty);
  showToast('Conversa limpa.');
  input.focus();
}

sendBtn.onclick = ()=>{ const t = input.value.trim(); if (!t) return; input.value=''; input.style.height='auto'; pergunta(t); };
stopBtn.onclick = ()=>{ if (abortController) abortController.abort(); };
limparBtn.onclick = limparConversa;
copiarBtn.onclick = copiarUltimaResposta;
menuToggle.onclick = ()=> abrirDrawer(!sidebarEl.classList.contains('drawer-open'));
if (sidebarClose) sidebarClose.onclick = ()=> abrirDrawer(false);
drawerOverlay.onclick = ()=> abrirDrawer(false);
selTrans.addEventListener('change', atualizarTamanhoKb);
if (buscaInput) buscaInput.addEventListener('input', filtrarTranscricoes);
input.addEventListener('keydown', e=>{
  if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendBtn.click(); }
  if(e.key==='Escape' && busy && abortController) { e.preventDefault(); abortController.abort(); }
  if(e.key==='Escape' && !busy && sidebarEl.classList.contains('drawer-open')) { abrirDrawer(false); }
});
input.addEventListener('input', ()=>{ input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,140)+'px'; });
document.addEventListener('keydown', (e)=>{
  if (e.key === 'Escape' && sidebarEl.classList.contains('drawer-open')) abrirDrawer(false);
  navegarActionCards(e);
});
document.querySelectorAll('.action-card').forEach(b=>{
  b.onclick = ()=>{
    const prompt = b.dataset.prompt;
    // Prefill input with prompt for editing, and auto-send? Direct send is better for speed.
    // Fill input so user can edit before sending, but also give toast
    input.value = prompt;
    input.focus();
    input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,140)+'px';
    showToast('Prompt carregado — edite se quiser e pressione Enviar.');
    // Optionally auto-send on second click: if empty, send
    // We do NOT auto-send to allow editing. User can press Enter.
  };
  b.addEventListener('keydown', (e)=>{
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); b.click(); }
  });
});
// double-click to send immediately
document.querySelectorAll('.action-card').forEach(b=>{
  b.addEventListener('dblclick', ()=> pergunta(b.dataset.prompt));
});
// Keyboard shortcut: Ctrl/Cmd+K focus search
document.addEventListener('keydown', (e)=>{
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (buscaInput) { abrirDrawer(true); buscaInput.focus(); buscaInput.select(); }
  }
});
input.focus();
loadList();
