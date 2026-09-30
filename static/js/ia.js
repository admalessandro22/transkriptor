// Configurações de IA (SDD v2.0, T-15.D3): Whisper local, resumo e chat por Ollama ou OpenRouter.
// Vale sem a bandeja: o estado vem de /api/ia. A chave do OpenRouter só vai; nunca volta.
import { confirmar, toast } from './ui.js';

const $ = (id) => document.getElementById(id);
const API_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
const FUNCOES = ['resumo', 'chat'];
let estado = null;

function cabecalhos(extra = {}) {
  const h = { ...extra };
  if (API_TOKEN) h['X-Transkriptor-Token'] = API_TOKEN;
  return h;
}

async function pedir(url, opcoes = {}) {
  const r = await fetch(url, { credentials: 'same-origin', ...opcoes, headers: cabecalhos(opcoes.headers || {}) });
  return { status: r.status, corpo: await r.json().catch(() => ({})) };
}

function opcoes(select, itens, valor) {
  select.replaceChildren();
  for (const [v, rotulo] of itens) {
    const op = document.createElement('option');
    op.value = v;
    op.textContent = rotulo;
    select.appendChild(op);
  }
  select.value = itens.some(([v]) => v === valor) ? valor : '';
}

async function carregarModelos(funcao) {
  const cfg = estado[funcao];
  const sel = $(`ia-${funcao}-modelo`);
  const aviso = $(`ia-${funcao}-estado`);
  const { corpo } = await pedir('/api/ia/modelos?provedor=' + encodeURIComponent(cfg.provedor));
  const lista = Array.isArray(corpo.modelos) ? corpo.modelos : [];
  // No OpenRouter o id (org/modelo) é o que identifica sem ambiguidade: mostra os dois.
  const itens = [['', 'Automático'], ...lista.map((m) => [m.id, m.nome && m.nome !== m.id ? `${m.nome} (${m.id})` : m.id])];
  if (cfg.modelo && !lista.some((m) => m.id === cfg.modelo)) itens.push([cfg.modelo, cfg.modelo]);
  opcoes(sel, itens, cfg.modelo);
  const est = corpo.estado || {};
  aviso.textContent = est.estado === 'online' ? `${lista.length} modelo(s) disponíveis.`
    : est.estado === 'sem_modelos' ? 'O Ollama está aberto, mas sem modelos instalados.'
      : (est.detalhe || 'Provedor indisponível.');
}

function aplicar(novo) {
  estado = novo;
  const t = estado.transcricao;
  $('ia-transcricao-info').textContent = `Idioma: ${t.idioma}. ${t.hardware.cuda ? `Placa de vídeo com ${t.hardware.vram_gb} GB` : 'Sem placa de vídeo compatível'}; modelo recomendado: ${t.recomendado}.`;
  $('ia-whisper_dispositivo').value = t.dispositivo;
  $('ia-whisper_precisao').value = t.precisao;
  $('ia-ollama_url').value = estado.ollama_url;
  const or = estado.openrouter;
  $('ia-openrouter-status').textContent = or.configurada ? `Chave configurada (termina em ${or.final}).` + (or.consentido_em ? ' Uso autorizado.' : '') : 'Nenhuma chave configurada.';
  for (const f of FUNCOES) {
    $(`ia-${f}-provedor`).value = estado[f].provedor;
    carregarModelos(f);
  }
}

async function mudar(chave, valor) {
  let r = await pedir('/api/ia', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chave, valor, confirmado: false }) });
  if (r.status === 409) {
    const ok = await confirmar({
      id: 'dialogo-confirmacao', titulo: r.corpo.titulo || 'Confirmar?', consequencia: r.corpo.consequencia || '',
      confirmarRotulo: r.corpo.confirmar || 'Confirmar', perigo: true,
    });
    if (!ok) { aplicar(estado); return false; }
    r = await pedir('/api/ia', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chave, valor, confirmado: true }) });
  }
  if (r.status !== 200) {
    toast('error', 'Não foi possível salvar', r.corpo.erro || 'Tente de novo.');
    if (estado) aplicar(estado);
    return false;
  }
  aplicar(r.corpo);
  toast('success', 'Configuração salva', 'Vale a partir do próximo uso.');
  return true;
}

async function testar(funcao) {
  const modelo = $(`ia-${funcao}-modelo`).value || [...$(`ia-${funcao}-modelo`).options].map((o) => o.value).find(Boolean);
  const aviso = $(`ia-${funcao}-estado`);
  if (!modelo) { aviso.textContent = 'Escolha um modelo para testar.'; return; }
  aviso.textContent = 'Testando…';
  const { corpo } = await pedir('/api/ia/testar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provedor: estado[funcao].provedor, modelo }) });
  aviso.textContent = corpo.ok ? `Respondeu em ${corpo.latencia_ms} ms.` : (corpo.erro || 'Não respondeu.');
}

async function iniciar() {
  const { status, corpo } = await pedir('/api/ia');
  if (status !== 200) return;
  aplicar(corpo);
  $('ia-whisper_dispositivo').addEventListener('change', (e) => mudar('whisper_dispositivo', e.target.value));
  $('ia-whisper_precisao').addEventListener('change', (e) => mudar('whisper_precisao', e.target.value));
  for (const f of FUNCOES) {
    $(`ia-${f}-provedor`).addEventListener('change', (e) => mudar(`ia_${f}_provedor`, e.target.value));
    $(`ia-${f}-modelo`).addEventListener('change', (e) => mudar(`ia_${f}_modelo`, e.target.value));
    $(`ia-${f}-testar`).addEventListener('click', () => testar(f));
  }
  $('ia-ollama-salvar').addEventListener('click', () => mudar('ollama_url', $('ia-ollama_url').value));
  $('ia-openrouter-salvar').addEventListener('click', async () => {
    const campo = $('ia-openrouter-chave');
    const valor = campo.value;
    campo.value = ''; // a chave não fica na tela nem na memória da página
    if (valor) await mudar('openrouter_chave', valor);
  });
}

if (typeof document !== 'undefined' && $('config-ia')) iniciar();
