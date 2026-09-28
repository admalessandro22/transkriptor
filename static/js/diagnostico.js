// Página Diagnóstico (SDD v1.9, T-14.D3): itens com ação sugerida, exportação sem PII e retranscrição.
import { confirmar, toast, icone } from './ui.js';

const $ = (id) => document.getElementById(id);
const ESTADO_ITEM = { OK: ['Ok', 'gravando'], AVISO: ['Aviso', 'separando_vozes'], ERRO: ['Erro', 'erro'] };

/** Próximo passo por item; a regra usa nome e estado, nunca o detalhe (que pode ter caminhos). */
export function acaoSugerida(item) {
  const nome = String(item.nome || '').toLowerCase();
  const estado = item.estado;
  if (estado === 'OK') return '';
  if (nome === 'soundcard') return 'Atualize a biblioteca de áudio: pip install -U "soundcard>=0.4.6".';
  if (nome === 'numpy') return 'Reinstale as dependências pelo instalar.bat.';
  if (nome.startsWith('áudio do sistema') || nome.startsWith('audio do sistema')) return estado === 'ERRO' ? 'Verifique o dispositivo de saída padrão do Windows e se o loopback está disponível.' : 'Normal se nada estiver tocando agora.';
  if (nome === 'microfone') return 'Verifique o microfone padrão do Windows e a permissão de microfone para aplicativos.';
  if (nome.startsWith('fonte:') || nome === 'detecção') return 'Abra a reunião no navegador com a aba em primeiro plano ou ative a extensão do Meet.';
  if (nome.startsWith('modelo whisper')) return 'Escolha outro modelo em Configurações ou verifique o espaço em disco.';
  if (nome.startsWith('integridade da captura')) return 'Se a captura estiver ativa sem avanço, pause e retome a gravação automática.';
  if (nome === 'gravando agora') return 'Aguardando reunião. Entre numa reunião do Meet ou do Zoom para o Transkriptor perguntar antes de gravar.';
  if (nome === 'zoom') return 'Se a versão do Zoom mudou a classe da janela, o item mostra título e classe para atualização.';
  return 'Veja o log para detalhes.';
}

function linhaItem(item) {
  const div = document.createElement('div');
  div.className = 'tk-row diag__item';
  div.dataset.estado = item.estado;
  const [rotulo, estado] = ESTADO_ITEM[item.estado] || ['—', 'aguardando'];
  const badge = document.createElement('span'); badge.className = 'tk-badge tk-badge-state diag__badge'; badge.dataset.estado = estado; badge.textContent = rotulo;
  const corpo = document.createElement('div'); corpo.className = 'diag__corpo';
  const nome = document.createElement('span'); nome.className = 'tk-row__principal'; nome.textContent = item.nome;
  const detalhe = document.createElement('span'); detalhe.className = 'diag__detalhe'; detalhe.textContent = item.detalhe || '';
  corpo.append(nome, detalhe);
  const acao = acaoSugerida(item);
  if (acao) { const a = document.createElement('span'); a.className = 'diag__acao'; a.appendChild(icone('chevron-right', 'tk-icon tk-icon--sm')); a.appendChild(document.createTextNode(acao)); corpo.appendChild(a); }
  div.append(badge, corpo);
  return div;
}

export function renderDiagnostico(dados) {
  const lista = $('diag-lista');
  lista.innerHTML = '';
  (dados.itens || []).forEach((i) => lista.appendChild(linhaItem(i)));
  lista.hidden = false; $('diag-vazio').hidden = true;
  const resumo = $('diag-resumo'); resumo.hidden = false;
  const badge = $('diag-resumo-badge');
  const erros = dados.erros || 0, avisos = dados.avisos || 0;
  badge.dataset.estado = erros ? 'erro' : avisos ? 'separando_vozes' : 'gravando';
  badge.textContent = erros ? `${erros} erro${erros > 1 ? 's' : ''}` : avisos ? `${avisos} aviso${avisos > 1 ? 's' : ''}` : 'Tudo certo';
  $('diag-resumo-texto').textContent = (erros ? 'Erro impede a gravação; resolva antes de contar com o app. ' : '') + (dados.relatorio ? `Relatório salvo como ${dados.relatorio}.` : '');
  $('diag-exportar').disabled = false;
}

