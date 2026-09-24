// Página Configurações (SDD v1.9, T-14.D2): toggles com as regras do menu da bandeja.
import { confirmar, toast } from './ui.js';

const $ = (id) => document.getElementById(id);
const form = $('config-form');
const indisponivel = $('config-indisponivel');
const estadoEl = $('config-estado');
const PROTECAO = {
  protected: ['Protegida', 'Resultados e eventos cifrados em repouso; exportar texto legível exige ação explícita.'],
  compatible: ['Compatível', 'Transcrições em texto legível, como nas versões anteriores.'],
};
let ocupado = false;

function dizer(texto) { if (estadoEl) estadoEl.textContent = texto; }

export function aplicarConfig(cfg) {
  if (!form) return;
  form.hidden = false; indisponivel.hidden = true;
  form.querySelectorAll('input[type="checkbox"][data-chave]').forEach((el) => { el.checked = cfg[el.dataset.chave] === true; el.disabled = false; });
  const sel = $('cfg-modelo_whisper');
  if (sel) {
    sel.innerHTML = '';
    (cfg.modelos_whisper || ['auto']).forEach((m) => { const op = document.createElement('option'); op.value = m; op.textContent = m; sel.appendChild(op); });
    sel.value = cfg.modelo_whisper || 'auto';
  }
  const prot = PROTECAO[cfg.protection_mode] || ['—', ''];
  $('cfg-protecao-badge').textContent = prot[0];
  $('cfg-protecao-badge').className = 'tk-badge tk-badge-protect ' + (cfg.protection_mode === 'protected' ? 'tk-badge-protect--protegida' : 'tk-badge-protect--legivel');
  $('cfg-protecao-desc').textContent = prot[1];
  $('cfg-linha-protegido').hidden = cfg.protection_mode === 'protected';
  const temPerfil = cfg.perfil_voz_existe === true;
  $('cfg-perfil-desc').textContent = temPerfil ? 'Perfil cadastrado. Apagar remove a identificação VOCÊ até um novo cadastro.' : 'Nenhum perfil cadastrado. Cadastre pelo menu da bandeja: Configurações → Minha voz → Cadastrar minha voz (20s).';
  $('cfg-apagar-perfil').disabled = !temPerfil;
  $('cfg-identificar_minha_voz').disabled = !temPerfil;
  dizer('Sincronizado com a bandeja');
}

function mostrarIndisponivel() {
  if (form) form.hidden = true;
  if (indisponivel) indisponivel.hidden = false;
  dizer('Central sem bandeja');
}

async function carregar(fetchFn = (u, o) => fetch(u, o)) {
  try {
    const r = await fetchFn('/api/config', { credentials: 'same-origin' });
    if (!r.ok) { mostrarIndisponivel(); return; }
    aplicarConfig(await r.json());
  } catch (_) { mostrarIndisponivel(); }
}

async function enviar(chave, valor, confirmado = false, fetchFn = (u, o) => fetch(u, o)) {
  const r = await fetchFn('/api/config', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chave, valor, confirmado }) });
  const corpo = await r.json().catch(() => ({}));
  return { status: r.status, corpo };
}

export async function mudar(chave, valor) {
  if (ocupado) return;
  ocupado = true;
  dizer('Salvando…');
  try {
    let resposta = await enviar(chave, valor);
    if (resposta.status === 409) {
      const ok = await confirmar({
        id: 'dialogo-confirmacao', titulo: resposta.corpo.titulo || 'Confirmar?', consequencia: resposta.corpo.consequencia || '',
        confirmarRotulo: resposta.corpo.confirmar || 'Confirmar', perigo: resposta.corpo.acao === 'apagar_perfil_voz' || resposta.corpo.acao === 'pausar_gravacao',
      });
      if (!ok) { await carregar(); return; }
      resposta = await enviar(chave, valor, true);
    }
    if (resposta.status === 503) { mostrarIndisponivel(); return; }
    if (resposta.status !== 200) { toast('error', 'Não foi possível salvar', resposta.corpo.erro || 'Tente de novo.'); await carregar(); return; }
    aplicarConfig(resposta.corpo);
    toast('success', 'Configuração salva', 'A bandeja já reflete a mudança.');
  } catch (_) {
    toast('error', 'Não foi possível salvar', 'Verifique se o aplicativo da bandeja está aberto.');
    await carregar();
  } finally { ocupado = false; }
}

if (typeof document !== 'undefined' && $('pagina-configuracoes')) {
  form.addEventListener('change', (e) => {
    const el = e.target;
    if (!el.dataset.chave) return;
    if (el.type === 'checkbox') mudar(el.dataset.chave, el.checked);
    else if (el.tagName === 'SELECT') mudar(el.dataset.chave, el.value);
  });
  $('cfg-apagar-perfil').addEventListener('click', () => mudar('apagar_perfil_voz', true));
  $('cfg-ativar-protegido').addEventListener('click', () => mudar('protection_mode', 'protected'));
  carregar();
}
