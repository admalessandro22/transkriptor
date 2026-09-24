// Barra de estado da Central (SDD v1.9, T-14.B1): espelha o ícone da bandeja
// lendo /api/estado a cada 2 s; pausa com a aba oculta; nunca gera toast.
const INTERVALO_MS = 2000;
const ROTULOS = {
  aguardando: 'Aguardando reunião', gravando: 'Gravando', processando: 'Processando reunião',
  separando_vozes: 'Separando vozes', pausado: 'Pausado', erro: 'Erro',
};
const ESTADOS = new Set(Object.keys(ROTULOS));

export function rotuloDoEstado(estado, rotuloServidor) {
  if (rotuloServidor && typeof rotuloServidor === 'string') return rotuloServidor;
  return ROTULOS[estado] || 'Central sem bandeja';
}

export function aplicarEstado(barra, snapshot) {
  if (!barra) return;
  const texto = barra.querySelector('.tk-statusbar__texto') || barra;
  if (!snapshot || !ESTADOS.has(snapshot.estado)) {
    barra.dataset.estado = 'indisponivel';
    texto.textContent = 'Central sem bandeja';
    barra.title = 'O aplicativo da bandeja não está ligado a esta Central.';
    return;
  }
  barra.dataset.estado = snapshot.estado;
  let rotulo = rotuloDoEstado(snapshot.estado, snapshot.rotulo);
  if (snapshot.estado === 'gravando' && Array.isArray(snapshot.fontes) && snapshot.fontes.length) {
    rotulo += ' · ' + snapshot.fontes.join(', ');
  }
  texto.textContent = rotulo;
  barra.title = snapshot.processamento ? 'Pós-processamento: ' + snapshot.processamento : '';
}

let timer = null;
let emCurso = false;

function publicar(snap) {
  document.dispatchEvent(new CustomEvent('tk-estado', { detail: snap }));
}

async function ler(barra, fetchFn) {
  if (emCurso) return;
  emCurso = true;
  try {
    const r = await fetchFn('/api/estado', { credentials: 'same-origin' });
    if (!r.ok) { aplicarEstado(barra, null); publicar(null); return; }
    const snap = await r.json();
    aplicarEstado(barra, snap);
    publicar(snap);
  } catch (_) {
    aplicarEstado(barra, null);
    publicar(null);
  } finally {
    emCurso = false;
  }
}

/** Inicia o polling; devolve uma função que o interrompe. */
export function iniciarEstado(barra = document.getElementById('statusbar'), fetchFn = (u, o) => fetch(u, o), intervaloMs = INTERVALO_MS) {
  if (!barra) return () => {};
  const passo = () => { if (!document.hidden) ler(barra, fetchFn); };
  const agendar = () => { if (timer) clearInterval(timer); timer = setInterval(passo, intervaloMs); };
  const aoMudarVisibilidade = () => {
    if (document.hidden) { if (timer) clearInterval(timer); timer = null; }
    else { passo(); agendar(); }
  };
  document.addEventListener('visibilitychange', aoMudarVisibilidade);
  passo();
  agendar();
  return () => { if (timer) clearInterval(timer); timer = null; document.removeEventListener('visibilitychange', aoMudarVisibilidade); };
}