async function rodar(fetchFn = (u, o) => fetch(u, o)) {
  const btn = $('diag-rodar');
  btn.classList.add('is-loading'); btn.disabled = true;
  $('diag-skeleton').hidden = false; $('diag-vazio').hidden = true; $('diag-lista').hidden = true;
  try {
    const r = await fetchFn('/api/diagnostico', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const corpo = await r.json().catch(() => ({}));
    if (r.status === 503) { $('diag-indisponivel').hidden = false; return; }
    if (!r.ok) { toast('error', 'O diagnóstico não terminou', corpo.erro || 'Tente de novo.'); $('diag-vazio').hidden = false; return; }
    renderDiagnostico(corpo);
  } catch (_) {
    toast('error', 'O diagnóstico não terminou', 'Verifique se o aplicativo da bandeja está aberto.');
    $('diag-vazio').hidden = false;
  } finally {
    btn.classList.remove('is-loading'); btn.disabled = false; $('diag-skeleton').hidden = true;
  }
}

async function exportar(fetchFn = (u, o) => fetch(u, o)) {
  const r = await fetchFn('/api/diagnostico/exportar', { credentials: 'same-origin' });
  if (!r.ok) { toast('error', 'Nada para exportar', 'Rode o diagnóstico antes.'); return; }
  const url = URL.createObjectURL(await r.blob());
  try {
    const a = document.createElement('a'); a.href = url; a.download = 'diagnostico-transkriptor.txt';
    document.body.appendChild(a); a.click(); a.remove();
    toast('success', 'Relatório exportado', 'Sem caminhos pessoais, credenciais ou títulos de reunião.');
  } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
}

function formatarDuracao(seg) {
  const s = Math.round(seg || 0);
  return s >= 60 ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s` : `${s} s`;
}

export async function carregarAudios(fetchFn = (u, o) => fetch(u, o)) {
  const lista = $('retranscrever-lista'), vazio = $('retranscrever-vazio');
  try {
    const r = await fetchFn('/api/audios-retidos', { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const itens = await r.json();
    lista.innerHTML = '';
    if (!itens.length) { vazio.hidden = false; lista.hidden = true; vazio.innerHTML = '<h3 class="tk-empty__titulo">Nenhum áudio retido</h3><p class="tk-empty__texto">Os áudios ficam em transcrições/audio por sete dias após um resultado válido.</p>'; return; }
    itens.forEach((a) => {
      const div = document.createElement('div'); div.className = 'tk-row'; div.dataset.nome = a.nome;
      const nome = document.createElement('span'); nome.className = 'tk-row__principal'; nome.textContent = a.nome;
      const meta = document.createElement('span'); meta.className = 'tk-row__meta'; meta.textContent = `${String(a.mtime || '').replace('T', ' ')} · ${formatarDuracao(a.duracao_seg)}`;
      const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'tk-btn tk-btn--sm'; btn.textContent = 'Retranscrever'; btn.dataset.acao = 'retranscrever';
      btn.addEventListener('click', () => retranscrever(a.nome, btn));
      div.append(nome, meta, btn);
      lista.appendChild(div);
    });
    lista.hidden = false; vazio.hidden = true;
  } catch (_) {
    vazio.hidden = false; lista.hidden = true;
    vazio.innerHTML = '<h3 class="tk-empty__titulo">Não foi possível listar os áudios</h3><p class="tk-empty__texto">Verifique se o aplicativo da bandeja está aberto.</p>';
  }
}

async function retranscrever(nome, botao, fetchFn = (u, o) => fetch(u, o)) {
  const ok = await confirmar({ id: 'dialogo-retranscrever', confirmarId: 'confirmar-retranscrever', titulo: 'Retranscrever este áudio?', consequencia: 'Gera uma nova transcrição com as configurações atuais. O áudio e as transcrições existentes não são apagados.', confirmarRotulo: 'Retranscrever' });
  if (!ok) return;
  botao.classList.add('is-loading'); botao.disabled = true;
  try {
    const r = await fetchFn('/api/acoes/retranscrever', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nome }) });
    const corpo = await r.json().catch(() => ({}));
    if (r.status !== 202) { toast('error', 'Não foi possível iniciar', corpo.erro || 'Tente de novo.'); return; }
    $('retranscrever-estado').textContent = 'Retranscrevendo… acompanhe o progresso na barra de estado.';
    toast('info', 'Retranscrição iniciada', 'O resultado aparece em Reuniões quando terminar.');
  } catch (_) {
    toast('error', 'Não foi possível iniciar', 'Verifique se o aplicativo da bandeja está aberto.');
  } finally { botao.classList.remove('is-loading'); botao.disabled = false; }
}

export async function gerarCodigoPareamento(fetchFn = (u, o) => fetch(u, o)) {
  const btn = $('pareamento-gerar'), aviso = $('pareamento-aviso'), wrap = $('pareamento-resultado');
  btn.classList.add('is-loading'); btn.disabled = true; aviso.hidden = true;
  try {
    const r = await fetchFn('/api/acoes/pareamento', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) {
      wrap.hidden = true; aviso.hidden = false;
      aviso.textContent = corpo.erro || 'Não foi possível gerar o código. Verifique se o aplicativo da bandeja está aberto.';
      return;
    }
    $('pareamento-codigo').textContent = corpo.codigo || '';
    wrap.hidden = false;
    const minutos = Math.max(1, Math.round((corpo.validade_seg || 300) / 60));
    aviso.hidden = false;
    aviso.textContent = (corpo.ponte_ativa ? '' : 'A opção "Identificar nomes do Meet" está desligada: ligue-a em Configurações antes de parear. ') + `Válido por ${minutos} min e só uma vez; gere outro se expirar.`;
  } catch (_) {
    wrap.hidden = true; aviso.hidden = false;
    aviso.textContent = 'Não foi possível gerar o código. Verifique se o aplicativo da bandeja está aberto.';
  } finally { btn.classList.remove('is-loading'); btn.disabled = false; }
}

async function copiarCodigo() {
  const codigo = $('pareamento-codigo').textContent;
  if (!codigo) return;
  try {
    await navigator.clipboard.writeText(codigo);
    toast('success', 'Código copiado', 'Cole na página de pareamento da extensão.');
  } catch (_) {
    toast('error', 'Não foi possível copiar', 'Selecione o código e copie com Ctrl+C.');
  }
}

if (typeof document !== 'undefined' && $('pagina-diagnostico')) {
  $('pareamento-gerar').addEventListener('click', () => gerarCodigoPareamento());
  $('pareamento-copiar').addEventListener('click', copiarCodigo);
  $('diag-rodar').addEventListener('click', () => rodar());
  $('diag-exportar').addEventListener('click', () => exportar());
  carregarAudios();
  if (location.hash === '#retranscrever') $('retranscrever').scrollIntoView();
}
