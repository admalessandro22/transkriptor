// Ações de cada reunião na página Reuniões: resumo da IA, edição (nome e
// participantes) e exclusão com dupla confirmação (plano exato + "EXCLUIR").
import { icone, toast } from './ui.js';
import { mapeamentoExibicao, nomeAmigavel } from './participantes.js';

const PALAVRA = 'EXCLUIR';
const API_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
function cabecalhos(extra = {}) {
  const h = Object.assign({}, extra);
  if (API_TOKEN) h['X-Transkriptor-Token'] = API_TOKEN;
  return h;
}
const url = (id, sufixo) => '/api/reunioes/' + encodeURIComponent(id) + sufixo;

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto != null) e.textContent = texto;
  return e;
}

function mb(bytes) {
  const v = bytes / 1e6;
  return (v < 0.1 ? '< 0,1' : v.toLocaleString('pt-BR', { maximumFractionDigits: v < 10 ? 1 : 0 })) + ' MB';
}

/** Diálogo modal próprio (reusa .tk-dialog); some do DOM ao fechar. */
function dialogo({ titulo, subtitulo = '', perigo = false, largo = false }) {
  const dlg = el('dialog', 'tk-dialog tk-dialog--reuniao' + (perigo ? ' tk-dialog--perigo' : '') + (largo ? ' tk-dialog--largo' : ''));
  const id = 'dlg-reuniao-' + Math.random().toString(36).slice(2, 8);
  dlg.setAttribute('aria-labelledby', id + '-t');
  const corpo = el('div', 'tk-dialog__corpo');
  const h = el('h2', 'tk-dialog__titulo', titulo); h.id = id + '-t';
  corpo.appendChild(h);
  if (subtitulo) corpo.appendChild(el('p', 'tk-dialog__subtitulo', subtitulo));
  const conteudo = el('div', 'tk-dialog__conteudo');
  const aviso = el('p', 'tk-dialog__aviso'); aviso.setAttribute('role', 'alert'); aviso.hidden = true;
  corpo.append(conteudo, aviso);
  const acoes = el('div', 'tk-dialog__acoes');
  dlg.append(corpo, acoes);
  document.body.appendChild(dlg);
  const anterior = document.activeElement;
  dlg.addEventListener('close', () => { dlg.remove(); if (anterior && anterior.focus) anterior.focus(); });
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  const avisar = (texto) => { aviso.textContent = texto || ''; aviso.hidden = !texto; };
  const botao = (texto, classe, aoClicar) => {
    const b = el('button', 'tk-btn ' + classe, texto); b.type = 'button';
    b.addEventListener('click', aoClicar); acoes.appendChild(b); return b;
  };
  const abrir = () => { if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', ''); };
  return { dlg, conteudo, acoes, avisar, botao, abrir };
}

function infoLinha(linha) {
  const texto = (sel) => { const c = linha.querySelector(sel); return c ? c.textContent : ''; };
  return {
    id: linha.dataset.id,
    titulo: linha.dataset.titulo || '',
    rotulo: texto('.tk-row__abrir'),
    quando: `${texto('.tk-reuniao__data')} · ${texto('.tk-reuniao__inicio')}–${texto('.tk-reuniao__fim')} · ${texto('.tk-reuniao__duracao')}`.replace(/–—/, ''),
  };
}

// ---- resumo -------------------------------------------------------------------

async function abrirResumo(info, fetchFn) {
  const d = dialogo({ titulo: info.rotulo, subtitulo: info.quando, largo: true });
  const texto = el('p', 'tk-resumo-ia'); texto.setAttribute('aria-live', 'polite');
  const selo = el('p', 'tk-resumo-ia__selo'); selo.append(icone('sparkles', 'tk-icon tk-icon--sm'), document.createTextNode(' Resumo gerado pela IA local'));
  d.conteudo.append(selo, texto);
  let timer = null;
  const tentar = d.botao('Tentar de novo', 'tk-btn--secondary', () => carregar(true));
  tentar.hidden = true;
  const link = el('a', 'tk-btn tk-btn--secondary', 'Abrir transcrição'); link.href = '/participantes?reuniao=' + encodeURIComponent(info.id);
  d.acoes.appendChild(link);
  d.botao('Fechar', 'tk-btn--primary', () => d.dlg.close());
  d.dlg.addEventListener('close', () => clearTimeout(timer));
  async function carregar(novamente = false) {
    clearTimeout(timer);
    try {
      const r = await fetchFn(url(info.id, '/resumo') + (novamente ? '?tentar=1' : ''), { credentials: 'same-origin', headers: cabecalhos() });
      const dados = r.ok ? await r.json() : { estado: 'indisponivel', motivo: 'IA local indisponível' };
      texto.dataset.estado = dados.estado;
      tentar.hidden = dados.estado !== 'indisponivel';
      if (dados.estado === 'pronto') texto.textContent = dados.resumo;
      else if (dados.estado === 'gerando') { texto.textContent = 'Gerando resumo com a IA local… isso leva cerca de um minuto.'; timer = setTimeout(carregar, 5000); }
      else texto.textContent = 'Resumo indisponível: ' + (dados.motivo || 'IA local indisponível') + '.';
    } catch (_) {
      texto.dataset.estado = 'indisponivel'; tentar.hidden = false;
      texto.textContent = 'Não foi possível falar com a Central.';
    }
  }
  d.abrir();
  await carregar();
}

// ---- edição -------------------------------------------------------------------

async function abrirEdicao(info, fetchFn, aoMudar) {
  const d = dialogo({ titulo: 'Editar reunião', subtitulo: info.quando, largo: true });
  const form = el('form', 'tk-form-reuniao'); form.noValidate = true;
  const campoTitulo = el('div', 'tk-field');
  const lbl = el('label', 'tk-label', 'Nome da reunião'); lbl.htmlFor = 'edicao-titulo';
  const inTitulo = el('input'); inTitulo.id = 'edicao-titulo'; inTitulo.maxLength = 80; inTitulo.value = info.titulo; inTitulo.placeholder = 'Reunião sem título'; inTitulo.autocomplete = 'off';
  campoTitulo.append(lbl, inTitulo, el('span', 'tk-field__ajuda', 'Até 80 caracteres. Deixe vazio para usar o título da gravação.'));
  const secao = el('fieldset', 'tk-form-reuniao__pessoas');
  secao.appendChild(el('legend', 'tk-label', 'Participantes'));
  const lista = el('div', 'tk-form-reuniao__lista'); lista.appendChild(el('p', 'tk-subtle', 'Carregando falantes…'));
  secao.appendChild(lista);
  form.append(campoTitulo, secao);
  d.conteudo.appendChild(form);
  d.botao('Cancelar', 'tk-btn--secondary', () => d.dlg.close());
  const salvar = d.botao('Salvar', 'tk-btn--primary', () => form.requestSubmit());
  d.abrir();
  inTitulo.focus();

  let dados = null; let clusters = []; let atuais = {};
  try {
    const r = await fetchFn(url(info.id, '/resultado'), { credentials: 'same-origin', headers: cabecalhos() });
    if (!r.ok) throw new Error();
    dados = await r.json();
    const segs = dados.segmentos || [];
    clusters = [...new Set(segs.map((s) => s.speaker_cluster_id))].sort();
    const mapa = mapeamentoExibicao(segs, dados.mapeamento);
    lista.innerHTML = '';
    clusters.forEach((c, i) => {
      const nomeAtual = mapa[c] && mapa[c].display_name ? mapa[c].display_name : '';
      atuais[c] = nomeAtual;
      const linha = el('div', 'tk-form-reuniao__pessoa');
      const idIn = 'edicao-falante-' + i;
      const rot = el('label', 'tk-form-reuniao__rotulo'); rot.htmlFor = idIn;
      rot.append(el('span', 'tk-form-reuniao__cor', ''), document.createTextNode(`Falante ${i + 1}`));
      rot.firstChild.dataset.cor = String((i % 8) + 1);
      const falas = segs.filter((s) => s.speaker_cluster_id === c).length;
      const inp = el('input', 'tk-input'); inp.id = idIn; inp.dataset.cluster = c; inp.maxLength = 80; inp.value = nomeAtual;
      inp.placeholder = nomeAmigavel(c, {}, clusters); inp.autocomplete = 'off';
      linha.append(rot, inp, el('span', 'tk-form-reuniao__falas', falas === 1 ? '1 fala' : `${falas} falas`));
      lista.appendChild(linha);
    });
    if (!clusters.length) lista.replaceChildren(el('p', 'tk-subtle', 'Esta reunião não tem falantes separados.'));
  } catch (_) {
    lista.replaceChildren(el('p', 'tk-subtle', 'Não foi possível carregar os participantes; só o nome da reunião pode ser editado agora.'));
  }

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    d.avisar('');
    salvar.disabled = true; salvar.classList.add('is-loading');
    try {
      const novoTitulo = inTitulo.value.trim();
      if (novoTitulo !== info.titulo) {
        const r = await fetchFn(url(info.id, '/titulo'), { method: 'POST', credentials: 'same-origin', headers: cabecalhos({ 'Content-Type': 'application/json' }), body: JSON.stringify({ titulo: novoTitulo }) });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).erro || 'Não foi possível salvar o nome.');
      }
      let revisao = dados && dados.revision;
      for (const inp of lista.querySelectorAll('input[data-cluster]')) {
        const nome = inp.value.trim();
        if (!nome || nome === atuais[inp.dataset.cluster]) continue;
        const r = await fetchFn(url(info.id, '/correcao'), { method: 'POST', credentials: 'same-origin', headers: cabecalhos({ 'Content-Type': 'application/json' }), body: JSON.stringify({ expected_revision: revisao, speaker_cluster_id: inp.dataset.cluster, display_name: nome }) });
        const resp = await r.json().catch(() => ({}));
        if (r.status === 409) throw new Error('A reunião foi alterada em outro lugar. Feche e abra a edição de novo.');
        if (!r.ok) throw new Error(resp.erro || 'Não foi possível salvar um participante.');
        revisao = resp.revision;
      }
      d.dlg.close();
      toast('success', 'Reunião atualizada');
      aoMudar();
    } catch (e) {
      d.avisar(e.message || 'Não foi possível salvar.');
    } finally {
      salvar.disabled = false; salvar.classList.remove('is-loading');
    }
  });
}

