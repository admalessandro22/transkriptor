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
const copiarBtn = document.getElementById('copiar-resposta');
const menuToggle = document.getElementById('menu-toggle');
const sidebarEl = document.getElementById('sidebar');
const drawerOverlay = document.getElementById('drawer-overlay');
let busy = false;
let abortController = null;
let timerInterval = null;
let timerStart = 0;
let historico = [];  // T4.2: histórico de conversa (UX-04)
let transcricoesLista = [];
let ultimaRespostaIA = '';
// Token via cookie HttpOnly (definido no redirect ?token=); header opcional se ainda na URL
const API_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
function apiHeaders(extra = {}) {
  const h = Object.assign({}, extra);
  if (API_TOKEN) h['X-Transkriptor-Token'] = API_TOKEN;
  return h;
}
const fetchOpts = { credentials: 'same-origin' };

function atualizarTamanhoKb() {
  const item = transcricoesLista.find(t => t.arquivo === selTrans.value);
  if (!item) {
    tamanhoKbEl.textContent = '';
    return;
  }
  let meta = `${item.tamanho_kb} KB`;
  if (item.com_sua_voz) meta += ' · com sua voz';
  tamanhoKbEl.innerHTML = item.com_sua_voz
    ? `${item.tamanho_kb} KB · <span class="badge-voce">com sua voz</span>`
    : meta;
}

