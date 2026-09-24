// Página Início (SDD v1.9, T-14.D1): estado ao vivo, última reunião, proteção e recentes.
import { linhaReuniao, preencherParticipantes } from './reunioes-pagina.js';

const $ = (id) => document.getElementById(id);
const DETALHES = {
  aguardando: 'Nenhuma reunião à vista. Ao detectar uma, o Transkriptor pergunta antes de gravar.',
  gravando: 'Gravando a reunião atual. Nada é mostrado durante a gravação.',
  processando: 'Transcrevendo e organizando a última reunião.',
  separando_vozes: 'Separando quem falou o quê.',
  pausado: 'A gravação automática está pausada. Nenhuma reunião será gravada até retomar.',
  erro: 'Algo falhou. Abra o Diagnóstico para ver o motivo.',
  indisponivel: 'O aplicativo da bandeja não está ligado a esta Central.',
};
const PROTECAO = {
  protected: ['Protegida', 'Resultados e eventos cifrados em repouso; exportar texto legível exige ação explícita.'],
  compatible: ['Compatível', 'Transcrições em texto legível, como nas versões anteriores. Ative o modo protegido em Configurações.'],
};

function formatarData(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')} · ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function aplicarSnapshot(snap) {
  const estadoEl = $('inicio-estado');
  if (!estadoEl) return;
  const estado = snap && snap.estado ? snap.estado : 'indisponivel';
  estadoEl.dataset.estado = estado;
  $('inicio-estado-valor').textContent = snap && snap.rotulo ? snap.rotulo : 'Central sem bandeja';
  let detalhe = DETALHES[estado] || '';
  if (snap && snap.processamento && estado === 'processando') detalhe = `Etapa: ${snap.processamento}.`;
  if (snap && estado === 'gravando' && Array.isArray(snap.fontes) && snap.fontes.length) detalhe += ` Sinal de: ${snap.fontes.join(', ')}.`;
  $('inicio-estado-detalhe').textContent = detalhe;

  const ultima = snap && snap.ultima_reuniao;
  $('inicio-ultima-valor').textContent = ultima ? formatarData(ultima.started_at) : '—';
  $('inicio-ultima-detalhe').textContent = ultima ? `Estado: ${ultima.estado}.` : 'Nenhuma reunião processada ainda.';

  const prot = snap && PROTECAO[snap.protecao];
  $('inicio-protecao-valor').textContent = prot ? prot[0] : '—';
  $('inicio-protecao-detalhe').textContent = prot ? prot[1] : 'Estado da proteção em repouso.';
}

async function carregarRecentes(fetchFn = (u, o) => fetch(u, o)) {
  const lista = $('inicio-recentes');
  const estado = $('inicio-recentes-estado');
  if (!lista) return;
  try {
    const r = await fetchFn('/api/reunioes-indice?limit=5', { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const dados = await r.json();
    const itens = dados.reunioes || [];
    lista.innerHTML = '';
    if (!itens.length) {
      estado.hidden = false; lista.hidden = true;
      estado.innerHTML = '<h3 class="tk-empty__titulo">Nenhuma reunião ainda</h3><p class="tk-empty__texto">Entre numa reunião do Meet ou do Zoom. O Transkriptor pergunta antes de gravar.</p>';
      return;
    }
    itens.forEach((r) => lista.appendChild(linhaReuniao(r)));
    lista.hidden = false; estado.hidden = true;
    preencherParticipantes(lista, fetchFn);
  } catch (_) {
    estado.hidden = false; lista.hidden = true;
    estado.innerHTML = '<h3 class="tk-empty__titulo">Não foi possível carregar</h3><p class="tk-empty__texto">A Central não conseguiu ler o índice de reuniões.</p>';
  }
}

if (typeof document !== 'undefined' && $('pagina-inicio')) {
  document.addEventListener('tk-estado', (e) => aplicarSnapshot(e.detail));
  carregarRecentes();
}