// ---- exclusão (dupla confirmação) --------------------------------------------

function resumoDoPlano(itens) {
  const grupos = new Map();
  for (const i of itens) {
    const g = grupos.get(i.categoria) || { n: 0, bytes: 0 };
    g.n += 1; g.bytes += i.bytes; grupos.set(i.categoria, g);
  }
  return grupos;
}

async function abrirExclusao(info, fetchFn, aoExcluir) {
  let plano;
  try {
    const r = await fetchFn(url(info.id, '/exclusao'), { credentials: 'same-origin', headers: cabecalhos() });
    plano = await r.json();
    if (!r.ok) { toast('error', 'Não é possível excluir agora', plano.erro || ''); return; }
  } catch (_) {
    toast('error', 'Não é possível excluir agora', 'A Central não respondeu.'); return;
  }
  // 1ª confirmação: o que exatamente será apagado.
  const p1 = dialogo({ titulo: `Excluir “${info.rotulo}”?`, subtitulo: info.quando, perigo: true, largo: true });
  p1.conteudo.appendChild(el('p', 'tk-dialog__consequencia', 'Todos os dados desta reunião serão apagados deste computador. Isto não pode ser desfeito.'));
  const ul = el('ul', 'tk-plano-exclusao');
  for (const [categoria, g] of resumoDoPlano(plano.itens)) {
    const li = el('li');
    li.append(el('span', 'tk-plano-exclusao__cat', categoria), el('span', 'tk-plano-exclusao__qtd', `${g.n} ${g.n === 1 ? 'item' : 'itens'} · ${mb(g.bytes)}`));
    ul.appendChild(li);
  }
  const total = el('li', 'tk-plano-exclusao__total');
  total.append(el('span', '', 'Total'), el('span', '', mb(plano.bytes_total)));
  ul.appendChild(total);
  const detalhes = el('details', 'tk-plano-exclusao__detalhes');
  detalhes.appendChild(el('summary', '', 'Ver a lista de arquivos'));
  const lista = el('ul', 'tk-plano-exclusao__arquivos');
  plano.itens.forEach((i) => lista.appendChild(el('li', '', i.caminho + (i.pasta ? '/' : ''))));
  detalhes.appendChild(lista);
  p1.conteudo.append(ul, detalhes);
  p1.botao('Cancelar', 'tk-btn--secondary', () => p1.dlg.close());
  p1.botao('Continuar', 'tk-btn--danger', () => { p1.dlg.close(); confirmarFinal(); });
  p1.abrir();
  p1.acoes.querySelector('.tk-btn--secondary').focus();

  // 2ª confirmação: digitar a palavra.
  function confirmarFinal() {
    const p2 = dialogo({ titulo: 'Confirmação final', perigo: true });
    const rot = el('label', 'tk-label'); rot.htmlFor = 'confirmar-exclusao';
    rot.append(document.createTextNode('Para apagar definitivamente, digite '), el('strong', '', PALAVRA));
    const inp = el('input', 'tk-input tk-input-confirmacao'); inp.id = 'confirmar-exclusao'; inp.autocomplete = 'off'; inp.spellcheck = false;
    p2.conteudo.append(el('p', 'tk-dialog__consequencia', `${plano.itens.length} itens (${mb(plano.bytes_total)}) de “${info.rotulo}” serão apagados.`), rot, inp);
    p2.botao('Cancelar', 'tk-btn--secondary', () => p2.dlg.close());
    const apagar = p2.botao('Excluir definitivamente', 'tk-btn--danger', executar);
    apagar.disabled = true;
    inp.addEventListener('input', () => { apagar.disabled = inp.value.trim().toUpperCase() !== PALAVRA; });
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !apagar.disabled) executar(); });
    p2.abrir();
    inp.focus();
    async function executar() {
      apagar.disabled = true; apagar.classList.add('is-loading'); p2.avisar('');
      try {
        const r = await fetchFn(url(info.id, '/excluir'), { method: 'POST', credentials: 'same-origin', headers: cabecalhos({ 'Content-Type': 'application/json' }), body: JSON.stringify({ plano_id: plano.plano_id, confirmacao: PALAVRA }) });
        const resp = await r.json().catch(() => ({}));
        if (!r.ok) { p2.avisar(resp.erro || 'Não foi possível excluir.'); apagar.disabled = false; return; }
        p2.dlg.close();
        toast('success', 'Reunião excluída', `${resp.excluidos} itens apagados.`);
        aoExcluir(info.id);
      } catch (_) {
        p2.avisar('A Central não respondeu; nada foi apagado.'); apagar.disabled = false;
      } finally {
        apagar.classList.remove('is-loading');
      }
    }
  }
}

/** Liga os botões de ação da lista (delegação: sobrevive a re-renderizações). */
export function ligarAcoesReunioes(lista, { fetchFn = (u, o) => fetch(u, o), aoMudar = () => {}, aoExcluir = () => {} } = {}) {
  lista.addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-acao]');
    if (!b || !lista.contains(b)) return;
    const linha = b.closest('.tk-row[data-id]');
    if (!linha) return;
    const info = infoLinha(linha);
    if (b.dataset.acao === 'resumo') abrirResumo(info, fetchFn);
    else if (b.dataset.acao === 'editar') abrirEdicao(info, fetchFn, aoMudar);
    else if (b.dataset.acao === 'excluir') abrirExclusao(info, fetchFn, aoExcluir);
  });
}
