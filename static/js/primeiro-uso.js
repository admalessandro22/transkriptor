// Primeiros passos (SDD v2.0, T-15.E3): Whisper, Ollama/OpenRouter e extensão, sem terminal.
import { confirmar, toast } from './ui.js';

const $ = (id) => document.getElementById(id);
const TOKEN = new URLSearchParams(window.location.search).get('token') || '';

function cabecalhos(extra = {}) {
  const h = { ...extra };
  if (TOKEN) h['X-Transkriptor-Token'] = TOKEN;
  return h;
}

async function pedir(url, corpo) {
  const opcoes = { credentials: 'same-origin', headers: cabecalhos(corpo ? { 'Content-Type': 'application/json' } : {}) };
  if (corpo) Object.assign(opcoes, { method: 'POST', body: JSON.stringify(corpo) });
  const r = await fetch(url, opcoes);
  return { status: r.status, corpo: await r.json().catch(() => ({})) };
}

function comToken(caminho) {
  return TOKEN ? `${caminho}?token=${encodeURIComponent(TOKEN)}` : caminho;
}

function mostrarOllama(dados) {
  const o = dados.ollama;
  const texto = {
    online: `Ollama ${o.versao || ''} encontrado neste computador.`,
    parado: 'O Ollama está instalado, mas fechado.',
    nao_instalado: 'O Ollama não está instalado. Ele roda a IA de resumos neste computador, sem enviar nada para fora.',
  }[o.estado] || 'Não foi possível verificar o Ollama.';
  $('pu-ollama').textContent = texto;
  const lista = $('pu-modelos');
  lista.replaceChildren();
  for (const m of o.modelos) {
    const li = document.createElement('li');
    li.textContent = m.id;
    lista.appendChild(li);
  }
  const sugerido = dados.modelo_sugerido;
  const falta = o.estado === 'online' && !o.modelos.some((m) => m.id === sugerido.id);
  $('pu-baixar').hidden = !falta;
  $('pu-baixar').textContent = `Baixar ${sugerido.id} (~${sugerido.tamanho_gb} GB, indicado para este computador)`;
  $('pu-baixar').dataset.modelo = sugerido.id;
  $('pu-iniciar').hidden = o.estado !== 'parado';
  $('pu-instalar').href = o.pagina_instalacao;
  $('pu-instalar').hidden = o.estado !== 'nao_instalado';
}

function mostrar(dados) {
  const h = dados.hardware;
  $('pu-transcricao').textContent = `A transcrição é feita pelo Whisper, aqui mesmo. ${h.cuda ? `Placa de vídeo com ${h.vram_gb} GB encontrada` : 'Sem placa de vídeo compatível; o processador dá conta'}. Modelo indicado: ${dados.whisper_recomendado}.`;
  mostrarOllama(dados);
  $('pu-extensao').textContent = dados.extensao.pareada
    ? 'Extensão conectada: os nomes do Meet já chegam ao Transkriptor.'
    : 'Adicione a extensão Transkriptor Meet Bridge ao Chrome ou Edge. Ela se conecta sozinha quando o Transkriptor está aberto.';
  const lojas = $('pu-lojas');
  lojas.replaceChildren();
  for (const loja of dados.extensao.lojas || []) {
    const a = document.createElement('a');
    a.className = 'tk-btn tk-btn--primary tk-btn--sm';
    a.href = loja.url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = `Adicionar ao ${loja.navegador}`;
    lojas.appendChild(a);
  }
  $('pu-estado').textContent = dados.concluido ? 'Concluído' : 'Em andamento';
}

async function atualizar() {
  const { status, corpo } = await pedir('/api/primeiro-uso');
  if (status === 200) mostrar(corpo);
}

async function baixar() {
  const modelo = $('pu-baixar').dataset.modelo;
  const { status, corpo } = await pedir('/api/primeiro-uso/ollama/baixar', { modelo });
  if (status !== 202) { toast('error', 'Não foi possível baixar', corpo.erro || 'Tente de novo.'); return; }
  const barra = $('pu-progresso');
  barra.hidden = false;
  $('pu-baixar').disabled = true;
  for (;;) {
    await new Promise((r) => setTimeout(r, 1000));
    const p = (await pedir(`/api/primeiro-uso/ollama/baixar/${corpo.id}`)).corpo;
    barra.value = p.percentual || 0;
    if (p.estado !== 'baixando') {
      barra.hidden = true;
      $('pu-baixar').disabled = false;
      if (p.estado === 'concluido') toast('success', 'Modelo pronto', `${modelo} já pode fazer resumos.`);
      else toast('error', 'O download falhou', p.erro || 'Tente de novo.');
      await atualizar();
      return;
    }
  }
}

async function iniciarOllama() {
  let r = await pedir('/api/primeiro-uso/ollama/iniciar', {});
  if (r.status === 409) {
    const ok = await confirmar({ id: 'dialogo-confirmacao', titulo: r.corpo.titulo, consequencia: r.corpo.consequencia, confirmarRotulo: r.corpo.confirmar });
    if (!ok) return;
    r = await pedir('/api/primeiro-uso/ollama/iniciar', { confirmado: true });
  }
  if (r.status !== 202) { toast('error', 'Não foi possível iniciar', r.corpo.erro || 'Abra o Ollama pelo menu Iniciar.'); return; }
  toast('success', 'Ollama iniciando', 'Em alguns segundos ele aparece aqui.');
  setTimeout(atualizar, 4000);
}

async function concluir() {
  await pedir('/api/primeiro-uso/concluir', {});
  window.location.href = comToken('inicio');
}

if (typeof document !== 'undefined' && $('pagina-primeiro-uso')) {
  $('pu-link-config').href = comToken('configuracoes');
  $('pu-baixar').addEventListener('click', baixar);
  $('pu-iniciar').addEventListener('click', iniciarOllama);
  $('pu-concluir').addEventListener('click', concluir);
  $('pu-pular').addEventListener('click', concluir);
  atualizar();
}
