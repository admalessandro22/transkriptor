/**
 * T-15.C4 — aba "Transcrição do Meet" na reunião: as legendas agrupadas por
 * falante, com horário e nome. Tudo via textContent (nada vira HTML); a
 * exportação é local (Blob) e só acontece com confirmação explícita.
 */
import { confirmar } from './ui.js';

const $ = (id) => document.getElementById(id);

function hora(ms) {
  const total = Math.max(0, Math.floor(Number(ms) / 1000) || 0);
  const dois = (n) => String(n).padStart(2, '0');
  return `${dois(Math.floor(total / 3600))}:${dois(Math.floor((total % 3600) / 60))}:${dois(total % 60)}`;
}

function blocosDe(dados) {
  const blocos = dados && Array.isArray(dados.transcricao_meet) ? dados.transcricao_meet : [];
  return blocos.filter((b) => b && typeof b.nome === 'string' && typeof b.texto === 'string');
}

export function textoTranscricaoMeet(blocos) {
  const linhas = blocos.map((b) => `[${hora(b.inicio_ms)}] ${b.nome}: ${b.texto.trim()}`);
  return linhas.join('\n') + (linhas.length ? '\n' : '');
}

function span(classe, texto) {
  const el = document.createElement('span');
  el.className = classe;
  el.textContent = texto;
  return el;
}

async function exportar(blocos, idReuniao) {
  const ok = await confirmar({
    id: 'dialogo-exportar-meet', confirmarId: 'confirmar-exportar-meet',
    titulo: 'Exportar a transcrição do Meet?',
    consequencia: 'O arquivo terá as legendas do Meet com nomes, fora da proteção do aplicativo. Guarde-o com cuidado.',
    confirmarRotulo: 'Exportar', perigo: true,
  });
  if (!ok) return;
  const url = URL.createObjectURL(new Blob([textoTranscricaoMeet(blocos)], { type: 'text/plain;charset=utf-8' }));
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = 'reuniao-' + idReuniao + '-meet.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export function renderTranscricaoMeet(dados, idReuniao) {
  const secao = $('secao-meet');
  const lista = $('lista-meet');
  if (!secao || !lista) return;
  const blocos = blocosDe(dados);
  secao.hidden = blocos.length === 0;
  lista.replaceChildren();
  for (const b of blocos) {
    const li = document.createElement('li');
    li.className = 'fala';
    const cab = document.createElement('div');
    cab.className = 'fala__cab';
    cab.append(span('fala__tempo', hora(b.inicio_ms)), span('fala__falante', b.nome));
    const texto = document.createElement('p');
    texto.className = 'fala__texto';
    texto.textContent = b.texto;
    li.append(cab, texto);
    lista.append(li);
  }
  const botao = $('exportar-meet');
  if (botao) botao.onclick = () => exportar(blocos, idReuniao);
}