function buildModelOptions(modelos) {
  selMod.replaceChildren();
  if (!modelos.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Ollama offline';
    selMod.appendChild(opt);
    statusMod.textContent = 'Ollama offline';
    ollamaDot.classList.add('off');
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
  transcricoesLista = items;
  selTrans.replaceChildren();
  if (!items.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '(nenhuma transcrição)';
    selTrans.appendChild(opt);
    tamanhoKbEl.textContent = '';
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
  atualizarTamanhoKb();
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
  }
  try {
    const r = await fetch('/api/modelos', {...fetchOpts, headers: apiHeaders()}); const d = await r.json();
    buildModelOptions(d);
  } catch(e) { buildModelOptions([]); }
}
selMod.addEventListener('change', ()=>{ statusMod.textContent = selMod.value; });

function addMsg(role, text) {
  if (emptyEl) emptyEl.remove();
  const row = document.createElement('div');
  row.className = 'msg-row '+role;
  const av = document.createElement('div');
  av.className = 'avatar '+role;
  av.setAttribute('aria-hidden', 'true');
  av.innerHTML = role==='ai' ? '<svg viewBox="0 0 24 24" style="width:18px;height:18px;fill:#fff"><path d="M12 2L2 7l10 5 10-5-10-5zm0 7L2 14l10 5 10-5-10-5z"/></svg>' : 'Você';
  const bub = document.createElement('div');
  bub.className = 'bubble'; bub.textContent = text;
  row.appendChild(av); row.appendChild(bub);
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
  return bub;
}

function addTyping() {
  if (emptyEl) emptyEl.remove();
  const row = document.createElement('div');
  row.className = 'msg-row ai'; row.id = 'typing-row';
  const av = document.createElement('div'); av.className = 'avatar ai';
  av.setAttribute('aria-hidden', 'true');
  av.innerHTML = '<svg viewBox="0 0 24 24" style="width:18px;height:18px;fill:#fff"><path d="M12 2L2 7l10 5 10-5-10-5zm0 7L2 14l10 5 10-5-10-5z"/></svg>';
  const bub = document.createElement('div'); bub.className = 'bubble';
  bub.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
  row.appendChild(av); row.appendChild(bub);
  chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
  return bub;
}

function iniciarTimer() {
  timerStart = Date.now();
  timerEl.style.display = 'block';
  timerEl.classList.remove('longo');
  timerEl.textContent = 'Processando... 0s';
  timerInterval = setInterval(() => {
    const seg = Math.floor((Date.now() - timerStart) / 1000);
    if (seg >= 15) {
      timerEl.classList.add('longo');
      timerEl.textContent = 'O modelo está pensando... (' + seg + 's)';
    } else {
      timerEl.textContent = `Processando... ${seg}s`;
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
}

async function pergunta(prompt) {
  const transc = selTrans.value;
  const modelo = selMod.value;
  if (!transc) { mostrarToastInline('Selecione uma transcrição primeiro.'); return; }
  if (!modelo || busy) return;
  busy = true; mostrarBotoes(true);
  addMsg('user', prompt);
  const aiEl = addTyping();
  iniciarTimer();
  let firstToken = true;
  abortController = new AbortController();
  try {
    const res = await fetch('/api/chat', {...fetchOpts, method:'POST', headers:apiHeaders({'Content-Type':'application/json'}),
      body: JSON.stringify({modelo, transcricao:transc, pergunta:prompt, historico}),
      signal: abortController.signal});
    const reader = res.body.getReader(); const dec = new TextDecoder(); let txt='';
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      txt += dec.decode(value, {stream:true});
      if (firstToken) { aiEl.innerHTML = ''; firstToken = false; pararTimer(); }
      aiEl.textContent = txt; chat.scrollTop = chat.scrollHeight;
    }
    if (firstToken) { aiEl.textContent = '(sem resposta)'; pararTimer(); }
    if (!txt.trim()) aiEl.textContent = '(sem resposta)';
    if (txt.trim()) {
      ultimaRespostaIA = txt;
      copiarBtn.disabled = false;
    }
    historico.push({role:'user', content:prompt});
    if (txt.trim()) historico.push({role:'assistant', content:txt});
  } catch(e) {
    pararTimer();
    if (e.name === 'AbortError') { aiEl.textContent = '(cancelado)'; }
    else { aiEl.textContent = 'Erro: '+e.message; }
  } finally {
    busy = false; mostrarBotoes(false); abortController = null; pararTimer();
  }
}

function mostrarToastInline(msg) {
  if (emptyEl) emptyEl.remove();
  const el = document.createElement('div');
  el.className = 'msg-row ai';
  el.innerHTML = '<div class="avatar ai" aria-hidden="true"><svg viewBox="0 0 24 24" style="width:18px;height:18px;fill:#fff"><path d="M12 2L2 7l10 5 10-5-10-5zm0 7L2 14l10 5 10-5-10-5z"/></svg></div><div class="bubble" style="color:var(--gold-bright)">' + msg + '</div>';
  chat.appendChild(el); chat.scrollTop = chat.scrollHeight;
}

function abrirDrawer(aberto) {
  sidebarEl.classList.toggle('drawer-open', aberto);
  drawerOverlay.classList.toggle('open', aberto);
  menuToggle.setAttribute('aria-expanded', aberto ? 'true' : 'false');
  drawerOverlay.setAttribute('aria-hidden', aberto ? 'false' : 'true');
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
  copiarBtn.disabled = true;
  chat.innerHTML = '';
  const empty = document.createElement('div');
  empty.className = 'empty-state'; empty.id = 'empty'; empty.setAttribute('role', 'status');
  empty.innerHTML = '<div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24" style="width:34px;height:34px;fill:#fff"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></div><div class="empty-title">Como posso ajudar?</div><div class="empty-desc">Selecione uma transcrição na barra lateral e faça uma pergunta sobre a reunião, ou use uma das ações rápidas.</div>';
  chat.appendChild(empty);
  input.focus();
}

sendBtn.onclick = ()=>{ const t = input.value.trim(); if (!t) return; input.value=''; input.style.height='auto'; pergunta(t); };
stopBtn.onclick = ()=>{ if (abortController) abortController.abort(); };
limparBtn.onclick = limparConversa;
copiarBtn.onclick = copiarUltimaResposta;
menuToggle.onclick = ()=> abrirDrawer(!sidebarEl.classList.contains('drawer-open'));
drawerOverlay.onclick = ()=> abrirDrawer(false);
selTrans.addEventListener('change', atualizarTamanhoKb);
input.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendBtn.click(); }});
input.addEventListener('input', ()=>{ input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,140)+'px'; });
document.addEventListener('keydown', navegarActionCards);
document.querySelectorAll('.action-card').forEach(b=>{
  b.onclick = ()=>pergunta(b.dataset.prompt);
});
// UX-06: foco automático no textarea
input.focus();
loadList();
